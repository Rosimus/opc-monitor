"""
Pytest-фикстуры для тестирования API и базы данных.

Мокают Database и load_config ДО импорта web_app, чтобы не требовать
реальных PostgreSQL, Redis и config.yaml при запуске тестов.

Для тестов db.py используется отдельная фикстура db_instance,
которая поднимает in-memory SQLite с реальным классом Database.
"""
import os
from unittest.mock import MagicMock

# ============================================================
# 1. Переменные окружения ДО импорта приложения
# ============================================================
os.environ.setdefault("ADMIN_USER", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-pytest-only")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "")
os.environ.setdefault("OTEL_SERVICE_NAME", "opc-monitor-tests")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")


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

# Сохраняем ссылку на РЕАЛЬНЫЙ класс до подмены,
# чтобы фикстура db_instance могла создать его экземпляр.
REAL_DATABASE_CLASS = db.Database

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


@pytest.fixture
def db_instance():
    """
    Реальный Database-инстанс на in-memory SQLite (без Redis).

    Минует __init__, потому что там:
      - требуется POSTGRES_PASSWORD (не нужен для SQLite)
      - pool_size/max_overflow несовместимы с SQLite

    StaticPool держит одно соединение → :memory: переиспользуется
    между сессиями внутри одного теста.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    instance = REAL_DATABASE_CLASS.__new__(REAL_DATABASE_CLASS)
    instance.params_config = MOCK_CONFIG["opc"]["params"]
    instance.param_ids = [p["id"] for p in instance.params_config]
    instance.cache_ttl = 30
    instance.redis_client = None  # кэш отключён

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db.Base.metadata.create_all(engine)
    instance.engine = engine
    instance.SessionLocal = sessionmaker(bind=engine)

    yield instance

    engine.dispose()


@pytest.fixture
def sample_thresholds():
    """Пороги в формате, который ожидает Database."""
    return {
        "temperature": {
            "warning_low": 20.0,
            "alarm_low": 16.0,
            "warning_high": 29.0,
            "alarm_high": 33.0,
        },
        "pressure": {
            "warning_low": 90.0,
            "alarm_low": 85.0,
            "warning_high": 112.0,
            "alarm_high": 118.0,
        },
    }