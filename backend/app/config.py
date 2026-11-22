from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config comes from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Local dev uses a SQLite file (no Docker needed). Production uses Neon Postgres:
    # postgresql+psycopg://user:pass@host/db
    database_url: str = "sqlite:///./ledgerwise.db"
    frontend_origin: str = "http://localhost:3000"

    # Free LLM providers, tried in this order. Each speaks the OpenAI chat API.
    # If one fails or hits its limit, the next one answers. If all fail -> human handoff.
    llm_providers: str = "groq,cloudflare,opencode,axforge,gonka"

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"

    opencode_api_key: str = ""
    opencode_base_url: str = "https://opencode.ai/zen/v1"
    opencode_model: str = ""

    axforge_api_key: str = ""
    axforge_base_url: str = ""  # copy from console.axforge.ai
    axforge_model: str = ""

    gonka_api_key: str = ""
    gonka_base_url: str = ""  # copy from app.gonkabroker.com
    gonka_model: str = ""

    # Quick filter: a fast, cheap model (Gemini Flash Lite on Google AI Studio, free tier).
    # Falls back to the main chain when not configured.
    quick_filter_providers: str = "gemini:gemini-3.5-flash-lite,cloudflare:@cf/openai/gpt-oss-20b"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-2.5-flash-lite"

    # One model pool per job. Entry = "provider" (its default model) or "provider:model".
    # Calls rotate inside a pool. An empty pool falls back to LLM_PROVIDERS.
    # fast: many small calls (search steps, pulling brands out of results)
    llm_fast: str = (
        "groq:openai/gpt-oss-20b,gemini:gemini-3.5-flash-lite,cloudflare:@cf/openai/gpt-oss-20b"
    )
    # read: long web pages and exact quotes (researcher, contact finder)
    llm_read: str = "gemini:gemini-2.5-flash,cloudflare:@cf/openai/gpt-oss-120b"
    # judge: decisions that matter (qualifier, reply classifier, thread report)
    llm_judge: str = "groq:openai/gpt-oss-120b,cloudflare:@cf/openai/gpt-oss-120b"
    # write: emails and replies (first email, follow-ups, replies, AI rewrite)
    llm_write: str = "groq:openai/gpt-oss-120b,cloudflare:@cf/openai/gpt-oss-120b"
    # check: the fact checker, a different model family from the writer
    llm_check: str = "gemini:gemini-2.5-flash,groq:qwen/qwen3.8-27b"

    # Cloudflare Workers AI (free daily allowance), an OpenAI-compatible fallback in the chain.
    cloudflare_account_id: str = ""
    cloudflare_api_key: str = ""
    cloudflare_model: str = "@cf/openai/gpt-oss-120b"

    @property
    def cloudflare_base_url(self) -> str:
        if not self.cloudflare_account_id:
            return ""
        return f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_account_id}/ai/v1"

    # Research tools (all have free tiers; every tool works without its key except Tavily)
    tavily_api_key: str = ""
    jina_api_key: str = ""
    hunter_api_key: str = ""
    # SEC asks automated clients to identify themselves. Use a generic project address.
    sec_user_agent: str = "LedgerwiseSDR-demo/0.1 research@ledgerwise-demo.test"
    exa_api_key: str = ""
    firecrawl_api_key: str = ""
    resend_api_key: str = ""
    resend_from: str = (
        "Ledgerwise <onboarding@resend.dev>"  # Resend's sender before a domain is verified
    )
    # Free receiving domain from Resend (Emails > Receiving), e.g. abc123.resend.app.
    # Replies go to reply+<thread id>@<this domain> and come back via the webhook.
    resend_inbound_domain: str = ""
    webhook_secret: str = ""  # appended as ?token= to the webhook URL in Resend
    secret_key: str = "dev-secret-change-me"  # signs unsubscribe links
    public_api_url: str = "http://localhost:3000"  # where unsubscribe links point
    sender_name: str = "Sam from Ledgerwise"
    postal_address: str = "Ledgerwise, 100 Demo Street, Austin, TX 78701"
    daily_send_cap: int = 50
    run_followup_timer: bool = True
    calcom_api_key: str = ""

    # Rule: outbound email only ever goes to this demo inbox, never to the real prospect.
    demo_inbox: str = "delivered@resend.dev"  # Resend's test inbox: accepts mail, reaches nobody
    # Below this confidence the reply agent hands the thread to a human.
    min_confidence: float = 0.7


settings = Settings()
