@echo off
chcp 65001 >nul

echo ========================================
echo   OPC Monitor - Stop
echo ========================================
echo.

echo Остановка Minikube...
minikube stop

echo.
echo ✅ Minikube остановлен
echo.
echo Для полного удаления: minikube delete
echo.

pause