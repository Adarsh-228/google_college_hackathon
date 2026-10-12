"""Factory to instantiate LLM providers based on environment and configuration."""

import logging
from typing import Optional

from packages.harness_core.config.settings import EngineConfig
from packages.harness_core.contracts.enums import ProviderType
from packages.harness_core.exceptions.errors import ConfigurationError
from packages.harness_core.providers.base import BaseLLMProvider
from packages.harness_core.providers.gemini_provider import GeminiProvider
from packages.harness_core.providers.mock_provider import MockLLMProvider
from packages.harness_core.providers.vertex_provider import VertexAIProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Instantiates the appropriate LLM provider adhering to environment settings."""

    @staticmethod
    def create_provider(
        config: Optional[EngineConfig] = None,
        force_mock: bool = False,
        mock_provider: Optional[BaseLLMProvider] = None,
    ) -> BaseLLMProvider:
        """Create provider respecting USE_VERTEX, GEMINI_API_KEY, or Mock fallback."""
        if mock_provider is not None:
            return mock_provider

        if force_mock:
            logger.info("Using MockLLMProvider (force_mock enabled)")
            return MockLLMProvider()

        cfg = config or EngineConfig.from_env()

        # 1. Vertex AI branch
        if cfg.use_vertex:
            logger.info(
                f"Initializing VertexAIProvider for project={cfg.google_cloud_project}, "
                f"region={cfg.gcp_region}, model={cfg.model_name}"
            )
            return VertexAIProvider(
                project_id=cfg.google_cloud_project,
                region=cfg.gcp_region,
                model_name=cfg.model_name,
            )

        # 2. Google AI Studio (Gemini API) branch
        if cfg.gemini_api_key:
            logger.info(f"Initializing GeminiProvider with model={cfg.model_name}")
            return GeminiProvider(
                api_key=cfg.gemini_api_key,
                model_name=cfg.model_name,
            )

        # 3. Fallback when neither key nor vertex is configured
        logger.warning(
            "Neither USE_VERTEX=true nor GEMINI_API_KEY found. Falling back to MockLLMProvider for offline execution."
        )
        return MockLLMProvider(model_name="mock-coding-model")
