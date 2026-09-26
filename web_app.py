from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_swagger_ui import get_swaggerui_blueprint
import io
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from utils import load_config, get_param_status
from db import Database
import gzip
from time import time
from functools import wraps
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

CORS(app, origins=['http://localhost:5000', 'http://localhost:3000'])
jwt = JWTManager(app)

# ============================================
# Security Headers (Flask-Talisman)
# ============================================
Talisman(
    app,
    force_https=False,  # HTTPS терминируется на ingress/ngrok
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,  # 1 год
    content_security_policy={
        'default-src': "'self'",
        'script-src': [
            "'self'",
            "'unsafe-inline'",  # для inline-скриптов в index.html
            'https://cdn.jsdelivr.net',
            'https://cdn.socket.io',
            'https://cdnjs.cloudflare.com',
        ],
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': ["'self'", 'data:', 'https:'],
        'connect-src': ["'self'", 'wss:', 'https:', 'ws:'],
        'font-src': ["'self'", 'data:'],
        'frame-ancestors': "'none'",
    },
    frame_options='DENY',
    referrer_policy='strict-origin-when-cross-origin',
    session_cookie_secure=False,  # для локальной разработки
    session_cookie_http_only=True,
)

# ============================================
# Rate Limiting (Flask-Limiter)
# ============================================
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per hour", "200 per minute"],
    storage_uri="memory://",
    strategy="fixed-window",
)

# --- Swagger ---
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'
try:
    swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
except Exception:
    pass

# --- Метрики ---
api_requests = Counter('api_requests_total', 'Total API requests', ['endpoint', 'method'])
api_latency = Histogram('api_latency_seconds', 'API latency', ['endpoint'])

# --- Логирование ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Загрузка конфига ---
config: Dict[str, Any] = load_config()
params_list: List[Dict[str, Any]] = config['opc']['params']
param_ids: List[str] = [p['id'] for p in params_list]

# --- База данных ---
db: Database = Database(params_list)


def load_thresholds() -> Dict[str, Dict[str, Any]]:
    base: Dict[str, Dict[str, Any]] = {}
    for p in params_list:
        th: Dict[str, Any] = {}
        for key in ['warning_low', 'alarm_low', 'warning_high', 'alarm_high', 'warning', 'alarm']:
            if key in p:
                th[key] = p[key]
        base[p['id']] = th

    overrides = db.get_thresholds_overrides()
    final: Dict[str, Dict[str, Any]] = {}
    for pid, th in base.items():
        if pid in overrides:
            ov = overrides[pid]
            for key in ['warning_low', 'alarm_low', 'warning_high', 'alarm_high']:
                if ov.get(key) is not None:
                    th[key] = ov[key]
        final[pid] = th
    return final


THRESHOLDS: Dict[str, Dict[str, Any]] = load_thresholds()
ALL_FIELDS: List[str] = ['timestamp', 'status'] + param_ids


# --- Аутентификация ---
@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute")  # Защита от брутфорса
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    admin_user = os.environ.get('ADMIN_USER', 'admin')
    admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin')

    if username == admin_user and password == admin_pass:
        access_token = create_access_token(identity=username)
        return jsonify({'access_token': access_token}), 200

    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/auth/refresh', methods=['POST'])
@jwt_required()
def refresh():
    current_user = get_jwt_identity()
    new_token = create_access_token(identity=current_user)
    return jsonify({'access_token': new_token}), 200


# --- Декоратор для метрик ---
def track_metrics(endpoint):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            start = time()
            try:
                result = f(*args, **kwargs)
                return result
            finally:
                api_requests.labels(endpoint=endpoint, method=request.method).inc()
                api_latency.labels(endpoint=endpoint).observe(time() - start)
        return decorated
    return decorator


# --- Эндпоинты ---
@app.route('/health')
def health():
    try:
        latest = db.get_latest(THRESHOLDS)
        if latest and latest.get('timestamp'):
            # Парсим timestamp из БД (naive, локальное время)
            ts = datetime.fromisoformat(latest['timestamp'].replace('Z', ''))

            # Сравниваем с текущим локальным временем (тоже naive)
            now = datetime.now()
            diff = now - ts

            if diff < timedelta(minutes=5):
                return jsonify({'status': 'ok', 'timestamp': latest['timestamp']}), 200

        return jsonify({'status': 'degraded', 'message': 'No recent data'}), 503
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/params')
@track_metrics('params')
@jwt_required()
def get_params():
    return jsonify(params_list)


@app.route('/api/thresholds')
@track_metrics('thresholds')
@jwt_required()
def thresholds():
    return jsonify(THRESHOLDS)


