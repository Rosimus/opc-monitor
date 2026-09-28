"""
Инициализация OpenTelemetry для distributed tracing.

Экспортирует трейсы в Jaeger через OTLP (gRPC).
Автоматически инструментирует Flask, SQLAlchemy и requests.
Добавляет trace_id в structlog-логи.
"""
import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def _build_provider(service: str, endpoint: str) -> TracerProvider:
    """Создать TracerProvider с OTLP-экспортёром в Jaeger."""
    resource = Resource.create({SERVICE_NAME: service})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def init_tracing(app, engine=None):
    """Инициализирует OpenTelemetry для Flask-приложения (web_app)."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    service = os.environ.get("OTEL_SERVICE_NAME", "opc-monitor-web")

    if not endpoint:
        logger.warning("OTEL_EXPORTER_OTLP_ENDPOINT не задан, трейсинг отключён")
        return

    try:
        provider = _build_provider(service, endpoint)
        trace.set_tracer_provider(provider)

        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()
        if engine is not None:
            SQLAlchemyInstrumentor().instrument(engine=engine)

        logger.info(
            f"✅ OpenTelemetry инициализирован: service={service}, endpoint={endpoint}"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации OpenTelemetry: {e}")


def init_client_tracing():
    """
    Инициализирует OpenTelemetry для client.py.

    Без Flask-инструментирования — только TracerProvider.
    Возвращает tracer для создания span'ов вручную.
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    service = os.environ.get("OTEL_SERVICE_NAME", "opc-monitor-client")

    if not endpoint:
        logger.warning("OTEL_EXPORTER_OTLP_ENDPOINT не задан, трейсинг client отключён")
        return trace.get_tracer("opc-monitor-client-noop")

    try:
        provider = _build_provider(service, endpoint)
        trace.set_tracer_provider(provider)
        logger.info(
            f"✅ OpenTelemetry (client) инициализирован: service={service}, endpoint={endpoint}"
        )
        return trace.get_tracer(service)
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации OpenTelemetry (client): {e}")
        return trace.get_tracer("opc-monitor-client-noop")


def add_trace_id_processor(logger, method_name, event_dict):
    """Structlog processor: добавляет trace_id из текущего OTel span."""
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx is not None and ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
    else:
        event_dict["trace_id"] = "-"
    return event_dict


def configure_structlog():
    """Настроить structlog с trace_id и JSON-форматом."""
    import structlog

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            add_trace_id_processor,
            structlog.processors.JSONRenderer(),
        ]
    )