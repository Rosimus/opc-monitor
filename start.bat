@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   OPC Monitor - Startup Script
echo ========================================
echo.

REM ============================================
REM 1. Проверка Docker
REM ============================================
echo [1/5] Проверка Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker не установлен!
    echo Скачайте Docker Desktop: https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)
echo [OK] Docker найден
echo.

REM ============================================
REM 2. Проверка Minikube
REM ============================================
echo [2/5] Проверка Minikube...
minikube version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Minikube не установлен!
    echo Скачайте Minikube: https://minikube.sigs.k8s.io/docs/start/
    echo.
    pause
    exit /b 1
)
echo [OK] Minikube найден
echo.

REM ============================================
REM 3. Создание .env если нет
REM ============================================
echo [3/5] Проверка .env файла...
if not exist .env (
    echo [INFO] Создание .env из .env.example
    copy .env.example .env
    echo [WARNING] Отредактируйте .env и запустите снова!
    echo.
    echo Нажмите любую клавишу для открытия .env в Notepad...
    pause >nul
    notepad .env
    echo.
    echo После редактирования запустите скрипт снова.
    pause
    exit /b 0
)
echo [OK] .env найден
echo.

REM ============================================
REM 4. Создание Kubernetes секрета
REM ============================================
echo [4/5] Создание Kubernetes секретов...

REM Загрузка переменных из .env
for /f "usebackq tokens=*" %%a in (".env") do (
    set "%%a"
)

REM Создание secret.yaml
(
echo apiVersion: v1
echo kind: Secret
echo metadata:
echo   name: opc-secrets
echo   namespace: opc-monitor
echo type: Opaque
echo stringData:
echo   POSTGRES_USER: %POSTGRES_USER%
echo   POSTGRES_PASSWORD: %POSTGRES_PASSWORD%
echo   POSTGRES_DB: %POSTGRES_DB%
echo   EMAIL_PASSWORD: %EMAIL_PASSWORD%
echo   ADMIN_USER: %ADMIN_USER%
echo   ADMIN_PASSWORD: %ADMIN_PASSWORD%
echo   JWT_SECRET_KEY: %JWT_SECRET_KEY%
echo   GRAFANA_PASSWORD: %GRAFANA_PASSWORD%
) > k8s\secret.yaml

echo [OK] Секреты созданы
echo.

REM ============================================
REM 5. Запуск Minikube и деплой
REM ============================================
echo [5/5] Запуск Minikube и деплой...

REM Запуск Minikube
echo   Запуск Minikube...
minikube start --driver=docker --memory=4096 --cpus=4
if errorlevel 1 (
    echo [ERROR] Ошибка запуска Minikube
    pause
    exit /b 1
)

REM Включение аддонов
echo   Включение аддонов...
minikube addons enable ingress
minikube addons enable metrics-server
minikube addons enable dashboard

REM Сборка образа
echo   Сборка Docker образа...
docker build -t opc-monitor:latest .
if errorlevel 1 (
    echo [ERROR] Ошибка сборки образа
    pause
    exit /b 1
)

REM Загрузка в Minikube
echo   Загрузка образа в Minikube...
minikube image load opc-monitor:latest

REM Применение манифестов
echo   Применение Kubernetes манифестов...
kubectl apply -f k8s\

REM Ожидание готовности
echo   Ожидание готовности подов...
kubectl wait --for=condition=ready pod -l app=web -n opc-monitor --timeout=180s
kubectl wait --for=condition=ready pod -l app=postgres -n opc-monitor --timeout=180s
kubectl wait --for=condition=ready pod -l app=redis -n opc-monitor --timeout=180s

echo.
echo ========================================
echo   ✅ OPC Monitor успешно запущен!
echo ========================================
echo.

REM Получение IP
for /f "usebackq tokens=*" %%i in (`minikube ip`) do set MINIKUBE_IP=%%i

echo 📊 Доступ к приложению:
echo   Web UI: http://%MINIKUBE_IP%:30500
echo   Grafana: http://%MINIKUBE_IP%:30300
echo   Prometheus: http://%MINIKUBE_IP%:30900
echo.
echo 🔑 Учетные данные:
echo   Login: %ADMIN_USER% / %ADMIN_PASSWORD%
echo.
echo 📋 Команды управления:
echo   Просмотр подов: kubectl get pods -n opc-monitor
echo   Просмотр логов: kubectl logs -f deployment/web -n opc-monitor
echo   Остановка: minikube stop
echo   Удаление: minikube delete
echo.
echo ========================================
echo.

pause