@app.route('/api/thresholds/history')
@track_metrics('thresholds_history')
@jwt_required()
def thresholds_history():
    limit = int(request.args.get('limit', 50))
    history = db.get_thresholds_history(limit)
    return jsonify(history)


@app.route('/api/thresholds/update', methods=['POST'])
@track_metrics('thresholds_update')
@jwt_required()
def update_thresholds():
    data = request.get_json()
    param_id = data.get('param_id')
    if not param_id:
        return jsonify({'error': 'param_id required'}), 400
    if param_id not in param_ids:
        return jsonify({'error': 'Invalid param_id'}), 400

    thresholds = {}
    for key in ['warning_low', 'alarm_low', 'warning_high', 'alarm_high']:
        val = data.get(key)
        if val is not None:
            try:
                thresholds[key] = float(val)
            except ValueError:
                return jsonify({'error': f'Invalid value for {key}'}), 400

    user = get_jwt_identity()
    db.update_thresholds(param_id, thresholds, user)

    global THRESHOLDS
    THRESHOLDS = load_thresholds()

    return jsonify({'status': 'ok'})


@app.route('/api/latest')
@track_metrics('latest')
@jwt_required()
def latest():
    data = db.get_latest(THRESHOLDS)
    if data:
        for pid in param_ids:
            if data.get(f'{pid}_status') == 'ALARM':
                data['status'] = 'ALARM'
                break
        else:
            data['status'] = 'NORMAL'

        if data['status'] == 'ALARM':
            ack = db.get_acknowledgement(data['timestamp'])
            data['acknowledged'] = ack is not None
            data['acknowledged_at'] = ack['acknowledged_at'] if ack else None
    return jsonify(data if data else {})


@app.route('/api/history')
@track_metrics('history')
@jwt_required()
def history():
    limit = int(request.args.get('limit', 100))
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status_filter = request.args.get('status', 'ALL')
    data = db.get_history(THRESHOLDS, limit, start_date, end_date, status_filter)
    return jsonify(data)


@app.route('/api/alarms')
@track_metrics('alarms')
@jwt_required()
def alarms():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    param = request.args.get('param')
    data = db.get_alarms(THRESHOLDS, start_date, end_date, param)
    return jsonify(data)


@app.route('/api/stats')
@track_metrics('stats')
@jwt_required()
def stats():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    data = db.get_stats(THRESHOLDS, start_date, end_date)
    return jsonify(data)


@app.route('/api/acknowledge', methods=['POST'])
@track_metrics('acknowledge')
@jwt_required()
def acknowledge_alarm():
    data = request.get_json()
    timestamp = data.get('timestamp')
    param_id = data.get('param_id')
    user = get_jwt_identity()

    if not timestamp:
        return jsonify({'error': 'timestamp required'}), 400

    db.acknowledge_alarm(timestamp, param_id, user)
    return jsonify({'status': 'ok'})


@app.route('/api/status/latest')
@track_metrics('status_latest')
@jwt_required()
def get_latest_status():
    status = db.get_last_status()
    if status:
        return jsonify(status)
    return jsonify({'status': 'NORMAL', 'timestamp': datetime.now().isoformat()})


@app.route('/api/notify', methods=['POST'])
@limiter.limit("60 per minute")  # Защита от флуда
def notify():
    # Просто возвращаем OK без WebSocket
    return '', 204


@app.route('/api/export')
@track_metrics('export')
@jwt_required()
def export_csv():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status_filter = request.args.get('status', 'ALL')
        fields_param = request.args.get('fields', '')

        if fields_param:
            selected_fields = [f.strip() for f in fields_param.split(',') if f.strip() in ALL_FIELDS]
        else:
            selected_fields = ALL_FIELDS[:]

        if not selected_fields:
            return "Нет выбранных полей", 400

        csv_data = db.export_csv(start_date, end_date, status_filter, selected_fields)
        if not csv_data.strip():
            return "Нет данных по фильтру", 404

        return send_file(
            io.BytesIO(csv_data.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'opc_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    except Exception as e:
        return str(e), 500


# ============================================
# Error handlers
# ============================================
@app.errorhandler(429)
def ratelimit_handler(e):
    """Обработчик превышения лимитов"""
    logger.warning(f"Rate limit exceeded from {get_remote_address()}: {e.description}")
    return jsonify({
        'error': 'Too many requests',
        'message': 'Please slow down and try again later',
        'retry_after': str(e.retry_after) if hasattr(e, 'retry_after') else '60'
    }), 429


@app.errorhandler(500)
def internal_error(e):
    """Обработчик внутренних ошибок"""
    logger.error(f"Internal error: {e}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'Please try again later'
    }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)