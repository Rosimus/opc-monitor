import yaml
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union

def load_config() -> Dict[str, Any]:
    with open("/app/config.yaml", 'r') as f:
        return yaml.safe_load(f)

def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None

def get_param_status(value: float, thresholds: Dict[str, Any], param_type: str) -> str:
    if not thresholds:
        return 'NORMAL'
    
    t = thresholds
    
    # Двусторонний контроль
    if t.get('warning_high') is not None and t.get('alarm_high') is not None:
        if value < t['alarm_low'] or value > t['alarm_high']:
            return 'ALARM'
        if value < t['warning_low'] or value > t['warning_high']:
            return 'WARNING'
        return 'NORMAL'
    
    # Односторонний (только превышение)
    if 'alarm_low' in t and 'warning_low' in t:
        if value >= t['alarm_low']:
            return 'ALARM'
        if value >= t['warning_low']:
            return 'WARNING'
        return 'NORMAL'
    
    return 'NORMAL'

def convert_temp(value: float, unit: str) -> float:
    return value * 9/5 + 32 if unit == 'F' else value

def convert_press(value: float, unit: str) -> float:
    if unit == 'bar':
        return value / 100
    if unit == 'psi':
        return value * 0.1450377
    return value

def get_temp_unit_label(unit: str) -> str:
    return '°F' if unit == 'F' else '°C'

def get_press_unit_label(unit: str) -> str:
    if unit == 'bar':
        return 'бар'
    if unit == 'psi':
        return 'psi'
    return 'кПа'