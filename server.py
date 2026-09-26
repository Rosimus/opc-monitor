"""
OPC UA PLC Simulator.

Эмулирует промышленный контроллер с 8 параметрами. Генерирует реалистичные
значения через random walk с возвратом к базовому значению, периодически
воспроизводит аварийные сценарии.
"""
import logging
import math
import os
import random
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from opcua import Server


# ============================================
# Логирование
# ============================================
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("plc-simulator")

# Понижаем уровень для шумных библиотек opcua
logging.getLogger("opcua").setLevel(logging.WARNING)
logging.getLogger("opcua.server").setLevel(logging.WARNING)
logging.getLogger("opcua.client").setLevel(logging.WARNING)
logging.getLogger("opcua.server.address_space").setLevel(logging.WARNING)
logging.getLogger("opcua.server.binary_server_asyncio").setLevel(logging.WARNING)


# ============================================
# Конфигурация параметра
# ============================================
@dataclass
class ParamConfig:
    """Конфигурация одного параметра."""
    name: str
    base: float
    min_value: float
    max_value: float
    step: float
    alarm_target: float
    current: float = field(init=False)

    def __post_init__(self):
        self.current = self.base


# ============================================
# Симулятор PLC
# ============================================
class PLCSimulator:
    """Симулятор ПЛК с OPC UA-сервером."""

    # Конфигурация параметров
    PARAMS: Dict[str, ParamConfig] = {
        "Temperature": ParamConfig("Temperature", 25.0, 15.0, 35.0, 0.3, 34.0),
        "Pressure":    ParamConfig("Pressure", 100.0, 80.0, 120.0, 1.5, 119.0),
        "Humidity":    ParamConfig("Humidity", 50.0, 30.0, 80.0, 2.0, 78.0),
        "Vibration":   ParamConfig("Vibration", 1.5, 0.2, 5.0, 0.2, 4.7),
        "Current":     ParamConfig("Current", 3.0, 0.5, 8.5, 0.4, 8.0),
        "Speed":       ParamConfig("Speed", 1000.0, 700.0, 1400.0, 15.0, 1370.0),
        "Level":       ParamConfig("Level", 50.0, 10.0, 90.0, 2.0, 12.0),
        "Frequency":   ParamConfig("Frequency", 50.0, 45.0, 55.0, 0.3, 54.0),
    }

    # Вероятность запуска аварии за один цикл
    ALARM_PROBABILITY = 0.01
    # Вероятность каскадной аварии (второй параметр одновременно)
    CASCADE_PROBABILITY = 0.3

    def __init__(self, endpoint: str = "opc.tcp://0.0.0.0:4840"):
        self.endpoint = endpoint
        self.server: Optional[Server] = None
        self.variables: Dict[str, object] = {}
        self.alarm_state: Dict[str, int] = {}
        self.tick = 0
        self.running = False

        # Настройка graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    # ---------- Управление сервером ----------
    def _signal_handler(self, signum, frame):
        logger.info(f"Получен сигнал {signum}, останавливаюсь...")
        self.running = False

    def _setup_server(self) -> None:
        """Создаёт OPC UA-сервер и регистрирует переменные."""
        self.server = Server()
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name("PLC Simulator")

        idx = self.server.register_namespace("PLC")
        objects = self.server.get_objects_node()
        plc = objects.add_object(idx, "PLC")

        for name, cfg in self.PARAMS.items():
            var = plc.add_variable(idx, name, cfg.current)
            var.set_writable(True)
            self.variables[name] = var

        logger.info(f"OPC UA сервер настроен: {self.endpoint}")
        logger.info(f"Зарегистрировано параметров: {len(self.variables)}")

    def start(self) -> None:
        """Запускает сервер и основной цикл."""
        try:
            self._setup_server()
            self.server.start()
            self.running = True

            logger.info("=" * 60)
            logger.info(f"✅ OPC UA сервер запущен на {self.endpoint}")
            logger.info(f"📊 Симулируется {len(self.PARAMS)} параметров")
            logger.info("🎬 Режим: random walk + mean reversion + аварии")
            logger.info("=" * 60)

            self._main_loop()

        except Exception as e:
            logger.exception(f"Критическая ошибка при запуске сервера: {e}")
            raise
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """Корректно останавливает сервер."""
        if self.server:
            try:
                self.server.stop()
                logger.info("OPC UA сервер остановлен")
            except Exception as e:
                logger.error(f"Ошибка при остановке сервера: {e}")

    # ---------- Основной цикл ----------
    def _main_loop(self) -> None:
        """Основной цикл обновления значений."""
        while self.running:
            try:
                self._update_all_params()
            except Exception as e:
                # Не падаем при единичной ошибке, логируем и продолжаем
                logger.exception(f"Ошибка в цикле обновления: {e}")
            time.sleep(2)

    def _update_all_params(self) -> None:
        """Обновляет все параметры и записывает в OPC UA."""
        self.tick += 1
        self._maybe_trigger_alarm()

        for name, cfg in self.PARAMS.items():
            try:
                if name in self.alarm_state and self.alarm_state[name] > 0:
                    value = self._apply_alarm(name, cfg)
                    self.alarm_state[name] -= 1
                    if self.alarm_state[name] == 0:
                        del self.alarm_state[name]
                        logger.info(f"✅ {name} вернулся в норму")
                else:
                    value = self._smooth_step(name, cfg)

                self.variables[name].set_value(value)
            except Exception as e:
                logger.error(f"Ошибка обновления параметра {name}: {e}")

    # ---------- Логика генерации ----------
    def _smooth_step(self, name: str, cfg: ParamConfig) -> float:
        """Плавное изменение с random walk, mean reversion и суточной волной."""
        current = cfg.current
        drift_to_base = (cfg.base - current) * 0.05
        random_walk = random.uniform(-cfg.step, cfg.step)
        daily_wave = math.sin(self.tick / 200.0) * cfg.step * 0.3

        new_value = current + drift_to_base + random_walk + daily_wave
        new_value = max(cfg.min_value, min(cfg.max_value, new_value))

        cfg.current = new_value
        return round(new_value, 2)

    def _apply_alarm(self, name: str, cfg: ParamConfig) -> float:
        """Плавно двигает значение к аварийному порогу."""
        new_value = cfg.current + (cfg.alarm_target - cfg.current) * 0.15
        cfg.current = new_value
        return round(new_value, 2)

    def _maybe_trigger_alarm(self) -> None:
        """С вероятностью ALARM_PROBABILITY запускает случайную аварию."""
        if random.random() >= self.ALARM_PROBABILITY:
            return

        param = random.choice(list(self.PARAMS.keys()))
        duration = random.randint(10, 25)
        self.alarm_state[param] = duration
        logger.warning(f"🚨 АВАРИЯ: {param} ({duration} циклов)")

        # Каскадная авария
        if random.random() < self.CASCADE_PROBABILITY:
            other = random.choice([p for p in self.PARAMS if p != param])
            duration2 = random.randint(8, 15)
            self.alarm_state[other] = duration2
            logger.warning(f"🚨 АВАРИЯ: {other} ({duration2} циклов)")


# ============================================
# Точка входа
# ============================================
def main() -> int:
    endpoint = os.getenv("OPC_ENDPOINT", "opc.tcp://0.0.0.0:4840")
    simulator = PLCSimulator(endpoint=endpoint)

    try:
        simulator.start()
    except Exception as e:
        logger.exception(f"Симулятор завершился с ошибкой: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())