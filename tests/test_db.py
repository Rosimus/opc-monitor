"""
Integration-тесты для db.py на in-memory SQLite.

Проверяют реальные SQL-запросы, сериализацию, вычисление статусов
и работу всех публичных методов Database.
"""
from datetime import datetime, timedelta

import pytest


# ============================================================
# Хелперы
# ============================================================

def _measurement(ts: str, status: str = "NORMAL",
                 temperature: float = 25.0, pressure: float = 100.0) -> dict:
    return {
        "timestamp": ts,
        "status": status,
        "temperature": temperature,
        "pressure": pressure,
    }


# ============================================================
# Measurements: insert + get_latest
# ============================================================

class TestInsertAndLatest:
    def test_get_latest_empty(self, db_instance, sample_thresholds):
        assert db_instance.get_latest(sample_thresholds) is None

    def test_insert_and_get_latest(self, db_instance, sample_thresholds):
        db_instance.insert_measurement(_measurement("2026-09-26T10:00:00"))
        result = db_instance.get_latest(sample_thresholds)

        assert result is not None
        assert result["temperature"] == 25.0
        assert result["pressure"] == 100.0
        assert result["status"] == "NORMAL"

    def test_get_latest_returns_most_recent(self, db_instance, sample_thresholds):
        db_instance.insert_measurement(
            _measurement("2026-09-26T10:00:00", temperature=22.0))
        db_instance.insert_measurement(
            _measurement("2026-09-26T11:00:00", temperature=27.0))

        result = db_instance.get_latest(sample_thresholds)
        assert result["temperature"] == 27.0

    def test_get_latest_calculates_param_status(self, db_instance, sample_thresholds):
        # temperature = 35 → выше alarm_high=33 → ALARM
        # pressure = 80    → ниже alarm_low=85  → ALARM
        db_instance.insert_measurement(
            _measurement("2026-09-26T10:00:00", temperature=35.0, pressure=80.0))

        result = db_instance.get_latest(sample_thresholds)
        assert result["temperature_status"] == "ALARM"
        assert result["pressure_status"] == "ALARM"

    def test_insert_uses_zero_for_missing_params(self, db_instance, sample_thresholds):
        # Передаём только temperature, pressure отсутствует
        db_instance.insert_measurement({
            "timestamp": "2026-09-26T10:00:00",
            "status": "NORMAL",
            "temperature": 25.0,
        })
        result = db_instance.get_latest(sample_thresholds)
        assert result["pressure"] == 0.0


# ============================================================
# get_history
# ============================================================

class TestGetHistory:
    def test_empty(self, db_instance, sample_thresholds):
        assert db_instance.get_history(sample_thresholds) == []

    def test_returns_all_sorted_ascending(self, db_instance, sample_thresholds):
        for i in range(3):
            db_instance.insert_measurement(
                _measurement(f"2026-09-26T1{i}:00:00", temperature=20.0 + i))

        result = db_instance.get_history(sample_thresholds)
        assert len(result) == 3
        # ascending (после reverse)
        assert result[0]["temperature"] == 20.0
        assert result[2]["temperature"] == 22.0

    def test_limit(self, db_instance, sample_thresholds):
        for i in range(5):
            db_instance.insert_measurement(
                _measurement(f"2026-09-26T1{i}:00:00"))

        result = db_instance.get_history(sample_thresholds, limit=2)
        assert len(result) == 2

    def test_filter_by_status(self, db_instance, sample_thresholds):
        db_instance.insert_measurement(_measurement("2026-09-26T10:00:00", status="NORMAL"))
        db_instance.insert_measurement(_measurement("2026-09-26T11:00:00", status="ALARM"))

        result = db_instance.get_history(sample_thresholds, status_filter="ALARM")
        assert len(result) == 1
        assert result[0]["status"] == "ALARM"

    def test_filter_by_status_all_returns_everything(self, db_instance, sample_thresholds):
        db_instance.insert_measurement(_measurement("2026-09-26T10:00:00", status="NORMAL"))
        db_instance.insert_measurement(_measurement("2026-09-26T11:00:00", status="ALARM"))

        result = db_instance.get_history(sample_thresholds, status_filter="ALL")
        assert len(result) == 2

    def test_filter_by_dates(self, db_instance, sample_thresholds):
        db_instance.insert_measurement(_measurement("2026-09-26T08:00:00"))
        db_instance.insert_measurement(_measurement("2026-09-26T12:00:00"))
        db_instance.insert_measurement(_measurement("2026-09-26T20:00:00"))

        result = db_instance.get_history(
            sample_thresholds,
            start_date="2026-09-26T10:00:00",
            end_date="2026-09-26T18:00:00",
        )
        assert len(result) == 1
        assert result[0]["timestamp"].startswith("2026-09-26T12")


# ============================================================
# get_alarms
# ============================================================

