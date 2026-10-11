from dataclasses import dataclass, field
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]

def _load_dotenv(path=ROOT / '.env'):
    """Minimal .env reader so local runs pick up secrets without an extra dependency.
    Real environment variables (Replit Secrets) always win. Tests set PROMOPILOT_SKIP_DOTENV."""
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key.strip() and value.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")

if not os.getenv('PROMOPILOT_SKIP_DOTENV'):
    _load_dotenv()

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "data" / "promopilot.sqlite3"}')
    provider: str = os.getenv('AI_PROVIDER', 'openai')
    gemini_model: str = os.getenv('GEMINI_MODEL', 'gemini-3.8-flash')
    # Model IDs and prices checked on developers.openai.com/api/docs/pricing (2026-10-07).
    openai_model: str = os.getenv('OPENAI_MODEL', 'gpt-6-luna')
    openai_review_model: str = os.getenv('OPENAI_REVIEW_MODEL', 'gpt-6.1-sol')
    daily_ai_limit: float = float(os.getenv('DAILY_AI_LIMIT_USD', '0.50'))  # .env / Replit Secrets raise it
    demo_mode: bool = os.getenv('DEMO_MODE', 'true').lower() == 'true'
    # Judges may run the live agent inside the daily cap; false requires owner login for paid calls.
    public_live: bool = os.getenv('PUBLIC_LIVE_AI', 'true').lower() == 'true'
    admin_token: str = os.getenv('ADMIN_TOKEN', '')
    session_secret: str = os.getenv('SESSION_SECRET', '')
    upload_limit: int = 8 * 1024 * 1024
    max_calls: int = 6
    agent_max_steps: int = int(os.getenv('AGENT_MAX_STEPS', '18'))
    api_rate_limit_per_hour: int = int(os.getenv('API_RATE_LIMIT_PER_HOUR', '400'))
    # New workspaces per client address per hour (owner's decision: 500). Behind a proxy every visitor shares one
    # address unless FORWARDED_ALLOW_IPS=* is set, so keep that set too.
    workspace_create_limit_per_hour: int = field(default_factory=lambda: int(os.getenv('WORKSPACE_CREATE_LIMIT_PER_HOUR', '500')))

    def __post_init__(self):
        if self.api_rate_limit_per_hour < 1:
            raise ValueError('API_RATE_LIMIT_PER_HOUR must be a positive integer')
        if self.workspace_create_limit_per_hour < 1:
            raise ValueError('WORKSPACE_CREATE_LIMIT_PER_HOUR must be a positive integer')

settings = Settings()
