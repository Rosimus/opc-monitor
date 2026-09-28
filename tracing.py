"""
Инициализация OpenTelemetry для distributed tracing.

Экспортирует трейсы в Jaeger через OTLP (gRPC).
Автоматически инструментирует Flask, SQLAlchemy и requests.
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


def init_tracing(app, engine=None):
    """
    Инициализирует OpenTelemetry и подключает экспорт в Jaeger.

    Args:
        app: Flask-приложение.
        engine: SQLAlchemy engine для инструментирования БД (опционально).
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    service = os.environ.get("OTEL_SERVICE_NAME", "opc-monitor-web")

    if not endpoint:
        logger.warning("OTEL_EXPORTER_OTLP_ENDPOINT не задан, трейсинг отключён")
        return

    try:
        resource = Resource.create({SERVICE_NAME: service})
        provider = TracerProvider(resource=resource)

        # OTLP gRPC экспортёр (Jaeger принимает OTLP)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        # Авто-инструментирование
        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()
        if engine is not None:
            SQLAlchemyInstrumentor().instrument(engine=engine)

        logger.info(
            f"✅ OpenTelemetry инициализирован: service={service}, endpoint={endpoint}"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации OpenTelemetry: {e}")