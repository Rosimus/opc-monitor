"""
Pytest-фикстуры для тестирования API.

Мокают Database и load_config ДО импорта web_app, чтобы не требовать
реальных PostgreSQL, Redis и config.yaml при запуске тестов.
"""
import os
import sys
from unittest.mock import MagicMock

# ============================================================
# 1. Переменные окружения ДО импорта приложения
# ============================================================
os.environ.setdefault("ADMIN_USER", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-pytest-only")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("REDIS_HOST", "localhost")


# ============================================================
# 2. Мок load_config ДО импорта web_app
# ============================================================
import utils

MOCK_CONFIG = {
    "opc": {
        "url": "opc.tcp://localhost:4840",
        "node_plc": "2:PLC",
        "params": [
            {
                "id": "temperature",
                "name": "Температура",
                "node": "2:Temperature",
                "unit": "°C",
                "warning_low": 20.0,
                "alarm_low": 16.0,
                "warning_high": 29.0,
                "alarm_high": 33.0,
            },
            {
                "id": "pressure",
                "name": "Давление",
                "node": "2:Pressure",
                "unit": "кПа",
                "warning_low": 90.0,
                "alarm_low": 85.0,
                "warning_high": 112.0,
                "alarm_high": 118.0,
            },
        ],
    },
    "alerts": {"cooldown_seconds": 300},
    "retention": {"enabled": True, "days": 30},
    "email": {"enabled": False},
    "telegram": {"enabled": False},
    "logging": {"level": "INFO"},
}

utils.load_config = lambda: MOCK_CONFIG


# ============================================================
# 3. Мок Database ДО импорта web_app
# ============================================================
import db

mock_db_instance = MagicMock()
mock_db_instance.get_thresholds_overrides.return_value = {}
mock_db_instance.get_latest.return_value = {
    "timestamp": "2026-09-26T10:00:00",
    "status": "NORMAL",
    "temperature": 25.0,
    "temperature_status": "NORMAL",
    "pressure": 100.0,
    "pressure_status": "NORMAL",
}
mock_db_instance.get_history.return_value = []
mock_db_instance.get_alarms.return_value = []
mock_db_instance.get_stats.return_value = {
    "total_records": 0,
    "total_alarms": 0,
    "total_warnings": 0,
    "stats_by_param": {},
    "alarms_by_param": {},
    "alarms_by_day": [],
}
mock_db_instance.get_thresholds_history.return_value = []
mock_db_instance.get_thresholds_overrides.return_value = {}

db.Database = lambda *args, **kwargs: mock_db_instance


# ============================================================
# 4. Фикстуры
# ============================================================
import pytest


@pytest.fixture(scope="session")
def app_client():
    """Flask test client с замоканными зависимостями."""
    import web_app as web_module

    app = web_module.app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers(app_client):
    """Получить JWT-токен и вернуть заголовки с авторизацией."""
    response = app_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test_password"},
    )
    if response.status_code != 200:
        pytest.skip("Не удалось получить токен")
    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}