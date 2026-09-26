"""
Интеграционные тесты API.

Проверяют авторизацию, JWT-защиту и основные эндпоинты.
Используют моки для БД и конфигов — не требуют реальных PostgreSQL/Redis.
"""


# ============================================================
# Healthcheck
# ============================================================
class TestHealth:

    def test_health_endpoint_returns_200_or_503(self, app_client):
        """Healthcheck возвращает 200 (ok) или 503 (degraded)."""
        response = app_client.get("/health")
        assert response.status_code in [200, 503]
        data = response.get_json()
        assert "status" in data


# ============================================================
# Аутентификация
# ============================================================
class TestAuth:

    def test_login_wrong_credentials(self, app_client):
        """Неверные креды → 401."""
        response = app_client.post(
            "/api/auth/login",
            json={"username": "wrong", "password": "wrong"},
        )
        assert response.status_code == 401
        assert "error" in response.get_json()

    def test_login_empty_body(self, app_client):
        """Пустое тело → не 200."""
        response = app_client.post("/api/auth/login", json={})
        assert response.status_code != 200

    def test_login_correct_credentials(self, app_client):
        """Правильные креды → 200 + access_token."""
        response = app_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "test_password"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "access_token" in data
        assert len(data["access_token"]) > 20


# ============================================================
# JWT-защита
# ============================================================
class TestJWTAuth:

    def test_latest_without_token(self, app_client):
        """Без токена → 401."""
        response = app_client.get("/api/latest")
        assert response.status_code == 401

    def test_history_without_token(self, app_client):
        """Без токена → 401."""
        response = app_client.get("/api/history")
        assert response.status_code == 401

    def test_params_without_token(self, app_client):
        """Без токена → 401."""
        response = app_client.get("/api/params")
        assert response.status_code == 401

    def test_params_with_valid_token(self, app_client, auth_headers):
        """С валидным токеном → 200."""
        response = app_client.get("/api/params", headers=auth_headers)
        assert response.status_code == 200

    def test_latest_with_valid_token(self, app_client, auth_headers):
        """С валидным токеном → 200 + JSON."""
        response = app_client.get("/api/latest", headers=auth_headers)
        assert response.status_code == 200

    def test_invalid_token(self, app_client):
        """Некорректный токен → 401 или 422."""
        response = app_client.get(
            "/api/latest",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code in [401, 422]


# ============================================================
# Metrics (не требует авторизации)
# ============================================================
class TestMetrics:

    def test_metrics_endpoint(self, app_client):
        """Prometheus метрики доступны без авторизации."""
        response = app_client.get("/metrics")
        assert response.status_code == 200
        # Проверяем, что это Prometheus-формат
        assert b"# HELP" in response.data or b"# TYPE" in response.data


# ============================================================
# Root
# ============================================================
class TestRoot:

    def test_root_returns_html(self, app_client):
        """Корень возвращает HTML-страницу."""
        response = app_client.get("/")
        assert response.status_code == 200
        assert b"<html" in response.data.lower() or b"<!DOCTYPE" in response.data