class TestGetAlarms:
    def test_empty(self, db_instance, sample_thresholds):
        assert db_instance.get_alarms(sample_thresholds) == []

    def test_only_alarm_status(self, db_instance, sample_thresholds):
        db_instance.insert_measurement(_measurement("2026-09-26T10:00:00", status="NORMAL"))
        db_instance.insert_measurement(_measurement("2026-09-26T11:00:00", status="ALARM"))

        result = db_instance.get_alarms(sample_thresholds)
        assert len(result) == 1
        assert result[0]["status"] == "ALARM"

    def test_includes_acknowledgement_info(self, db_instance, sample_thresholds):
        ts = "2026-09-26T10:00:00"
        db_instance.insert_measurement(_measurement(ts, status="ALARM"))
        db_instance.acknowledge_alarm(ts, param_id=None, user="operator")

        result = db_instance.get_alarms(sample_thresholds)
        assert len(result) == 1
        assert result[0]["acknowledged"] is True
        assert result[0]["acknowledged_at"] is not None


# ============================================================
# get_stats
# ============================================================

class TestGetStats:
    def test_empty(self, db_instance, sample_thresholds):
        stats = db_instance.get_stats(sample_thresholds)
        assert stats["total_records"] == 0
        assert stats["total_alarms"] == 0
        assert stats["total_warnings"] == 0

    def test_total_records(self, db_instance, sample_thresholds):
        for i in range(4):
            db_instance.insert_measurement(_measurement(f"2026-09-26T1{i}:00:00"))

        stats = db_instance.get_stats(sample_thresholds)
        assert stats["total_records"] == 4

    def test_stats_by_param_min_max_avg(self, db_instance, sample_thresholds):
        db_instance.insert_measurement(_measurement("2026-09-26T10:00:00", temperature=20.0))
        db_instance.insert_measurement(_measurement("2026-09-26T11:00:00", temperature=30.0))

        stats = db_instance.get_stats(sample_thresholds)
        assert stats["stats_by_param"]["temperature"]["min"] == 20.0
        assert stats["stats_by_param"]["temperature"]["max"] == 30.0
        assert stats["stats_by_param"]["temperature"]["avg"] == 25.0

    @pytest.mark.xfail(
        reason="SQLite's cast(timestamp, Date) returns a date object, but SQLAlchemy "
               "applies a str_to_date processor that expects a string. In PostgreSQL "
               "this works correctly. Skipped for SQLite-based tests."
    )
    def test_alarms_by_param(self, db_instance, sample_thresholds):
        # temperature=35 → param_status=ALARM
        db_instance.insert_measurement(
            _measurement("2026-09-26T10:00:00", status="ALARM", temperature=35.0))
        db_instance.insert_measurement(
            _measurement("2026-09-26T11:00:00", status="NORMAL", temperature=25.0))

        stats = db_instance.get_stats(sample_thresholds)
        assert stats["alarms_by_param"]["temperature"] == 1
        assert stats["alarms_by_param"]["pressure"] == 0


# ============================================================
# delete_old_records
# ============================================================

class TestDeleteOldRecords:
    def test_zero_days_returns_zero(self, db_instance):
        assert db_instance.delete_old_records(0) == 0
        assert db_instance.delete_old_records(-5) == 0

    def test_deletes_old_only(self, db_instance):
        old_ts = (datetime.now() - timedelta(days=60)).isoformat()
        new_ts = datetime.now().isoformat()

        db_instance.insert_measurement(_measurement(old_ts))
        db_instance.insert_measurement(_measurement(new_ts))

        deleted = db_instance.delete_old_records(30)
        assert deleted == 1


# ============================================================
# Thresholds: snapshots
# ============================================================

class TestThresholdsSnapshot:
    def test_saves_new_snapshot(self, db_instance):
        config = {"opc": {"params": [{"id": "temperature"}]}, "thresholds": {}}
        db_instance.save_thresholds_snapshot(config)

        history = db_instance.get_thresholds_history()
        assert len(history) == 1
        # save_thresholds_snapshot сохраняет как {'params': [...], 'thresholds': {}}
        assert history[0]["snapshot"]["params"][0]["id"] == "temperature"

    def test_deduplicates_by_hash(self, db_instance):
        config = {"opc": {"params": [{"id": "temperature"}]}, "thresholds": {}}
        db_instance.save_thresholds_snapshot(config)
        db_instance.save_thresholds_snapshot(config)  # same hash → no new

        history = db_instance.get_thresholds_history()
        assert len(history) == 1

    def test_different_config_creates_new_snapshot(self, db_instance):
        db_instance.save_thresholds_snapshot(
            {"opc": {"params": [{"id": "a"}]}, "thresholds": {}})
        db_instance.save_thresholds_snapshot(
            {"opc": {"params": [{"id": "b"}]}, "thresholds": {}})

        history = db_instance.get_thresholds_history()
        assert len(history) == 2


# ============================================================
# Thresholds: overrides
# ============================================================

