"""
OPC UA PLC Simulator.

Эмулирует промышленный контроллер с 8 параметрами. Генерирует реалистичные
значения через random walk с возвратом к базовому значению, периодически
воспроизводит аварийные сценарии.

Безопасность:
    OPC_SECURITY_MODE=None            — без шифрования (dev/тесты)
    OPC_SECURITY_MODE=Sign            — подпись без шифрования
    OPC_SECURITY_MODE=SignAndEncrypt  — подпись + шифрование (prod)

Соответствие IEC 62541-100:
    Nameplate        — Manufacturer, Model, SerialNumber, revisions
    DeviceHealth     — Int32 enum: NORMAL=0, FAILURE=1, CHECK_FUNCTION=2,
                       OFF_SPEC=3, MAINTENANCE_REQUIRED=4
"""
import logging
import math
import os
import random
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from opcua import Server, ua


# ============================================
# Логирование
# ============================================
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("plc-simulator")

# Понижаем уровень для шумных библиотек opcua
logging.getLogger("opcua").setLevel(logging.WARNING)
logging.getLogger("opcua.server").setLevel(logging.WARNING)
logging.getLogger("opcua.client").setLevel(logging.WARNING)
logging.getLogger("opcua.server.address_space").setLevel(logging.WARNING)
logging.getLogger("opcua.server.binary_server_asyncio").setLevel(logging.WARNING)


# ============================================
# IEC 62541-100: DeviceHealth enumeration
# ============================================
class DeviceHealth:
    """Значения DeviceHealthEnumeration (IEC 62541-100)."""
    NORMAL = 0
    FAILURE = 1
    CHECK_FUNCTION = 2
    OFF_SPEC = 3
    MAINTENANCE_REQUIRED = 4


# ============================================
# Конфигурация параметра
# ============================================
@dataclass
class ParamConfig:
    """Конфигурация одного параметра."""
    name: str
    base: float
    min_value: float
    max_value: float
    step: float
    alarm_target: float
    current: float = field(init=False)

    def __post_init__(self):
        self.current = self.base


