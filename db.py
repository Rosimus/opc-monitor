import os
import json
import hashlib
import redis
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Index, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
import logging
from utils import get_param_status

logger = logging.getLogger(__name__)

Base = declarative_base()


# --- Модели ---
class Measurement(Base):
    __tablename__ = 'measurements'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    temperature = Column(Float)
    pressure = Column(Float)
    humidity = Column(Float)
    vibration = Column(Float)
    current = Column(Float)
    speed = Column(Float)
    level = Column(Float)
    frequency = Column(Float)

    __table_args__ = (
        Index('idx_measurements_timestamp_status', 'timestamp', 'status'),
        Index('idx_measurements_status_timestamp', 'status', 'timestamp'),
    )


class ThresholdsHistory(Base):
    __tablename__ = 'thresholds_history'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    config_hash = Column(String(64), nullable=False)
    config_snapshot = Column(Text, nullable=False)


class ThresholdsOverride(Base):
    __tablename__ = 'thresholds_overrides'

    param_id = Column(String(50), primary_key=True)
    warning_low = Column(Float)
    alarm_low = Column(Float)
    warning_high = Column(Float)
    alarm_high = Column(Float)
    updated_at = Column(DateTime, nullable=False)
    user = Column(String(100))


class AppState(Base):
    __tablename__ = 'app_state'

    key = Column(String(50), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime)


class AlarmAcknowledgement(Base):
    __tablename__ = 'alarm_acknowledgements'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    param_id = Column(String(50))
    acknowledged_at = Column(DateTime, nullable=False)
    user = Column(String(100), default='operator')


class ThresholdsAudit(Base):
    __tablename__ = 'thresholds_audit'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    param_id = Column(String(50), nullable=False)
    old_values = Column(Text)
    new_values = Column(Text)
    user = Column(String(100))


