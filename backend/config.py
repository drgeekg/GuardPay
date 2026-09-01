"""
GuardPay backend configuration.
All values loaded from environment variables (.env file or real env).
Defaults are development-safe and documented in .env.example.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Razorpay test-mode credentials
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    razorpay_webhook_secret: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Anthropic Claude API key (dossier generation only)
    claude_api_key: str = os.getenv("CLAUDE_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

    # NVIDIA NIM API key (OpenAI-compatible cloud inference)
    # Get from https://build.nvidia.com/
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    nvidia_base_url: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    nvidia_model: str = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

    # Cloud Ollama / Remote LLM settings (with API Key & custom URL)
    ollama_cloud_base_url: str = os.getenv("OLLAMA_CLOUD_BASE_URL", "") or os.getenv("OLLAMA_HOST", "")
    ollama_cloud_api_key: str = os.getenv("OLLAMA_CLOUD_API_KEY", "") or os.getenv("OLLAMA_API_KEY", "")
    ollama_cloud_model: str = os.getenv("OLLAMA_CLOUD_MODEL", "") or os.getenv("OLLAMA_MODEL", "gpt-oss:120b")

    # Local Ollama settings (local Ollama instance)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3")

    # Server
    backend_host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))

    # Velocity engine thresholds (tunable per merchant)
    velocity_txn_per_card_per_min: int = int(
        os.getenv("VELOCITY_TXN_PER_CARD_PER_MIN", "10")
    )
    velocity_bin_cluster_threshold: int = int(
        os.getenv("VELOCITY_BIN_CLUSTER_THRESHOLD", "5")
    )
    velocity_subnet_cluster_threshold: int = int(
        os.getenv("VELOCITY_SUBNET_CLUSTER_THRESHOLD", "8")
    )
    velocity_window_seconds: int = int(
        os.getenv("VELOCITY_WINDOW_SECONDS", "60")
    )


settings = Settings()
