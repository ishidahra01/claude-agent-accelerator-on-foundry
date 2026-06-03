from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

import agent_framework as agent_framework_module

from agent_framework_claude import ClaudeAgent


if not hasattr(agent_framework_module, "BaseContextProvider") and hasattr(agent_framework_module, "ContextProvider"):
    agent_framework_module.BaseContextProvider = agent_framework_module.ContextProvider
if not hasattr(agent_framework_module, "ContextProvider") and hasattr(agent_framework_module, "BaseContextProvider"):
    agent_framework_module.ContextProvider = agent_framework_module.BaseContextProvider
if not hasattr(agent_framework_module, "BaseHistoryProvider") and hasattr(agent_framework_module, "HistoryProvider"):
    agent_framework_module.BaseHistoryProvider = agent_framework_module.HistoryProvider
if not hasattr(agent_framework_module, "HistoryProvider") and hasattr(agent_framework_module, "BaseHistoryProvider"):
    agent_framework_module.HistoryProvider = agent_framework_module.BaseHistoryProvider

from azure.ai.agentserver.agentframework import from_agent_framework
from azure.ai.agentserver.agentframework.persistence import InMemoryAgentSessionRepository
from azure.ai.agentserver.core.logger import request_context
from azure.ai.agentserver.core.models.projects import AgentReference
from azure.ai.agentserver.core.server.base import AgentRunContextMiddleware
from azure.ai.agentserver.agentframework.models.agent_framework_output_streaming_converter import (
    AgentFrameworkOutputStreamingConverter,
)
from agent_framework.observability import AgentTelemetryLayer

from src.agent.runtime_contracts import analysis_output_instructions
from src.agent.workspaces import ensure_workspace_root, workspace_instructions


PROJECT_ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger("azure_resource_analyzer")
DEFAULT_PORT = 8088
FOUNDRY_AGENT_NAME = "my-claude-agent"
FOUNDRY_MODEL_PIN_KEYS = [
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
]
VALID_EFFORT_LEVELS = {"low", "medium", "high", "max", "auto"}
BUILTIN_TOOLS = [
    "Agent",
    "Skill",
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "TodoWrite",
]


def _build_system_prompt_append(workspace_root: Path) -> str:
    return "\n\n".join(
        [
            (
                "You are hosted behind Microsoft Agent Framework and Azure AI Agent Server. "
                "Respond in Japanese unless the user explicitly requests another language. "
                "When the request is about Azure resource exports, first use the explore-agent for "
                "large or unfamiliar inputs, then delegate to the security-analyzer, cost-optimizer, "
                "and architecture-reviewer subagents when that improves the analysis. Return a "
                "synthesized final report."
            ),
            workspace_instructions(workspace_root),
            analysis_output_instructions(),
        ]
    )


class ObservableClaudeAgent(AgentTelemetryLayer, ClaudeAgent):
    pass


def _configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _configure_observability_environment() -> None:
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return

    connection_string = os.getenv("APPINSIGHTS_CONNECTION_STRING") or os.getenv("AZURE_MONITOR_CONNECTION_STRING")
    if connection_string:
        os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = connection_string


def _patch_foundry_agent_identity(agent_name: str = FOUNDRY_AGENT_NAME) -> None:
    if getattr(AgentRunContextMiddleware, "_foundry_trace_identity_patched", False):
        return

    original_set_run_context = AgentRunContextMiddleware.set_run_context_to_context_var
    original_build_created_by = AgentFrameworkOutputStreamingConverter._build_created_by

    def ensure_agent_reference(run_context: object) -> None:
        request = getattr(run_context, "request", None)
        if request is None or request.get("agent"):
            return
        request["agent"] = AgentReference(name=agent_name, version="")

    def set_run_context_with_agent_identity(self: AgentRunContextMiddleware, run_context: object) -> None:
        ensure_agent_reference(run_context)
        original_set_run_context(self, run_context)
        ctx = request_context.get() or {}
        ctx["azure.ai.agentserver.agent_name"] = agent_name
        ctx["gen_ai.agent.name"] = ctx.get("gen_ai.agent.name") or agent_name
        ctx["gen_ai.agent.id"] = ctx.get("gen_ai.agent.id") or agent_name
        request_context.set(ctx)

    def build_created_by_with_agent_identity(
        self: AgentFrameworkOutputStreamingConverter,
        author_name: str,
    ) -> dict:
        return original_build_created_by(self, author_name or agent_name)

    AgentRunContextMiddleware.set_run_context_to_context_var = set_run_context_with_agent_identity
    AgentFrameworkOutputStreamingConverter._build_created_by = build_created_by_with_agent_identity
    AgentRunContextMiddleware._foundry_trace_identity_patched = True


