from __future__ import annotations

import os
from pathlib import Path


DEFAULT_WORKSPACE_ROOT_NAME = "work"


def resolve_workspace_root(project_root: Path) -> Path:
    configured = os.getenv("CLAUDE_WORKSPACE_ROOT")
    if configured:
        expanded = os.path.expandvars(configured)
        path = Path(expanded).expanduser()
        return path if path.is_absolute() else project_root / path

    return project_root / DEFAULT_WORKSPACE_ROOT_NAME


def ensure_workspace_root(project_root: Path) -> Path:
    workspace_root = resolve_workspace_root(project_root)
    workspace_root.mkdir(parents=True, exist_ok=True)
    return workspace_root


def workspace_instructions(workspace_root: Path) -> str:
    return f"""
Use the hosted-agent workspace root for generated artifacts and intermediate analysis files:
{workspace_root}

When a request includes a session, thread, or run identifier, keep request-specific files in a
subdirectory under that root. Treat this directory as the persistent filesystem boundary for the
Hosted Agent demo: normalized exports, intermediate summaries, and final reports belong there.
Do not write secrets or credential material to the workspace.
""".strip()