# ============================================
# Симулятор PLC
# ============================================
class PLCSimulator:
    """Симулятор ПЛК с OPC UA-сервером."""

    # Паспортные данные (IEC 62541-100 Nameplate)
    NAMEPLATE: Dict[str, str] = {
        "Manufacturer":       "Rosimus Sim",
        "Model":              "PLC-Sim-3000",
        "SerialNumber":       "SN-2024-0001",
        "HardwareRevision":   "1.0",
        "SoftwareRevision":   "1.2.0",
        "DeviceRevision":     "A",
    }

    # Конфигурация параметров
    PARAMS: Dict[str, ParamConfig] = {
        "Temperature": ParamConfig("Temperature", 25.0, 15.0, 35.0, 0.3, 34.0),
        "Pressure":    ParamConfig("Pressure", 100.0, 80.0, 120.0, 1.5, 119.0),
        "Humidity":    ParamConfig("Humidity", 50.0, 30.0, 80.0, 2.0, 78.0),
        "Vibration":   ParamConfig("Vibration", 1.5, 0.2, 5.0, 0.2, 4.7),
        "Current":     ParamConfig("Current", 3.0, 0.5, 8.5, 0.4, 8.0),
        "Speed":       ParamConfig("Speed", 1000.0, 700.0, 1400.0, 15.0, 1370.0),
        "Level":       ParamConfig("Level", 50.0, 10.0, 90.0, 2.0, 12.0),
        "Frequency":   ParamConfig("Frequency", 50.0, 45.0, 55.0, 0.3, 54.0),
    }

    ALARM_PROBABILITY = 0.01
    CASCADE_PROBABILITY = 0.3

    def __init__(self, advertise_url: Optional[str] = None):
        self.advertise_url = advertise_url or os.getenv(
            "OPC_ADVERTISE_URL", "opc.tcp://localhost:4840"
        )

        # --- Безопасность OPC UA ---
        self.security_mode = os.getenv("OPC_SECURITY_MODE", "None").strip()
        self.cert_dir = os.getenv("OPC_CERT_DIR", "/certs")
        self.opc_user = os.getenv("OPC_USER", "")
        self.opc_password = os.getenv("OPC_PASSWORD", "")

        self.server: Optional[Server] = None
        self.variables: Dict[str, object] = {}
        self.alarm_state: Dict[str, int] = {}
        # Ссылки на стандартные узлы IEC 62541-100
        self.health_node = None
        self.tick = 0
        self.running = False

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    # ---------- Управление сервером ----------
    def _signal_handler(self, signum, frame):
        logger.info(f"Получен сигнал {signum}, останавливаюсь...")
        self.running = False

    def _setup_security(self) -> None:
        """Настраивает безопасность OPC UA (см. docstring модуля)."""
        if self.security_mode == "None":
            logger.warning(
                "⚠️ OPC UA security mode = None. Только для dev! "
                "В продакшене задайте OPC_SECURITY_MODE=SignAndEncrypt"
            )
            self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
            return

        if self.security_mode not in ("Sign", "SignAndEncrypt"):
            raise RuntimeError(
                f"Недопустимый OPC_SECURITY_MODE={self.security_mode!r}. "
                "Допустимо: None | Sign | SignAndEncrypt"
            )

        if not self.opc_user or not self.opc_password:
            raise RuntimeError(
                "OPC_SECURITY_MODE задан, но OPC_USER / OPC_PASSWORD не установлены"
            )

        cert_path = os.path.join(self.cert_dir, "server_cert.pem")
        key_path = os.path.join(self.cert_dir, "server_key.pem")
        for p in (cert_path, key_path):
            if not os.path.exists(p):
                raise RuntimeError(f"Сертификат не найден: {p}")

        self.server.load_certificate(cert_path)
        self.server.load_private_key(key_path)

        if self.security_mode == "SignAndEncrypt":
            policies = [ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt]
        else:
            policies = [ua.SecurityPolicyType.Basic256Sha256_Sign]
        self.server.set_security_policy(policies)

        # UserManager: в opcua==0.98 user_manager — это объект UserManager
        # с методом set_user_manager(), а не функция-колбэк.
        expected_user = self.opc_user
        expected_pw = self.opc_password

        def _user_manager(isession, username, password):
            ok = (username == expected_user and password == expected_pw)
            logger.info(f"OPC UA login attempt: user={username!r} ok={ok}")
            return ok

        self.server.user_manager.set_user_manager(_user_manager)

        logger.info(
            f"🔐 OPC UA security enabled: mode={self.security_mode}, "
            f"user={self.opc_user}, cert_dir={self.cert_dir}"
        )

    def _add_nameplate(self, plc_node, idx: int) -> None:
        """
        IEC 62541-100 Nameplate: паспортные данные устройства.

        Промышленные OPC UA-клиенты (Ignition, KEPServerEX, WinCC)
        ожидают увидеть эти узлы под объектом устройства.
        """
        nameplate = plc_node.add_object(idx, "Nameplate")
        for key, value in self.NAMEPLATE.items():
            prop = nameplate.add_property(idx, key, value)
            prop.set_writable(False)
        logger.info(
            f"📋 Nameplate добавлен: {len(self.NAMEPLATE)} свойств "
            f"({', '.join(self.NAMEPLATE.keys())})"
        )

    def _add_device_health(self, plc_node, idx: int) -> None:
        """
        IEC 62541-100 DeviceHealth: состояние устройства.

        Int32 enum:
            NORMAL               = 0
            FAILURE              = 1
            CHECK_FUNCTION       = 2
            OFF_SPEC             = 3
            MAINTENANCE_REQUIRED = 4

        Обновляется в _update_all_params() на каждом цикле.
        """
        self.health_node = plc_node.add_variable(
            idx, "DeviceHealth",
            DeviceHealth.NORMAL,
            varianttype=ua.VariantType.Int32,
        )
        self.health_node.set_writable(False)
        logger.info("🩺 DeviceHealth добавлен (IEC 62541-100)")

    def _setup_server(self) -> None:
        """Создаёт OPC UA-сервер и регистрирует переменные."""
        self.server = Server()
        self.server.set_endpoint(self.advertise_url)
        self.server.set_server_name("PLC Simulator")

        # Безопасность настраиваем ДО регистрации нод.
        self._setup_security()

        idx = self.server.register_namespace("PLC")
        objects = self.server.get_objects_node()
        plc = objects.add_object(idx, "PLC")

        # IEC 62541-100: Nameplate + DeviceHealth
        self._add_nameplate(plc, idx)
        self._add_device_health(plc, idx)

        # Технологические параметры
        for name, cfg in self.PARAMS.items():
            var = plc.add_variable(idx, name, cfg.current)
            var.set_writable(True)
            self.variables[name] = var

        logger.info(f"OPC UA сервер настроен: advertise={self.advertise_url}")
        logger.info(f"Зарегистрировано параметров: {len(self.variables)}")

    def start(self) -> None:
        """Запускает сервер и основной цикл."""
        try:
            self._setup_server()
            self.server.start()
            self.running = True

            logger.info("=" * 60)
            logger.info(f"✅ OPC UA сервер запущен, advertise={self.advertise_url}")
            logger.info(f"📊 Симулируется {len(self.PARAMS)} параметров")
            logger.info("🎬 Режим: random walk + mean reversion + аварии")
            logger.info("=" * 60)

            self._main_loop()

        except Exception as e:
            logger.exception(f"Критическая ошибка при запуске сервера: {e}")
            raise
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """Корректно останавливает сервер."""
        if self.server:
            try:
                self.server.stop()
                logger.info("OPC UA сервер остановлен")
            except Exception as e:
                logger.error(f"Ошибка при остановке сервера: {e}")

    # ---------- Основной цикл ----------
    def _main_loop(self) -> None:
        """Основной цикл обновления значений."""
        while self.running:
            try:
                self._update_all_params()
            except Exception as e:
                logger.exception(f"Ошибка в цикле обновления: {e}")
            time.sleep(2)

    def _update_all_params(self) -> None:
        """Обновляет все параметры, DeviceHealth и пишет в OPC UA."""
        self.tick += 1
        self._maybe_trigger_alarm()

        for name, cfg in self.PARAMS.items():
            try:
                if name in self.alarm_state and self.alarm_state[name] > 0:
                    value = self._apply_alarm(name, cfg)
                    self.alarm_state[name] -= 1
                    if self.alarm_state[name] == 0:
                        del self.alarm_state[name]
                        logger.info(f"✅ {name} вернулся в норму")
                else:
                    value = self._smooth_step(name, cfg)

                self.variables[name].set_value(value)
            except Exception as e:
                logger.error(f"Ошибка обновления параметра {name}: {e}")

        # IEC 62541-100: обновляем DeviceHealth на каждом цикле.
        # FAILURE (1) если есть активная авария, иначе NORMAL (0).
        if self.health_node is not None:
            try:
                new_health = (
                    DeviceHealth.FAILURE if self.alarm_state
                    else DeviceHealth.NORMAL
                )
                self.health_node.set_value(new_health)
            except Exception as e:
                logger.error(f"Ошибка обновления DeviceHealth: {e}")

    # ---------- Логика генерации ----------
    def _smooth_step(self, name: str, cfg: ParamConfig) -> float:
        """Плавное изменение с random walk, mean reversion и суточной волной."""
        current = cfg.current
        drift_to_base = (cfg.base - current) * 0.05
        random_walk = random.uniform(-cfg.step, cfg.step)
        daily_wave = math.sin(self.tick / 200.0) * cfg.step * 0.3

        new_value = current + drift_to_base + random_walk + daily_wave
        new_value = max(cfg.min_value, min(cfg.max_value, new_value))

        cfg.current = new_value
        return round(new_value, 2)

    def _apply_alarm(self, name: str, cfg: ParamConfig) -> float:
        """Плавно двигает значение к аварийному порогу."""
        new_value = cfg.current + (cfg.alarm_target - cfg.current) * 0.15
        cfg.current = new_value
        return round(new_value, 2)

    def _maybe_trigger_alarm(self) -> None:
        """С вероятностью ALARM_PROBABILITY запускает случайную аварию."""
        if random.random() >= self.ALARM_PROBABILITY:
            return

        param = random.choice(list(self.PARAMS.keys()))
        duration = random.randint(10, 25)
        self.alarm_state[param] = duration
        logger.warning(f"🚨 АВАРИЯ: {param} ({duration} циклов)")

        if random.random() < self.CASCADE_PROBABILITY:
            other = random.choice([p for p in self.PARAMS if p != param])
            duration2 = random.randint(8, 15)
            self.alarm_state[other] = duration2
            logger.warning(f"🚨 АВАРИЯ: {other} ({duration2} циклов)")


# ============================================
# Точка входа
# ============================================
def main() -> int:
    advertise_url = os.getenv("OPC_ADVERTISE_URL", "opc.tcp://localhost:4840")
    simulator = PLCSimulator(advertise_url=advertise_url)

    try:
        simulator.start()
    except Exception as e:
        logger.exception(f"Симулятор завершился с ошибкой: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())