import time
import yaml
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from opcua import Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from utils import get_param_status, load_config
from db import Database
import threading
import signal
from prometheus_client import Counter, Gauge, start_http_server
import structlog

# Включаем построчную буферизацию stdout (для Docker/K8s)
sys.stdout.reconfigure(line_buffering=True)


# --- Настройка структурированного логирования ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# --- Загрузка конфига ---
config: Dict[str, Any] = load_config()

# --- Метрики Prometheus ---
start_http_server(8001)
alerts_counter = Counter('opc_alerts_total', 'Total alerts', ['type'])
values_gauge = Gauge('opc_values', 'Current values', ['param_id'])
status_gauge = Gauge('opc_status', 'Current status', ['status'])

# --- Параметры ---
opc_cfg: Dict[str, Any] = config['opc']
params_list: List[Dict[str, Any]] = opc_cfg['params']
param_ids: List[str] = [p['id'] for p in params_list]
email_cfg: Dict[str, Any] = config['email']
telegram_cfg: Dict[str, Any] = config['telegram']
alert_cooldown: int = config['alerts']['cooldown_seconds']
retention: Dict[str, Any] = config.get('retention', {})
retention_enabled: bool = retention.get('enabled', False)
retention_days: int = retention.get('days', 30)

# Пароль email – из переменной окружения
email_password = os.environ.get('EMAIL_PASSWORD') or email_cfg.get('password', '')

# Пороги
THRESHOLDS: Dict[str, Dict[str, float]] = {}
for p in params_list:
    th: Dict[str, float] = {}
    for key in ['warning_low', 'alarm_low', 'warning_high', 'alarm_high', 'warning', 'alarm']:
        if key in p:
            th[key] = p[key]
    THRESHOLDS[p['id']] = th

logger.info("THRESHOLDS loaded", thresholds=THRESHOLDS)

# БД
db: Database = Database(params_list)
db.save_thresholds_snapshot(config)

last_alert_time: float = 0
cycle_count: int = 0
offline_mode: bool = False
last_known_values: Dict[str, float] = {}
running = True


# --- Функции отправки ---
def send_email_alert(subject: str, body: str) -> bool:
    if not email_cfg.get('enabled', False):
        return False

    msg = MIMEMultipart()
    msg['From'] = email_cfg['sender']
    msg['To'] = email_cfg['recipient']
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(email_cfg['smtp_server'], email_cfg['smtp_port'])
        server.starttls()
        server.login(email_cfg['sender'], email_password)
        server.sendmail(email_cfg['sender'], email_cfg['recipient'], msg.as_string())
        server.quit()
        logger.info("Email sent")
        return True
    except Exception as e:
        logger.error("Email error", error=str(e))
        return False


def send_telegram_alert(text: str) -> bool:
    if not telegram_cfg.get('enabled', False):
        return False

    url = f"https://api.telegram.org/bot{telegram_cfg['bot_token']}/sendMessage"
    try:
        r = requests.post(url, json={
            'chat_id': telegram_cfg['chat_id'],
            'text': text
        }, timeout=10)
        r.raise_for_status()
        logger.info("Telegram sent")
        return True
    except Exception as e:
        logger.error("Telegram error", error=str(e))
        return False


def get_overall_status(values: Dict[str, float]) -> str:
    for pid in param_ids:
        val = values.get(pid)
        if val is None:
            continue
        status = get_param_status(val, THRESHOLDS.get(pid, {}), pid)
        if status == 'ALARM':
            return "ALARM"

    for pid in param_ids:
        val = values.get(pid)
        if val is None:
            continue
        status = get_param_status(val, THRESHOLDS.get(pid, {}), pid)
        if status == 'WARNING':
            return "WARNING"

    return "NORMAL"


def cleanup_worker():
    while running:
        if retention_enabled and retention_days > 0:
            try:
                deleted = db.delete_old_records(retention_days)
                if deleted:
                    logger.info("Old records deleted", count=deleted)
            except Exception as e:
                logger.error("Cleanup error", error=str(e))
        time.sleep(3600)


def ping_opc_server(url: str):
    while running:
        try:
            test_client = Client(url)
            test_client.connect()
            test_client.disconnect()
            logger.debug("OPC server available")
        except Exception as e:
            logger.warning("OPC server unavailable", error=str(e))
        time.sleep(120)