def _resolve_port(default: int = DEFAULT_PORT) -> int:
    raw = os.getenv("PORT")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        LOGGER.warning("Invalid PORT=%r. Falling back to %s.", raw, default)
        return default


def _build_claude_process_env() -> dict[str, str]:
    effort_level = _resolve_effort_level()
    env = {
        "CLAUDE_CODE_USE_POWERSHELL_TOOL": os.getenv("CLAUDE_CODE_USE_POWERSHELL_TOOL", "1"),
        "CLAUDE_CODE_USE_FOUNDRY": os.getenv("CLAUDE_CODE_USE_FOUNDRY", "1"),
        "CLAUDE_CODE_EFFORT_LEVEL": effort_level,
    }

    optional_keys = [
        "ANTHROPIC_FOUNDRY_RESOURCE",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_FOUNDRY_API_KEY",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_MODEL",
    ]
    for key in optional_keys:
        value = os.getenv(key)
        if value:
            env[key] = value

    return env


def _resolve_effort_level(default: str = "high") -> str:
    raw = os.getenv("CLAUDE_EFFORT") or os.getenv("CLAUDE_CODE_EFFORT_LEVEL") or default
    normalized = raw.strip().lower()

    aliases = {
        "middle": "medium",
    }
    normalized = aliases.get(normalized, normalized)

    if normalized not in VALID_EFFORT_LEVELS:
        LOGGER.warning(
            "Invalid effort level %r. Falling back to %s. Valid values are: %s.",
            raw,
            default,
            ", ".join(sorted(VALID_EFFORT_LEVELS)),
        )
        return default

    return normalized


def _validate_foundry_configuration() -> None:
    use_foundry = os.getenv("CLAUDE_CODE_USE_FOUNDRY", "1").strip().lower()
    if use_foundry not in {"1", "true", "yes", "on"}:
        LOGGER.warning(
            "CLAUDE_CODE_USE_FOUNDRY is not enabled. This project is intended to run against Microsoft Foundry."
        )

    resource = os.getenv("ANTHROPIC_FOUNDRY_RESOURCE")
    base_url = os.getenv("ANTHROPIC_FOUNDRY_BASE_URL")
    if not resource and not base_url:
        raise RuntimeError(
            "Microsoft Foundry is not configured. Set ANTHROPIC_FOUNDRY_RESOURCE or "
            "ANTHROPIC_FOUNDRY_BASE_URL before starting the server."
        )

    auth_mode = "API key" if os.getenv("ANTHROPIC_FOUNDRY_API_KEY") else "Entra ID"
    target = base_url or resource or "<unknown>"
    LOGGER.info("Microsoft Foundry target: %s", target)
    LOGGER.info("Microsoft Foundry authentication mode: %s", auth_mode)

    missing_model_pins = [key for key in FOUNDRY_MODEL_PIN_KEYS if not os.getenv(key)]
    if missing_model_pins:
        LOGGER.warning(
            "Foundry model version pinning is incomplete. Set %s to deployment names to avoid breakage on future Claude releases.",
            ", ".join(missing_model_pins),
        )


def _build_agent() -> ClaudeAgent:
    effort_level = _resolve_effort_level()
    workspace_root = ensure_workspace_root(PROJECT_ROOT)
    default_options = {
        "cwd": str(PROJECT_ROOT),
        "setting_sources": ["project"],
        "system_prompt": {
            "type": "preset",
            "preset": "claude_code",
            "append": _build_system_prompt_append(workspace_root),
        },
        "allowed_tools": BUILTIN_TOOLS,
        "permission_mode": os.getenv("CLAUDE_PERMISSION_MODE", "dontAsk"),
        "model": os.getenv("CLAUDE_MODEL", "sonnet"),
        "max_turns": int(os.getenv("CLAUDE_MAX_TURNS", "12")),
        "effort": effort_level,
        "env": _build_claude_process_env(),
    }

    return ObservableClaudeAgent(
        name="azure-resource-analyzer",
        description="Claude Agent SDK based Azure resource analyzer hosted through Microsoft Agent Framework.",
        tools=BUILTIN_TOOLS,
        default_options=default_options,
    )


def main() -> None:
    load_dotenv(override=False)
    _configure_observability_environment()
    _configure_logging()
    _validate_foundry_configuration()

    port = _resolve_port()
    agent = _build_agent()
    _patch_foundry_agent_identity()

    LOGGER.info("Starting azure-resource-analyzer on http://localhost:%s/responses", port)
    from_agent_framework(agent, session_repository=InMemoryAgentSessionRepository()).run(port=port)


if __name__ == "__main__":
    main()