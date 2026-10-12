"""
Centralized configuration for the Harness Kit API.
Loads from environment variables / .env file.
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """All backend configuration, with local-dev defaults."""

    # Google Cloud
    google_cloud_project: str = "harness-kit-33919"
    google_cloud_region: str = "us-central1"
    google_application_credentials: Optional[str] = "gcp-key.json"

    # BigQuery
    bq_dataset: str = "harness_analytics"
    bq_runs_table: str = "runs"
    bq_turns_table: str = "turns"
    bq_tool_calls_table: str = "tool_calls"
    bq_judgments_table: str = "judgments"

    # Firestore
    firestore_collection: str = "runs"

    # API
    api_port: int = 8080
    cors_origins: str = "*"

    # Engine mode: "mock" uses mock_runner, "live" calls harness_core
    engine_mode: str = "mock"

    # SQLite fallback path (relative to working directory)
    sqlite_db_path: str = "harness_analytics.db"

    # Agent defaults
    default_model: str = "gemini-2.5-flash"
    default_context_tier: str = "T4"
    default_budget_cap: int = 32768

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton
settings = Settings()
