#!/usr/bin/env pwsh
# ==================================================
# OPC Monitor - Quick Deploy Script
# ==================================================

param(
    [switch]$Delete = $false,
    [switch]$Restart = $false,
    [switch]$Logs = $false
)

if ($Delete) {
    Write-Host "🗑️ Удаление приложения..." -ForegroundColor Yellow
    kubectl delete namespace opc-monitor
    Write-Host "✅ Удалено" -ForegroundColor Green
    exit 0
}

if ($Restart) {
    Write-Host "🔄 Перезапуск подов..." -ForegroundColor Yellow
    kubectl rollout restart deployment -n opc-monitor
    Write-Host "✅ Перезапущено" -ForegroundColor Green
    exit 0
}

if ($Logs) {
    Write-Host "📋 Логи web:" -ForegroundColor Yellow
    kubectl logs -f deployment/web -n opc-monitor
    exit 0
}

Write-Host "🚀 Запуск деплоя..." -ForegroundColor Cyan

# Сборка образа
docker build -t opc-monitor:latest .
minikube image load opc-monitor:latest

# Применение манифестов
kubectl apply -f k8s/

# Ожидание готовности
kubectl wait --for=condition=ready pod -l app=web -n opc-monitor --timeout=120s

Write-Host "✅ Деплой завершен!" -ForegroundColor Green

kubectl get pods -n opc-monitor
kubectl get svc -n opc-monitor