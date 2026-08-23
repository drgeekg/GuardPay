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

    # Anthropic Claude API key (dossier generation only)
    claude_api_key: str = os.getenv("CLAUDE_API_KEY", "")

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
