"""Environment-derived settings. Fails fast on startup if required config is missing."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT / ".env")
WORKSPACE_ROOT = BACKEND_ROOT / "workspace"
EVIDENCE_ROOT = WORKSPACE_ROOT / "evidence"
POLICY_ROOT = WORKSPACE_ROOT / "policy"
POLICY_ACTIVE_PATH = POLICY_ROOT / "credit_policy_active.yaml"
POLICY_DRAFTS_ROOT = POLICY_ROOT / "drafts"
POLICY_HISTORY_ROOT = POLICY_ROOT / "history"
DECISIONS_ROOT = WORKSPACE_ROOT / "decisions"
APPLICANTS_PATH = WORKSPACE_ROOT / "applicants.json"

OPENAI_MODEL = os.environ.get("CREDIT_GENIE_MODEL", "gpt-5.1")


def require_api_key() -> str:
    """Return OPENAI_API_KEY or raise if it isn't set — no silent fallback."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it before starting the server: "
            "export OPENAI_API_KEY=sk-..."
        )
    return key
