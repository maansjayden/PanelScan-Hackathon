"""Project environment loading for local development."""

from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:
    """Load the repository-level .env file without replacing shell variables."""
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env, override=False)
