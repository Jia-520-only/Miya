"""
OpenTelemetry tracing setup for MIYA.
Provides a no-op fallback if OpenTelemetry is not installed.
"""

import logging
import os

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import SpanKind, Status, StatusCode

    _OPENTELEMETRY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OPENTELEMETRY_AVAILABLE = False
    trace = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    OTLPSpanExporter = None  # type: ignore
    Resource = None  # type: ignore
    SpanKind = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore

# Global tracer
_tracer = None


def init_tracing(service_name="miya", service_version="1.0.0"):
    """
    Initialize OpenTelemetry tracing if available.
    """
    global _tracer
    if not _OPENTELEMETRY_AVAILABLE:
        logger.warning("OpenTelemetry not available, tracing disabled")
        return None

    # Set up resource
    resource = Resource(
        attributes={
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": os.getenv("MIYA_ENV", "development"),
        }
    )

    # Set up tracer provider
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # Set up exporter (OTLP by default, can be changed via env)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    span_processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(span_processor)

    # Get tracer
    _tracer = trace.get_tracer(__name__)

    logger.info(f"OpenTelemetry tracing initialized for {service_name}")
    return _tracer


def get_tracer():
    """
    Get the global tracer.
    Returns a no-op tracer if OpenTelemetry is not available.
    """
    global _tracer
    if _tracer is None and _OPENTELEMETRY_AVAILABLE:
        # Initialize with defaults if not already done
        init_tracing()
    return _tracer


def trace_async_function(func):
    """
    Decorator to trace an async function.
    If tracing is not available, returns the original function.
    """
    if not _OPENTELEMETRY_AVAILABLE:
        return func

    async def wrapper(*args, **kwargs):
        tracer = get_tracer()
        if tracer is None:
            return await func(*args, **kwargs)
        with tracer.start_as_current_span(func.__name__, kind=SpanKind.INTERNAL) as span:
            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    return wrapper


def trace_function(func):
    """
    Decorator to trace a synchronous function.
    If tracing is not available, returns the original function.
    """
    if not _OPENTELEMETRY_AVAILABLE:
        return func

    def wrapper(*args, **kwargs):
        tracer = get_tracer()
        if tracer is None:
            return func(*args, **kwargs)
        with tracer.start_as_current_span(func.__name__, kind=SpanKind.INTERNAL) as span:
            try:
                result = func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    return wrapper
