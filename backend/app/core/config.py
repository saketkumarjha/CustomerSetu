from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_vision_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimension: int = 512

    # Gemini
    gemini_api_key: str = ""

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_storage_bucket: str = "complaint-images"

    # Tesseract
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # Auth
    api_key: str

    # Rate Limiting
    rate_limit_per_minute: int = 10

    # Duplicate Detection
    duplicate_threshold: float = 0.92

    # App
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    max_file_size_mb: int = 10

    # Notification gateways (leave blank to use simulation in prototype)
    email_gateway_url: str = ""
    email_from_address: str = "customercare@unionbankofindia.com"
    sms_gateway_url: str = ""
    sms_api_key: str = ""

    # Response templates
    tier_templates_path: str = "app/templates/tier_responses/"

    # Knowledge base enrichment
    enable_auto_kb_enrichment: bool = True
    kb_enrichment_delay_hours: int = 24

    # KB enrichment quality thresholds
    kb_auto_approve_threshold: float = 0.95   # auto-add to KB without admin review
    kb_review_threshold:       float = 0.70   # minimum quality to enter queue
    kb_min_resolution_length:  int   = 50     # chars
    kb_max_resolution_length:  int   = 5000   # chars
    kb_max_escalations:        int   = 3      # skip if more than N escalations
    kb_queue_retention_days:   int   = 90     # days to keep processed queue rows
    kb_notify_queue_threshold: int   = 50     # alert when pending queue exceeds N

    # Notification retries
    notification_retry_count: int = 3
    notification_timeout_seconds: int = 10

    # Agent queue
    agent_max_workload: int = 5
    agent_queue_refresh_interval: int = 30   # seconds
    agent_notification_channels: list = ["email", "slack", "push"]

    # Auto-Escalation (Route 3)
    max_escalation_iterations: int = 5       # hard limit on escalation hops
    max_escalation_tier: int = 5             # Tier 5 = RBI Ombudsman (external)
    escalation_cache_ttl_seconds: int = 30   # anti-rapid-fire window per tier
    min_escalation_interval_seconds: int = 10
    enable_escalation_loop_detection: bool = True

    # Tier → agent mapping (overridable via env as JSON string)
    tier_agent_mapping: dict = {
        0: ["Rishi", "Alok", "Shaunak"],
        1: ["Saket", "Prince"],
        2: ["Shubham"],
        3: ["Shubham Kumar"],
        4: ["Sarthak"],
    }

    # Agent specialisation map
    agent_specialization: dict = {
        "Rishi": ["UPI", "ATM", "Cards"],
        "Alok": ["General Banking", "Savings Account"],
        "Shaunak": ["Internet Banking", "Mobile Banking"],
        "Saket": ["Branch Services", "Locker", "KYC"],
        "Prince": ["Home Loan", "Personal Loan"],
        "Shubham": ["Business Loan", "Insurance"],
        "Shubham Kumar": ["Regional Compliance", "Mis-selling"],
        "Sarthak": ["Nodal Office", "Fraud", "RBI Escalation"],
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()