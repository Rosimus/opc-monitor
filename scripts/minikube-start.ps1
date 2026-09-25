#!/usr/bin/env pwsh
# ==================================================
# OPC Monitor - Minikube Startup Script (Windows)
# ==================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OPC Monitor - Minikube Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Проверка Minikube
Write-Host "`n[1/7] Проверка Minikube..." -ForegroundColor Yellow
$minikube = Get-Command minikube -ErrorAction SilentlyContinue
if (-not $minikube) {
    Write-Host "❌ Minikube не установлен!" -ForegroundColor Red
    Write-Host "Скачайте: https://minikube.sigs.k8s.io/docs/start/" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Minikube найден" -ForegroundColor Green

# 2. Запуск Minikube
Write-Host "`n[2/7] Запуск Minikube..." -ForegroundColor Yellow
minikube start --driver=docker --memory=4096 --cpus=4
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка запуска Minikube" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Minikube запущен" -ForegroundColor Green

# 3. Включение аддонов
Write-Host "`n[3/7] Включение аддонов..." -ForegroundColor Yellow
minikube addons enable ingress
minikube addons enable metrics-server
minikube addons enable dashboard
Write-Host "✅ Аддоны включены" -ForegroundColor Green

# 4. Сборка Docker образа
Write-Host "`n[4/7] Сборка Docker образа..." -ForegroundColor Yellow
docker build -t opc-monitor:latest .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка сборки образа" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Образ собран" -ForegroundColor Green

# 5. Загрузка образа в Minikube
Write-Host "`n[5/7] Загрузка образа в Minikube..." -ForegroundColor Yellow
minikube image load opc-monitor:latest
Write-Host "✅ Образ загружен" -ForegroundColor Green

# 6. Применение манифестов
Write-Host "`n[6/7] Развертывание приложения..." -ForegroundColor Yellow

# Создание namespace
kubectl create namespace opc-monitor --dry-run=client -o yaml | kubectl apply -f -

# Применение всех манифестов
$manifests = @(
    "pvc.yaml",
    "configmap.yaml",
    "secret.yaml",
    "postgres.yaml",
    "redis.yaml",
    "server.yaml",
    "client.yaml",
    "web.yaml",
    "prometheus.yaml",
    "grafana.yaml",
    "ingress.yaml",
    "hpa.yaml"
)

foreach ($manifest in $manifests) {
    $path = "k8s/$manifest"
    if (Test-Path $path) {
        Write-Host "  Применение: $manifest" -ForegroundColor Gray
        kubectl apply -f $path
    } else {
        Write-Host "  ⚠️ Файл не найден: $manifest" -ForegroundColor Yellow
    }
}

Write-Host "✅ Приложение развернуто" -ForegroundColor Green

# 7. Ожидание готовности
Write-Host "`n[7/7] Ожидание готовности подов..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=web -n opc-monitor --timeout=180s
kubectl wait --for=condition=ready pod -l app=postgres -n opc-monitor --timeout=180s
kubectl wait --for=condition=ready pod -l app=redis -n opc-monitor --timeout=180s

# Информация о доступе
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  ✅ OPC Monitor развернут!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

$minikube_ip = minikube ip
Write-Host "`n📊 Доступ к приложению:" -ForegroundColor Yellow
Write-Host "  Web UI: http://$minikube_ip`:30500" -ForegroundColor White
Write-Host "  Grafana: http://$minikube_ip`:30300" -ForegroundColor White
Write-Host "  Prometheus: http://$minikube_ip`:30900" -ForegroundColor White
Write-Host "  Dashboard: minikube dashboard" -ForegroundColor White

Write-Host "`n🔑 Учетные данные:" -ForegroundColor Yellow
Write-Host "  Login: admin / admin (измените в секретах!)" -ForegroundColor White

Write-Host "`n📋 Команды управления:" -ForegroundColor Yellow
Write-Host "  Просмотр подов: kubectl get pods -n opc-monitor" -ForegroundColor White
Write-Host "  Просмотр логов: kubectl logs -f <pod-name> -n opc-monitor" -ForegroundColor White
Write-Host "  Остановка: minikube stop" -ForegroundColor White
Write-Host "  Удаление: minikube delete" -ForegroundColor White

Write-Host "`n✅ Готово!" -ForegroundColor Green