class TestThresholdsOverrides:
    def test_empty_initially(self, db_instance):
        assert db_instance.get_thresholds_overrides() == {}

    def test_insert_new_override(self, db_instance):
        db_instance.update_thresholds(
            "temperature",
            {"warning_low": 21.0, "alarm_low": 17.0, "warning_high": 30.0, "alarm_high": 34.0},
            user="admin",
        )
        overrides = db_instance.get_thresholds_overrides()

        assert "temperature" in overrides
        assert overrides["temperature"]["warning_low"] == 21.0
        assert overrides["temperature"]["alarm_high"] == 34.0

    def test_update_existing_override(self, db_instance):
        db_instance.update_thresholds(
            "temperature",
            {"warning_low": 21.0, "alarm_low": 17.0, "warning_high": 30.0, "alarm_high": 34.0},
        )
        db_instance.update_thresholds(
            "temperature",
            {"warning_low": 22.0, "alarm_low": 18.0, "warning_high": 31.0, "alarm_high": 35.0},
            user="admin2",
        )
        overrides = db_instance.get_thresholds_overrides()

        assert overrides["temperature"]["warning_low"] == 22.0
        assert overrides["temperature"]["warning_high"] == 31.0

    def test_update_writes_audit(self, db_instance):
        db_instance.update_thresholds(
            "temperature",
            {"warning_low": 21.0, "alarm_low": 17.0, "warning_high": 30.0, "alarm_high": 34.0},
            user="admin",
        )
        # Проверяем через прямой session — аудит не имеет публичного метода чтения
        from db import ThresholdsAudit
        with db_instance.SessionLocal() as session:
            rows = session.query(ThresholdsAudit).all()
        assert len(rows) == 1
        assert rows[0].param_id == "temperature"
        assert rows[0].user == "admin"


# ============================================================
# AppState: last_status
# ============================================================

class TestAppState:
    def test_get_none_when_empty(self, db_instance):
        assert db_instance.get_last_status() is None

    def test_save_and_get(self, db_instance):
        ts = "2026-09-26T10:00:00"
        db_instance.save_last_status("ALARM", ts)
        result = db_instance.get_last_status()

        assert result["status"] == "ALARM"
        assert result["timestamp"].startswith("2026-09-26T10:00:00")

    def test_update_overwrites(self, db_instance):
        db_instance.save_last_status("NORMAL", "2026-09-26T10:00:00")
        db_instance.save_last_status("ALARM", "2026-09-26T11:00:00")

        result = db_instance.get_last_status()
        assert result["status"] == "ALARM"


# ============================================================
# Alarm acknowledgements
# ============================================================

class TestAlarmAcknowledgement:
    def test_get_none_when_not_acknowledged(self, db_instance):
        assert db_instance.get_acknowledgement("2026-09-26T10:00:00") is None

    def test_acknowledge_and_get(self, db_instance):
        ts = "2026-09-26T10:00:00"
        db_instance.acknowledge_alarm(ts, param_id=None, user="operator")

        ack = db_instance.get_acknowledgement(ts)
        assert ack is not None
        assert ack["user"] == "operator"

    def test_acknowledge_with_param_id(self, db_instance):
        ts = "2026-09-26T10:00:00"
        db_instance.acknowledge_alarm(ts, param_id="temperature", user="op1")
        db_instance.acknowledge_alarm(ts, param_id="pressure", user="op2")

        ack = db_instance.get_acknowledgement(ts, param_id="temperature")
        assert ack["user"] == "op1"


# ============================================================
# export_csv
# ============================================================

class TestExportCsv:
    def test_empty_returns_headers_only(self, db_instance):
        csv = db_instance.export_csv()
        lines = csv.strip().split("\n")
        assert len(lines) == 1
        assert "timestamp" in lines[0]
        assert "temperature" in lines[0]

    def test_exports_records(self, db_instance):
        db_instance.insert_measurement(_measurement("2026-09-26T10:00:00", temperature=25.0))
        csv = db_instance.export_csv()
        lines = csv.strip().split("\n")
        assert len(lines) == 2
        assert "25.0" in lines[1]

    def test_custom_fields_subset(self, db_instance):
        db_instance.insert_measurement(_measurement("2026-09-26T10:00:00"))
        csv = db_instance.export_csv(fields=["timestamp", "temperature"])
        header = csv.split("\n")[0]
        assert "temperature" in header
        assert "pressure" not in header

    def test_filter_by_status(self, db_instance):
        db_instance.insert_measurement(_measurement("2026-09-26T10:00:00", status="NORMAL"))
        db_instance.insert_measurement(_measurement("2026-09-26T11:00:00", status="ALARM"))

        csv = db_instance.export_csv(status_filter="ALARM")
        lines = csv.strip().split("\n")
        assert len(lines) == 2  # header + 1 alarm
        assert "ALARM" in lines[1]