def signal_handler(sig, frame):
    global running
    logger.info("Shutting down...")
    running = False
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# --- Запуск фоновых потоков ---
threading.Thread(target=cleanup_worker, daemon=True).start()
threading.Thread(target=ping_opc_server, args=(opc_cfg['url'],), daemon=True).start()

# --- Сигнал готовности для healthcheck ---
try:
    with open('/tmp/client_ready', 'w') as f:
        f.write('ready')
    logger.info("✅ Client готов к работе")
except Exception as e:
    logger.warning(f"Не удалось создать /tmp/client_ready: {e}")

# ========== ОСНОВНОЙ ЦИКЛ ==========
url = opc_cfg['url']

while running:
    client: Optional[Client] = None
    try:
        logger.info("Connecting to OPC server...")
        client = Client(url)
        client.connect()
        logger.info("Connected to OPC server")
        offline_mode = False

        objects = client.get_objects_node()
        plc = objects.get_child([opc_cfg['node_plc']])

        opc_vars: Dict[str, Any] = {}
        for p in params_list:
            try:
                opc_vars[p['id']] = plc.get_child([p['node']])
            except Exception as e:
                logger.error("Node not found", param=p['id'], node=p['node'], error=str(e))

        error_count = 0
        MAX_ERRORS = 5

        while running:
            try:
                values: Dict[str, float] = {}
                for pid, var in opc_vars.items():
                    val = var.get_value()
                    values[pid] = float(val) if val is not None else 0.0
                    values_gauge.labels(param_id=pid).set(values[pid])

                offline_mode = False
                last_known_values = values.copy()
                error_count = 0

            except Exception as e:
                logger.error("OPC read error", error=str(e))
                error_count += 1
                if error_count >= MAX_ERRORS:
                    logger.warning("Max errors reached, reconnecting...")
                    raise

                if not offline_mode:
                    offline_mode = True
                    logger.warning("Entering offline mode")

                values = last_known_values.copy() if last_known_values else {
                    pid: 0.0 for pid in param_ids
                }

            # Обновление порогов
            cycle_count += 1
            if cycle_count % 6 == 0:
                try:
                    overrides = db.get_thresholds_overrides()
                    for pid, th in THRESHOLDS.items():
                        if pid in overrides:
                            ov = overrides[pid]
                            for key in ['warning_low', 'alarm_low', 'warning_high', 'alarm_high']:
                                if ov.get(key) is not None:
                                    th[key] = ov[key]
                except Exception as e:
                    logger.error("Threshold update error", error=str(e))

            # Статус
            status = get_overall_status(values)
            status_gauge.labels(status=status).set(1)

            now = datetime.now().isoformat()

            if offline_mode:
                status = f"OFFLINE_{status}"

            measurement = {'timestamp': now, 'status': status}
            for pid in param_ids:
                measurement[pid] = values.get(pid, 0.0)

            db.insert_measurement(measurement)
            db.save_last_status(status, now)

            # Уведомление через WebSocket
            try:
                requests.post('http://web:5000/api/notify', timeout=1)
            except Exception:
                pass

            # Логирование
            val_str = ", ".join([f"{pid}={values.get(pid, 0):.2f}" for pid in param_ids])
            logger.info("Measurement", status=status, values=val_str)

            # Обработка аварии
            if status == "ALARM":
                current_time = time.time()
                if current_time - last_alert_time > alert_cooldown:
                    subject = "🔴 АВАРИЯ на OPC-мониторе!"
                    body = "\n".join([
                        f"{p['name']}: {values.get(p['id'], 0):.2f} {p.get('unit', '')}"
                        for p in params_list
                    ])
                    body += f"\nСтатус: АВАРИЯ"

                    send_email_alert(subject, body)
                    send_telegram_alert(body)
                    alerts_counter.labels(type='email').inc()
                    alerts_counter.labels(type='telegram').inc()

                    last_alert_time = current_time

            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Stopping client")
        break
    except Exception as e:
        logger.error("Critical error", error=str(e))
        if client:
            try:
                client.disconnect()
            except Exception:
                pass
        logger.info("Reconnecting in 10 seconds...")
        time.sleep(10)
        continue
    finally:
        if client:
            try:
                client.disconnect()
                logger.info("Client disconnected")
            except Exception:
                pass