class Database:
    def __init__(self, params_config: List[Dict[str, Any]] = None):
        self.params_config = params_config or []
        self.param_ids = [p['id'] for p in self.params_config]

        # PostgreSQL
        self.db_url = os.environ.get(
            'DATABASE_URL',
            f"postgresql://{os.getenv('POSTGRES_USER', 'opc_user')}:{os.getenv('POSTGRES_PASSWORD', 'secure_password')}@"
            f"{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/"
            f"{os.getenv('POSTGRES_DB', 'opc_monitor')}"
        )
        self.engine = create_engine(
            self.db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._init_db()

        # Redis
        self.cache_ttl = int(os.getenv('REDIS_CACHE_TTL', '30'))
        try:
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', '6379')),
                password=os.getenv('REDIS_PASSWORD') or None,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            self.redis_client.ping()
            logger.info("✅ Redis подключён")
        except Exception as e:
            logger.warning(f"⚠️ Redis недоступен, кэширование отключено: {e}")
            self.redis_client = None

    def _init_db(self):
        Base.metadata.create_all(self.engine)
        logger.info("✅ PostgreSQL инициализирован")

    def _get_session(self) -> Session:
        return self.SessionLocal()

    # ---------- Кэширование ----------
    def _cache_get(self, key: str) -> Optional[Any]:
        if not self.redis_client:
            return None
        try:
            val = self.redis_client.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None

    def _cache_set(self, key: str, value: Any, ttl: int = None):
        if not self.redis_client:
            return
        try:
            self.redis_client.setex(
                key,
                ttl or self.cache_ttl,
                json.dumps(value, default=str, ensure_ascii=False)
            )
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

    def _cache_delete(self, key: str):
        if not self.redis_client:
            return
        try:
            self.redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")

    def _cache_delete_pattern(self, pattern: str):
        if not self.redis_client:
            return
        try:
            for key in self.redis_client.scan_iter(match=pattern):
                self.redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Redis pattern delete error: {e}")

    # ---------- Измерения ----------
    def insert_measurement(self, data: Dict[str, Any]) -> None:
        with self._get_session() as session:
            measurement = Measurement(
                timestamp=datetime.fromisoformat(data['timestamp']),
                status=data['status'],
                **{pid: data.get(pid, 0.0) for pid in self.param_ids}
            )
            session.add(measurement)
            session.commit()

        # Инвалидируем кэш, чтобы клиент увидел свежие данные
        self._cache_delete('opc:latest')

    def get_latest(self, thresholds: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cache_key = 'opc:latest'

        cached = self._cache_get(cache_key)
        if cached:
            return cached

        with self._get_session() as session:
            measurement = session.query(Measurement).order_by(
                Measurement.timestamp.desc()
            ).first()

            if not measurement:
                return None

            result = {
                'timestamp': measurement.timestamp.isoformat(),
                'status': measurement.status
            }
            for pid in self.param_ids:
                val = getattr(measurement, pid, 0.0)
                result[pid] = val
                result[f'{pid}_status'] = get_param_status(
                    val, thresholds.get(pid, {}), pid
                )

        self._cache_set(cache_key, result, ttl=10)
        return result

    def get_history(self, thresholds: Dict[str, Any], limit: int = 100,
                    start_date: Optional[str] = None, end_date: Optional[str] = None,
                    status_filter: Optional[str] = None) -> List[Dict[str, Any]]:

        with self._get_session() as session:
            query = session.query(Measurement)

            if start_date:
                query = query.filter(Measurement.timestamp >= datetime.fromisoformat(start_date))
            if end_date:
                query = query.filter(Measurement.timestamp <= datetime.fromisoformat(end_date))
            if status_filter and status_filter.upper() != 'ALL':
                query = query.filter(Measurement.status == status_filter.upper())

            query = query.order_by(Measurement.timestamp.desc()).limit(limit)
            measurements = query.all()

            result = []
            for m in measurements:
                rec = {
                    'timestamp': m.timestamp.isoformat(),
                    'status': m.status
                }
                for pid in self.param_ids:
                    val = getattr(m, pid, 0.0)
                    rec[pid] = val
                    rec[f'{pid}_status'] = get_param_status(
                        val, thresholds.get(pid, {}), pid
                    )
                result.append(rec)

            result.reverse()
            return result

    def get_alarms(self, thresholds: Dict[str, Any],
                   start_date: Optional[str] = None, end_date: Optional[str] = None,
                   param_filter: Optional[str] = None) -> List[Dict[str, Any]]:

        with self._get_session() as session:
            query = session.query(Measurement).filter(
                Measurement.status == 'ALARM'
            )

            if start_date:
                query = query.filter(Measurement.timestamp >= datetime.fromisoformat(start_date))
            if end_date:
                query = query.filter(Measurement.timestamp <= datetime.fromisoformat(end_date))

            query = query.order_by(Measurement.timestamp.desc())
            measurements = query.all()

            result = []
            for m in measurements:
                rec = {
                    'timestamp': m.timestamp.isoformat(),
                    'status': m.status
                }
                for pid in self.param_ids:
                    val = getattr(m, pid, 0.0)
                    rec[pid] = val
                    status = get_param_status(val, thresholds.get(pid, {}), pid)
                    rec[f'{pid}_status'] = status

                if param_filter and rec.get(f'{param_filter}_status') != 'ALARM':
                    continue

                ack = self.get_acknowledgement(m.timestamp.isoformat())
                rec['acknowledged'] = ack is not None
                rec['acknowledged_at'] = ack['acknowledged_at'] if ack else None
                result.append(rec)

            return result

    def get_stats(self, thresholds: Dict[str, Any],
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None) -> Dict[str, Any]:

        cache_key = f'opc:stats:{start_date or "all"}:{end_date or "all"}'

        cached = self._cache_get(cache_key)
        if cached:
            return cached

        with self._get_session() as session:
            query = session.query(Measurement)
            if start_date:
                query = query.filter(Measurement.timestamp >= datetime.fromisoformat(start_date))
            if end_date:
                query = query.filter(Measurement.timestamp <= datetime.fromisoformat(end_date))

            total_records = query.count()
            total_alarms = query.filter(Measurement.status == 'ALARM').count()
            total_warnings = query.filter(Measurement.status == 'WARNING').count()

            stats = {}
            alarms_by_param = {}

            for pid in self.param_ids:
                result = session.query(
                    func.min(getattr(Measurement, pid)),
                    func.max(getattr(Measurement, pid)),
                    func.avg(getattr(Measurement, pid))
                )

                if start_date:
                    result = result.filter(Measurement.timestamp >= datetime.fromisoformat(start_date))
                if end_date:
                    result = result.filter(Measurement.timestamp <= datetime.fromisoformat(end_date))

                row = result.first()
                if row and row[0] is not None:
                    stats[pid] = {'min': row[0], 'max': row[1], 'avg': row[2]}
                else:
                    stats[pid] = {'min': None, 'max': None, 'avg': None}

                alarm_query = session.query(Measurement).filter(Measurement.status == 'ALARM')
                if start_date:
                    alarm_query = alarm_query.filter(Measurement.timestamp >= datetime.fromisoformat(start_date))
                if end_date:
                    alarm_query = alarm_query.filter(Measurement.timestamp <= datetime.fromisoformat(end_date))

                count = 0
                for m in alarm_query.all():
                    val = getattr(m, pid, 0.0)
                    if get_param_status(val, thresholds.get(pid, {}), pid) == 'ALARM':
                        count += 1
                alarms_by_param[pid] = count

            from sqlalchemy import cast, Date
            alarms_by_day_query = session.query(
                cast(Measurement.timestamp, Date).label('day'),
                func.count().label('cnt')
            ).filter(Measurement.status == 'ALARM')

            if start_date:
                alarms_by_day_query = alarms_by_day_query.filter(
                    Measurement.timestamp >= datetime.fromisoformat(start_date)
                )
            if end_date:
                alarms_by_day_query = alarms_by_day_query.filter(
                    Measurement.timestamp <= datetime.fromisoformat(end_date)
                )

            alarms_by_day = [
                {'date': row.day.isoformat(), 'count': row.cnt}
                for row in alarms_by_day_query.group_by('day').order_by('day').all()
            ]

            result = {
                'total_records': total_records,
                'total_alarms': total_alarms,
                'total_warnings': total_warnings,
                'stats_by_param': stats,
                'alarms_by_param': alarms_by_param,
                'alarms_by_day': alarms_by_day
            }

        self._cache_set(cache_key, result, ttl=60)
        return result

    def delete_old_records(self, days: int) -> int:
        if days <= 0:
            return 0

        cutoff = datetime.now() - timedelta(days=days)
        with self._get_session() as session:
            deleted = session.query(Measurement).filter(
                Measurement.timestamp < cutoff
            ).delete()
            session.commit()

        # Инвалидируем кэши после удаления
        self._cache_delete('opc:latest')
        self._cache_delete_pattern('opc:stats:*')
        return deleted

    # ---------- Пороги ----------
    def save_thresholds_snapshot(self, config: Dict[str, Any]) -> None:
        snapshot = {
            'params': config.get('opc', {}).get('params', []),
            'thresholds': config.get('thresholds', {})
        }
        hash_str = hashlib.md5(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

        with self._get_session() as session:
            last = session.query(ThresholdsHistory).order_by(
                ThresholdsHistory.timestamp.desc()
            ).first()

            if last and last.config_hash == hash_str:
                return

            history = ThresholdsHistory(
                timestamp=datetime.now(),
                config_hash=hash_str,
                config_snapshot=json.dumps(snapshot, ensure_ascii=False)
            )
            session.add(history)
            session.commit()

    def get_thresholds_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            history = session.query(ThresholdsHistory).order_by(
                ThresholdsHistory.timestamp.desc()
            ).limit(limit).all()

            result = []
            for h in history:
                result.append({
                    'timestamp': h.timestamp.isoformat(),
                    'snapshot': json.loads(h.config_snapshot)
                })
            result.reverse()
            return result

    def get_thresholds_overrides(self) -> Dict[str, Dict[str, Any]]:
        with self._get_session() as session:
            overrides = session.query(ThresholdsOverride).all()
            result = {}
            for o in overrides:
                result[o.param_id] = {
                    'warning_low': o.warning_low,
                    'alarm_low': o.alarm_low,
                    'warning_high': o.warning_high,
                    'alarm_high': o.alarm_high,
                    'updated_at': o.updated_at.isoformat()
                }
            return result

    def update_thresholds(self, param_id: str, thresholds: Dict[str, Any], user: str = 'operator') -> None:
        old = self.get_thresholds_overrides().get(param_id, {})

        with self._get_session() as session:
            override = session.query(ThresholdsOverride).filter(
                ThresholdsOverride.param_id == param_id
            ).first()

            if override:
                override.warning_low = thresholds.get('warning_low')
                override.alarm_low = thresholds.get('alarm_low')
                override.warning_high = thresholds.get('warning_high')
                override.alarm_high = thresholds.get('alarm_high')
                override.updated_at = datetime.now()
                override.user = user
            else:
                override = ThresholdsOverride(
                    param_id=param_id,
                    warning_low=thresholds.get('warning_low'),
                    alarm_low=thresholds.get('alarm_low'),
                    warning_high=thresholds.get('warning_high'),
                    alarm_high=thresholds.get('alarm_high'),
                    updated_at=datetime.now(),
                    user=user
                )
                session.add(override)

            audit = ThresholdsAudit(
                timestamp=datetime.now(),
                param_id=param_id,
                old_values=json.dumps(old),
                new_values=json.dumps(thresholds),
                user=user
            )
            session.add(audit)
            session.commit()

        # Инвалидируем кэши после изменения порогов
        self._cache_delete('opc:latest')
        self._cache_delete_pattern('opc:stats:*')
        self._cache_delete_pattern('opc:history:*')

    # ---------- Состояние приложения ----------
    def save_last_status(self, status: str, timestamp: str) -> None:
        with self._get_session() as session:
            state = session.query(AppState).filter(AppState.key == 'last_status').first()
            if state:
                state.value = status
                state.updated_at = datetime.fromisoformat(timestamp)
            else:
                state = AppState(
                    key='last_status',
                    value=status,
                    updated_at=datetime.fromisoformat(timestamp)
                )
                session.add(state)
            session.commit()

    def get_last_status(self) -> Optional[Dict[str, str]]:
        with self._get_session() as session:
            state = session.query(AppState).filter(AppState.key == 'last_status').first()
            if state:
                return {
                    'status': state.value,
                    'timestamp': state.updated_at.isoformat()
                }
            return None

    # ---------- Аварии ----------
    def acknowledge_alarm(self, timestamp: str, param_id: Optional[str] = None, user: str = 'operator') -> None:
        with self._get_session() as session:
            ack = AlarmAcknowledgement(
                timestamp=datetime.fromisoformat(timestamp),
                param_id=param_id,
                acknowledged_at=datetime.now(),
                user=user
            )
            session.add(ack)
            session.commit()

    def get_acknowledgement(self, timestamp: str, param_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            query = session.query(AlarmAcknowledgement).filter(
                AlarmAcknowledgement.timestamp == datetime.fromisoformat(timestamp)
            )
            if param_id:
                query = query.filter(AlarmAcknowledgement.param_id == param_id)

            ack = query.order_by(AlarmAcknowledgement.acknowledged_at.desc()).first()
            if ack:
                return {
                    'acknowledged_at': ack.acknowledged_at.isoformat(),
                    'user': ack.user
                }
            return None

    # ---------- Экспорт ----------
    def export_csv(self, start_date: Optional[str] = None, end_date: Optional[str] = None,
                   status_filter: Optional[str] = None, fields: Optional[List[str]] = None) -> str:
        import csv
        import io

        if fields is None:
            fields = ['timestamp', 'status'] + self.param_ids

        valid_fields = ['timestamp', 'status'] + self.param_ids
        fields = [f for f in fields if f in valid_fields]

        with self._get_session() as session:
            query = session.query(Measurement)
            if start_date:
                query = query.filter(Measurement.timestamp >= datetime.fromisoformat(start_date))
            if end_date:
                query = query.filter(Measurement.timestamp <= datetime.fromisoformat(end_date))
            if status_filter and status_filter.upper() != 'ALL':
                query = query.filter(Measurement.status == status_filter.upper())

            query = query.order_by(Measurement.timestamp)
            measurements = query.all()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(fields)

            for m in measurements:
                row = []
                for field in fields:
                    if field == 'timestamp':
                        row.append(m.timestamp.isoformat())
                    elif field == 'status':
                        row.append(m.status)
                    else:
                        row.append(getattr(m, field, 0.0))
                writer.writerow(row)

            return output.getvalue()