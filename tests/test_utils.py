"""
Тесты для utils.py — чистые функции без внешних зависимостей.
"""
import pytest
from datetime import datetime

from utils import (
    get_param_status,
    parse_datetime,
    convert_temp,
    convert_press,
    get_temp_unit_label,
    get_press_unit_label,
)


# ============================================================
# get_param_status — двусторонний контроль (warning_low/high + alarm_low/high)
# ============================================================
class TestGetParamStatusTwoSided:
    """Тесты для параметров с двумя порогами (например, temperature)."""

    THRESHOLDS = {
        "warning_low": 20.0,
        "alarm_low": 16.0,
        "warning_high": 29.0,
        "alarm_high": 33.0,
    }

    def test_normal_value(self):
        """Значение внутри нормы → NORMAL."""
        assert get_param_status(25.0, self.THRESHOLDS, "temp") == "NORMAL"

    def test_normal_low_boundary(self):
        """Значение на нижней границе нормы → NORMAL."""
        assert get_param_status(20.0, self.THRESHOLDS, "temp") == "NORMAL"

    def test_normal_high_boundary(self):
        """Значение на верхней границе нормы → NORMAL."""
        assert get_param_status(29.0, self.THRESHOLDS, "temp") == "NORMAL"

    def test_warning_low(self):
        """Ниже warning_low → WARNING."""
        assert get_param_status(18.0, self.THRESHOLDS, "temp") == "WARNING"

    def test_warning_high(self):
        """Выше warning_high → WARNING."""
        assert get_param_status(31.0, self.THRESHOLDS, "temp") == "WARNING"

    def test_alarm_low(self):
        """Ниже alarm_low → ALARM."""
        assert get_param_status(15.0, self.THRESHOLDS, "temp") == "ALARM"

    def test_alarm_high(self):
        """Выше alarm_high → ALARM."""
        assert get_param_status(35.0, self.THRESHOLDS, "temp") == "ALARM"

    def test_way_above_alarm(self):
        """Сильно выше порога → всё ещё ALARM."""
        assert get_param_status(100.0, self.THRESHOLDS, "temp") == "ALARM"


# ============================================================
# get_param_status — односторонний контроль (только превышение)
# ============================================================
class TestGetParamStatusOneSided:
    """Тесты для параметров с одним порогом (например, vibration)."""

    THRESHOLDS = {
        "warning_low": 3.0,
        "alarm_low": 4.0,
    }

    def test_normal(self):
        assert get_param_status(1.5, self.THRESHOLDS, "vibration") == "NORMAL"

    def test_warning(self):
        assert get_param_status(3.5, self.THRESHOLDS, "vibration") == "WARNING"

    def test_alarm(self):
        assert get_param_status(5.0, self.THRESHOLDS, "vibration") == "ALARM"


# ============================================================
# get_param_status — edge cases
# ============================================================
class TestGetParamStatusEdgeCases:

    def test_empty_thresholds(self):
        """Пустые пороги → NORMAL (безопасное поведение)."""
        assert get_param_status(25.0, {}, "temp") == "NORMAL"

    def test_none_thresholds(self):
        """None → NORMAL."""
        assert get_param_status(25.0, None, "temp") == "NORMAL"


# ============================================================
# parse_datetime
# ============================================================
class TestParseDatetime:

    def test_iso_without_tz(self):
        """ISO без таймзоны."""
        result = parse_datetime("2026-09-26T10:30:00")
        assert result == datetime(2026, 9, 26, 10, 30, 0)

    def test_iso_with_z(self):
        """ISO с Z (UTC) → naive UTC."""
        result = parse_datetime("2026-09-26T10:30:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 9
        assert result.day == 26

    def test_empty_string(self):
        """Пустая строка → None."""
        assert parse_datetime("") is None

    def test_none(self):
        """None → None."""
        assert parse_datetime(None) is None

    def test_invalid_format(self):
        """Некорректный формат → None."""
        assert parse_datetime("not-a-date") is None


# ============================================================
# Конвертеры
# ============================================================
class TestConverters:

    def test_convert_temp_celsius(self):
        """Celsius остаётся без изменений."""
        assert convert_temp(25.0, "C") == 25.0

    def test_convert_temp_fahrenheit(self):
        """25°C → 77°F."""
        assert convert_temp(25.0, "F") == 77.0

    def test_convert_temp_zero_fahrenheit(self):
        """0°C → 32°F."""
        assert convert_temp(0.0, "F") == 32.0

    def test_convert_press_kpa(self):
        """kPa остаётся без изменений."""
        assert convert_press(100.0, "kPa") == 100.0

    def test_convert_press_bar(self):
        """100 kPa → 1 bar."""
        assert convert_press(100.0, "bar") == 1.0

    def test_convert_press_psi(self):
        """100 kPa → ~14.5 psi."""
        result = convert_press(100.0, "psi")
        assert abs(result - 14.50377) < 0.001


# ============================================================
# Лейблы единиц измерения
# ============================================================
class TestUnitLabels:

    def test_temp_label_celsius(self):
        assert get_temp_unit_label("C") == "°C"

    def test_temp_label_fahrenheit(self):
        assert get_temp_unit_label("F") == "°F"

    def test_press_label_kpa(self):
        assert get_press_unit_label("kPa") == "кПа"

    def test_press_label_bar(self):
        assert get_press_unit_label("bar") == "бар"

    def test_press_label_psi(self):
        assert get_press_unit_label("psi") == "psi"