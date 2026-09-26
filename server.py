from opcua import Server
import random
import math
import time
from datetime import datetime


# ============================================
# Настройка OPC UA сервера
# ============================================
server = Server()
server.set_endpoint("opc.tcp://0.0.0.0:4840")
server.set_server_name("PLC Simulator")

idx = server.register_namespace("PLC")
objects = server.get_objects_node()
plc = objects.add_object(idx, "PLC")

# ============================================
# Параметры симуляции
# ============================================
# Формат: name -> (base, min, max, step, default)
PARAMS = {
    "Temperature": {"base": 25.0, "min": 15.0, "max": 35.0, "step": 0.3, "current": 25.0},
    "Pressure":    {"base": 100.0, "min": 80.0, "max": 120.0, "step": 1.5, "current": 100.0},
    "Humidity":    {"base": 50.0, "min": 30.0, "max": 80.0, "step": 2.0, "current": 50.0},
    "Vibration":   {"base": 1.5, "min": 0.2, "max": 5.0, "step": 0.2, "current": 1.5},
    "Current":     {"base": 3.0, "min": 0.5, "max": 8.5, "step": 0.4, "current": 3.0},
    "Speed":       {"base": 1000.0, "min": 700.0, "max": 1400.0, "step": 15.0, "current": 1000.0},
    "Level":       {"base": 50.0, "min": 10.0, "max": 90.0, "step": 2.0, "current": 50.0},
    "Frequency":   {"base": 50.0, "min": 45.0, "max": 55.0, "step": 0.3, "current": 50.0},
}

# Создаём переменные в OPC UA
variables = {}
for name, cfg in PARAMS.items():
    var = plc.add_variable(idx, name, cfg["current"])
    var.set_writable(True)
    variables[name] = var


# ============================================
# Состояние симуляции
# ============================================
alarm_state = {}          # активные аварии: {param: осталось_циклов}
tick = 0                  # счётчик циклов
START_TIME = time.time()


# ============================================
# Логика реалистичного изменения
# ============================================
def smooth_step(param_name: str, cfg: dict) -> float:
    """
    Плавное изменение значения с трендом и шумом.
    - Random walk (плавное блуждание)
    - Возврат к базовому значению (mean reversion)
    - Случайный шум
    """
    current = cfg["current"]
    base = cfg["base"]
    step = cfg["step"]
    min_v = cfg["min"]
    max_v = cfg["max"]

    # 1. Притяжение к базовому значению (чтобы не улетало слишком далеко)
    drift_to_base = (base - current) * 0.05

    # 2. Случайное блуждание
    random_walk = random.uniform(-step, step)

    # 3. Суточные колебания (медленные)
    daily_wave = math.sin(tick / 200.0) * step * 0.3

    # Итоговое изменение
    new_val = current + drift_to_base + random_walk + daily_wave

    # 4. Ограничение диапазона
    new_val = max(min_v, min(max_v, new_val))

    cfg["current"] = new_val
    return round(new_val, 2)


def trigger_alarm(param_name: str, duration: int = 15):
    """Запустить аварию на N циклов."""
    alarm_state[param_name] = duration


def apply_alarm(param_name: str, cfg: dict) -> float:
    """
    Наложить аварию — сдвигаем значение в сторону выхода за порог.
    Плавно, но заметно.
    """
    current = cfg["current"]
    base = cfg["base"]
    step = cfg["step"]

    # Сдвигаем в сторону от нормы
    if param_name == "Temperature":
        target = cfg["max"] - 1  # ~34
    elif param_name == "Pressure":
        target = cfg["max"] - 1  # ~119
    elif param_name == "Vibration":
        target = cfg["max"] - 0.3  # ~4.7
    elif param_name == "Current":
        target = cfg["max"] - 0.5  # ~8
    elif param_name == "Level":
        target = cfg["min"] + 2  # низкий уровень
    elif param_name == "Frequency":
        target = cfg["max"] - 1  # ~54
    elif param_name == "Speed":
        target = cfg["max"] - 30
    elif param_name == "Humidity":
        target = cfg["max"] - 2
    else:
        target = base

    # Плавно двигаемся к target
    new_val = current + (target - current) * 0.15
    cfg["current"] = new_val
    return round(new_val, 2)


def maybe_trigger_random_alarm():
    """
    С вероятностью ~1% за цикл запустить случайную аварию.
    Также иногда — 'каскад' из 2 аварий (интереснее для скриншотов).
    """
    if random.random() < 0.01:  # 1% на цикл = примерно раз в 100 циклов
        param = random.choice(list(PARAMS.keys()))
        duration = random.randint(10, 25)
        trigger_alarm(param, duration)
        print(f"🚨 [{datetime.now().strftime('%H:%M:%S')}] АВАРИЯ: {param} ({duration} циклов)")

        # 30% шанс на вторую аварию (каскад)
        if random.random() < 0.3:
            param2 = random.choice([p for p in PARAMS.keys() if p != param])
            duration2 = random.randint(8, 15)
            trigger_alarm(param2, duration2)
            print(f"🚨 [{datetime.now().strftime('%H:%M:%S')}] АВАРИЯ: {param2} ({duration2} циклов)")


def update_all_params():
    """Обновить все параметры и записать в OPC UA."""
    global tick
    tick += 1

    maybe_trigger_random_alarm()

    for name, cfg in PARAMS.items():
        # Если активна авария — применяем её
        if name in alarm_state and alarm_state[name] > 0:
            val = apply_alarm(name, cfg)
            alarm_state[name] -= 1
            if alarm_state[name] == 0:
                del alarm_state[name]
                print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] {name} вернулся в норму")
        else:
            val = smooth_step(name, cfg)

        variables[name].set_value(val)


# ============================================
# Запуск сервера
# ============================================
server.start()
print("=" * 60)
print("✅ OPC UA сервер запущен на opc.tcp://0.0.0.0:4840")
print(f"📊 Симулируется {len(PARAMS)} параметров:")
for name in PARAMS:
    print(f"   • {name}")
print("=" * 60)
print("🎬 Режим симуляции:")
print("   • Плавные изменения (random walk)")
print("   • Возврат к норме (mean reversion)")
print("   • Суточные колебания")
print("   • Случайные аварии (~1% за цикл)")
print("   • Каскадные аварии (30% случаев)")
print("=" * 60)

try:
    while True:
        update_all_params()
        time.sleep(2)
except KeyboardInterrupt:
    print("\n⏹ Остановка сервера...")
finally:
    server.stop()
    print("✅ Сервер остановлен")