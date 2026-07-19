import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _secret(key: str, default: str = "") -> str:
    """Read from env first, then Streamlit secrets (for Streamlit Cloud deployment)."""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LOG_DIR = Path(os.getenv("LOG_DIR", str(DATA_DIR / "logs")))
LOG_DIR.mkdir(exist_ok=True)

DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "productivity.db"))

# LLM — Groq (OpenAI-compatible endpoint)
GROQ_API_KEY = _secret("GROQ_API_KEY")
LLM_MODEL = _secret("LLM_MODEL") or "llama-3.3-70b-versatile"
LLM_BASE_URL = "https://api.groq.com/openai/v1"

# Use whichever key is set
API_KEY = GROQ_API_KEY or _secret("GOOGLE_API_KEY")

# Agent limits
MAX_AGENT_STEPS = 8
MAX_TOOL_RETRIES = 2
TOOL_TIMEOUT_SECONDS = 30

# Tools that require human approval before execution
APPROVAL_REQUIRED_TOOLS = {
    "create_task",
    "update_task",
    "complete_task",
    "delete_task",
    "save_note",
}

WRITE_OPERATIONS = APPROVAL_REQUIRED_TOOLS
