from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger("azure_resource_analyzer.optimization")


@dataclass(frozen=True)
class AgentOptimizerConfig:
    instructions: str
    model: str | None
    source: str
    skill_count: int
    enabled: bool


def load_agent_optimizer_config(config_dir: Path) -> AgentOptimizerConfig:
    try:
        from azure.ai.agentserver.optimization import load_config
    except ModuleNotFoundError:
        LOGGER.warning(
            "Agent Optimizer package is not installed. Install azure-ai-agentserver-optimization "
            "to enable optimizer candidates."
        )
        return AgentOptimizerConfig(
            instructions="",
            model=None,
            source="package-missing",
            skill_count=0,
            enabled=False,
        )

    config = load_config(config_dir=config_dir)
    instructions = _compose_instructions(config)
    model = _string_or_none(getattr(config, "model", None))
    source = _string_or_none(getattr(config, "source", None)) or "unknown"
    skill_count = _resolve_skill_count(config)

    return AgentOptimizerConfig(
        instructions=instructions,
        model=model,
        source=source,
        skill_count=skill_count,
        enabled=True,
    )


def _compose_instructions(config: Any) -> str:
    compose = getattr(config, "compose_instructions", None)
    if callable(compose):
        value = compose()
    else:
        value = getattr(config, "instructions", "")

    if value is None:
        return ""
    return str(value).strip()


def _resolve_skill_count(config: Any) -> int:
    skills = getattr(config, "skills", None)
    if skills:
        return len(skills)

    skills_dir = _string_or_none(getattr(config, "skills_dir", None))
    if not skills_dir:
        return 0

    path = Path(skills_dir)
    if not path.exists():
        return 0

    return sum(1 for skill_file in path.glob("*/SKILL.md") if skill_file.is_file())


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None