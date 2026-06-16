from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from agent_framework_claude import ClaudeAgent
from agent_framework_foundry_hosting import ResponsesHostServer

from src.agent.observability.tracing import (
    configure_agent_framework_observability,
    create_observability,
    trace_server_startup,
)
from src.agent.optimization import AgentOptimizerConfig, load_agent_optimizer_config
from src.agent.runtime_contracts import analysis_output_instructions
from src.agent.workspaces import ensure_workspace_root, workspace_instructions


PROJECT_ROOT = Path(__file__).resolve().parent
OPTIMIZER_CONFIG_DIR = PROJECT_ROOT / ".claude" / "optimizer_configs"
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


def _default_agent_instructions() -> str:
    return (
        "You are hosted behind Microsoft Agent Framework and Azure AI Agent Server. "
        "Respond in Japanese unless the user explicitly requests another language. "
        "When the request is about Azure resource exports, first use the explore-agent for "
        "large or unfamiliar inputs, then delegate to the security-analyzer, cost-optimizer, "
        "and architecture-reviewer subagents when that improves the analysis. Return a "
        "synthesized final report."
    )


def _build_system_prompt_append(workspace_root: Path, optimizer_config: AgentOptimizerConfig) -> str:
    agent_instructions = optimizer_config.instructions or _default_agent_instructions()
    return "\n\n".join(
        [
            agent_instructions,
            workspace_instructions(workspace_root),
            analysis_output_instructions(),
        ]
    )


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


def _resolve_foundry_agent_name() -> str:
    return os.getenv("FOUNDRY_AGENT_NAME") or os.getenv("CLAUDE_HOSTED_AGENT_NAME") or FOUNDRY_AGENT_NAME


def _resolve_foundry_agent_version() -> str:
    return os.getenv("FOUNDRY_AGENT_VERSION") or os.getenv("CLAUDE_HOSTED_AGENT_VERSION", "")


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


def _build_agent(workspace_root: Path, optimizer_config: AgentOptimizerConfig) -> ClaudeAgent:
    effort_level = _resolve_effort_level()
    default_options = {
        "cwd": str(PROJECT_ROOT),
        "setting_sources": ["project"],
        "system_prompt": {
            "type": "preset",
            "preset": "claude_code",
            "append": _build_system_prompt_append(workspace_root, optimizer_config),
        },
        "allowed_tools": BUILTIN_TOOLS,
        "permission_mode": os.getenv("CLAUDE_PERMISSION_MODE", "dontAsk"),
        "model": os.getenv("CLAUDE_MODEL", "sonnet"),
        "max_turns": int(os.getenv("CLAUDE_MAX_TURNS", "12")),
        "effort": effort_level,
        "env": _build_claude_process_env(),
    }

    return ClaudeAgent(
        id=f"{_resolve_foundry_agent_name()}:{_resolve_foundry_agent_version()}"
        if _resolve_foundry_agent_version()
        else _resolve_foundry_agent_name(),
        name=_resolve_foundry_agent_name(),
        description="Claude Agent SDK based Azure resource analyzer hosted through Microsoft Agent Framework.",
        tools=BUILTIN_TOOLS,
        default_options=default_options,
    )


async def main() -> None:
    load_dotenv(override=False)
    _configure_observability_environment()
    _configure_logging()
    configure_agent_framework_observability(
        agent_name=_resolve_foundry_agent_name(),
        agent_version=_resolve_foundry_agent_version(),
    )
    _validate_foundry_configuration()
    optimizer_config = load_agent_optimizer_config(OPTIMIZER_CONFIG_DIR)
    LOGGER.info(
        "Agent optimizer config source=%s model=%s skills=%s enabled=%s",
        optimizer_config.source,
        optimizer_config.model or "<default>",
        optimizer_config.skill_count,
        optimizer_config.enabled,
    )

    workspace_root = ensure_workspace_root(PROJECT_ROOT)
    agent = _build_agent(workspace_root, optimizer_config)
    port = _resolve_port()
    observability = create_observability(
        agent_name=_resolve_foundry_agent_name(),
        agent_version=_resolve_foundry_agent_version(),
        workspace_root=workspace_root,
    )
    trace_server_startup(observability, agent_id=agent.id, port=port)

    LOGGER.info("Starting azure-resource-analyzer with agent id %s", agent.id)
    server = ResponsesHostServer(agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())