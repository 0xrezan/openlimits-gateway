from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from src.settings import Settings


def configure_tracing(app: FastAPI, settings: Settings) -> None:
    if not settings.tracing_enabled:
        return
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tracer_provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)
