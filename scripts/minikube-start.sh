#!/bin/bash
# ==================================================
# OPC Monitor - Minikube Startup Script
# ==================================================

set -e

echo "========================================"
echo "  OPC Monitor - Minikube Deployment"
echo "========================================"

# 1. Проверка Minikube
echo -e "\n[1/7] Проверка Minikube..."
if ! command -v minikube &> /dev/null; then
    echo "❌ Minikube не установлен!"
    echo "Скачайте: https://minikube.sigs.k8s.io/docs/start/"
    exit 1
fi
echo "✅ Minikube найден"

# 2. Запуск Minikube
echo -e "\n[2/7] Запуск Minikube..."
minikube start --driver=docker --memory=4096 --cpus=4
echo "✅ Minikube запущен"

# 3. Включение аддонов
echo -e "\n[3/7] Включение аддонов..."
minikube addons enable ingress
minikube addons enable metrics-server
minikube addons enable dashboard
echo "✅ Аддоны включены"

# 4. Сборка Docker образа
echo -e "\n[4/7] Сборка Docker образа..."
docker build -t opc-monitor:latest .
echo "✅ Образ собран"

# 5. Загрузка образа в Minikube
echo -e "\n[5/7] Загрузка образа в Minikube..."
minikube image load opc-monitor:latest
echo "✅ Образ загружен"

# 6. Применение манифестов
echo -e "\n[6/7] Развертывание приложения..."
kubectl create namespace opc-monitor --dry-run=client -o yaml | kubectl apply -f -

for manifest in pvc.yaml configmap.yaml secret.yaml postgres.yaml redis.yaml server.yaml client.yaml web.yaml prometheus.yaml grafana.yaml ingress.yaml hpa.yaml; do
    if [ -f "k8s/$manifest" ]; then
        echo "  Применение: $manifest"
        kubectl apply -f "k8s/$manifest"
    else
        echo "  ⚠️ Файл не найден: $manifest"
    fi
done

echo "✅ Приложение развернуто"

# 7. Ожидание готовности
echo -e "\n[7/7] Ожидание готовности подов..."
kubectl wait --for=condition=ready pod -l app=web -n opc-monitor --timeout=180s
kubectl wait --for=condition=ready pod -l app=postgres -n opc-monitor --timeout=180s
kubectl wait --for=condition=ready pod -l app=redis -n opc-monitor --timeout=180s

MINIKUBE_IP=$(minikube ip)
echo -e "\n========================================"
echo "  ✅ OPC Monitor развернут!"
echo "========================================"
echo -e "\n📊 Доступ к приложению:"
echo "  Web UI: http://$MINIKUBE_IP:30500"
echo "  Grafana: http://$MINIKUBE_IP:30300"
echo "  Prometheus: http://$MINIKUBE_IP:30900"
echo "  Dashboard: minikube dashboard"

echo -e "\n🔑 Учетные данные:"
echo "  Login: admin / admin (измените в секретах!)"

echo -e "\n📋 Команды управления:"
echo "  Просмотр подов: kubectl get pods -n opc-monitor"
echo "  Просмотр логов: kubectl logs -f <pod-name> -n opc-monitor"
echo "  Остановка: minikube stop"
echo "  Удаление: minikube delete"

echo -e "\n✅ Готово!"