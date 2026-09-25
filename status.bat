@echo off
chcp 65001 >nul

echo ========================================
echo   OPC Monitor - Status
echo ========================================
echo.

echo 📋 Статус подов:
kubectl get pods -n opc-monitor
echo.

echo 📋 Статус сервисов:
kubectl get svc -n opc-monitor
echo.

echo 📋 Статус PVC:
kubectl get pvc -n opc-monitor
echo.

echo 📋 Статус HPA:
kubectl get hpa -n opc-monitor
echo.

echo 📊 Информация о Minikube:
minikube ip
echo.

pause