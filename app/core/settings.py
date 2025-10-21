# app/core/settings.py
# Best practice: centralize configuration in one place using Pydantic BaseSettings.
# This ensures type-checked, documented, and testable config loading.
from __future__ import annotations
from pathlib import Path
from typing import Optional

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict  # <- v2 Location
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # project root: app/core -> app -> ROOT

def _load_env_files() -> None:
    """
    Best practice:
    - Load `.env` from the project root by default.
    - Optionally fall back to `.env.txt` to stay compatible with your current layout.
    - Avoid cwd-dependent relative paths; use absolute paths based on ROOT.
    - Never fail silently—log a short note if not found.
    """
    

    env_candidates = [ROOT / ".env", ROOT / ".env.txt"]
    loaded_any = False
    for p in env_candidates:
        if p.exists():
            load_dotenv(dotenv_path=p, override=False)  # don't override real envs
            loaded_any = True
            break  # prefer the first one found (.env over .env.txt)

    if not loaded_any:
        # Optional: keep this quiet in prod; during dev it’s useful.
        # print(f"[settings] No .env found at {env_candidates}")
        pass

# Attempt to load env files before reading settings
try:
    _load_env_files()
except Exception as e:
    # Best practice: avoid hard crash on config load path; you’ll fail below if required vars are missing.
    # print(f"[settings] Env load warning: {e}")
    pass

class Settings(BaseSettings):
    # Document required vars. Let’s fail fast if missing (no default).
    OPENAI_API_KEY: str = Field(..., description="Project-scoped OpenAI API key starting with 'sk-'")
    OPENAI_ORG_ID: Optional[str] = None     # Optional
    OPENAI_PROJECT: Optional[str] = None    # Optional

    # ---- Tunables (env-overridable) ----
    OPENAI_MODEL: str = Field("gpt-4o-mini", description="Default chat model")
    OPENAI_TIMEOUT_S: int = Field(30, description="HTTP timeout in seconds")

    # App paths (optional, but helpful to standardize)
    ROOT: Path = ROOT
    BUCKET: Path = Field(default=ROOT / "bucket")
    OUT: Path = Field(default=ROOT / "out")
    STATIC: Path = Field(default=ROOT / "static")
    TASK_TMP_ROOT: Path = Field(default=Path("/tmp/tasks"))

    # Pydantic v2 settings configuration (replaces class Config)
    model_config = SettingsConfigDict(
        case_sensitive=True,  # Best practice: avoid surprises on env names
        extra="ignore",       # Ignore unknown env vars instead of erroring
    )

# Instantiate once and reuse
try:
    settings = Settings()
except ValidationError as e:
    # Best practice: fail fast with a clear message when required secrets are missing.
    # In production, let the process crash here so Orchestrator/K8s restarts it.
    raise RuntimeError(
        "Missing required environment variables. "
        "Ensure OPENAI_API_KEY is set via system env or .env."
    ) from e