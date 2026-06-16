from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


LOGGER = logging.getLogger("azure_resource_analyzer.observability")
TRACER_NAME = "claude_agent_accelerator.part_b"
OUTPUT_SCHEMA_NAME = "azure-analysis-output-v1"
PART_NAME = "part-b-observe"
MAX_ATTRIBUTE_STRING_LENGTH = 256

AttributeValue = str | bool | int | float


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_flag_or_none(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_hosted_runtime() -> bool:
    return any(
        os.getenv(name)
        for name in (
            "FOUNDRY_AGENT_NAME",
            "FOUNDRY_AGENT_VERSION",
            "FOUNDRY_PROJECT_ENDPOINT",
            "AZURE_AI_PROJECT_ENDPOINT",
        )
    )


def _normalize_attribute_value(value: Any) -> AttributeValue | None:
    if value is None:
        return None
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        return value[:MAX_ATTRIBUTE_STRING_LENGTH]
    return str(value)[:MAX_ATTRIBUTE_STRING_LENGTH]


def _set_attributes(span: trace.Span, attributes: Mapping[str, Any]) -> None:
    for key, value in attributes.items():
        normalized = _normalize_attribute_value(value)
        if normalized is not None:
            span.set_attribute(key, normalized)


@dataclass(frozen=True)
class ObservabilityContext:
    service_name: str
    agent_name: str
    agent_version: str
    workspace_root: Path

    def base_attributes(self) -> dict[str, AttributeValue]:
        return {
            "service.name": self.service_name,
            "gen_ai.agent.name": self.agent_name,
            "gen_ai.agent.version": self.agent_version,
            "azure.accelerator.part": PART_NAME,
            "azure.accelerator.schema": OUTPUT_SCHEMA_NAME,
            "azure.accelerator.workspace_root": str(self.workspace_root),
            "azure.accelerator.hosted": _is_hosted_runtime(),
            "azure.accelerator.app_insights.configured": bool(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")),
            "azure.accelerator.genai_tracing.enabled": _env_flag("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"),
        }

    @property
    def tracer(self) -> trace.Tracer:
        return trace.get_tracer(TRACER_NAME)

    @contextmanager
    def start_span(self, name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[trace.Span]:
        combined_attributes: dict[str, Any] = dict(self.base_attributes())
        if attributes:
            combined_attributes.update(attributes)

        with self.tracer.start_as_current_span(name) as span:
            _set_attributes(span, combined_attributes)
            try:
                yield span
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise

    def record_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> None:
        span = trace.get_current_span()
        if not span or not span.is_recording():
            LOGGER.debug("Skipping observability event %s because no recording span is active.", name)
            return

        safe_attributes: dict[str, AttributeValue] = {}
        for key, value in (attributes or {}).items():
            normalized = _normalize_attribute_value(value)
            if normalized is not None:
                safe_attributes[key] = normalized
        span.add_event(name, safe_attributes)


def create_observability(agent_name: str, agent_version: str, workspace_root: Path) -> ObservabilityContext:
    return ObservabilityContext(
        service_name="azure-resource-analyzer",
        agent_name=agent_name,
        agent_version=agent_version,
        workspace_root=workspace_root,
    )


def configure_agent_framework_observability(*, agent_name: str, agent_version: str) -> None:
    instrumentation_enabled = _env_flag_or_none("ENABLE_INSTRUMENTATION")
    if instrumentation_enabled is False:
        LOGGER.info("Agent Framework instrumentation is disabled by ENABLE_INSTRUMENTATION=false.")
        return

    os.environ.setdefault("OTEL_SERVICE_NAME", "azure-resource-analyzer")
    if agent_version:
        os.environ.setdefault("OTEL_SERVICE_VERSION", agent_version)

    from agent_framework.observability import configure_otel_providers, create_resource, enable_instrumentation

    enable_sensitive_data = _env_flag_or_none("ENABLE_SENSITIVE_DATA")
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if connection_string and not _env_flag("DISABLE_AZURE_MONITOR_EXPORTER"):
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "APPLICATIONINSIGHTS_CONNECTION_STRING is set, but azure-monitor-opentelemetry is not installed. "
                "Install azure-monitor-opentelemetry or set DISABLE_AZURE_MONITOR_EXPORTER=true."
            ) from exc

        resource = create_resource(
            service_name="azure-resource-analyzer",
            service_version=agent_version or None,
            **{
                "gen_ai.agent.name": agent_name,
                "gen_ai.agent.version": agent_version,
                "azure.accelerator.part": PART_NAME,
                "azure.accelerator.schema": OUTPUT_SCHEMA_NAME,
            },
        )
        configure_azure_monitor(connection_string=connection_string, resource=resource)
        enable_instrumentation(enable_sensitive_data=enable_sensitive_data, force=True)
        LOGGER.info("Configured Agent Framework tracing with Azure Monitor exporter.")
        return

    configure_otel_providers(
        enable_sensitive_data=enable_sensitive_data,
        enable_console_exporters=_env_flag_or_none("ENABLE_CONSOLE_EXPORTERS"),
    )
    LOGGER.info("Configured Agent Framework tracing with OpenTelemetry environment exporters.")


def trace_server_startup(observability: ObservabilityContext, *, agent_id: str, port: int) -> None:
    with observability.start_span(
        "hosted_agent.server.startup",
        {
            "server.port": port,
            "gen_ai.agent.id": agent_id,
        },
    ) as span:
        span.add_event("server.starting")
        LOGGER.info(
            "Observability context initialized for agent=%s version=%s workspace=%s app_insights=%s genai_tracing=%s",
            observability.agent_name,
            observability.agent_version or "<none>",
            observability.workspace_root,
            observability.base_attributes()["azure.accelerator.app_insights.configured"],
            observability.base_attributes()["azure.accelerator.genai_tracing.enabled"],
        )
        span.add_event("server.startup_context_ready")


def record_hook_event(
    observability: ObservabilityContext,
    *,
    hook_name: str,
    phase: str,
    attributes: Mapping[str, Any] | None = None,
) -> None:
    event_attributes: dict[str, Any] = {
        "azure.accelerator.hook.name": hook_name,
        "azure.accelerator.hook.phase": phase,
    }
    if attributes:
        event_attributes.update(attributes)
    observability.record_event("claude_sdk.hook", event_attributes)
