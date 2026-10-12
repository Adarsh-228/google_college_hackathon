"""Tests for LLM provider abstraction, Gemini, Vertex, and Mock providers."""

import pytest
from packages.harness_core.config.settings import EngineConfig
from packages.harness_core.contracts.enums import ProviderType
from packages.harness_core.exceptions.errors import (
    ConfigurationError,
    ModelAuthenticationError,
    ModelRateLimitError,
    ProviderError,
)
from packages.harness_core.providers.base import (
    BaseLLMProvider,
    BaseModelProvider,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
)
from packages.harness_core.providers.gemini_provider import GeminiProvider
from packages.harness_core.providers.mock_provider import MockLLMProvider, MockModelProvider
from packages.harness_core.providers.provider_factory import ProviderFactory
from packages.harness_core.providers.vertex_provider import VertexAIProvider


# ==============================================================================
# 1. Mock Provider Initialization & Generation
# ==============================================================================

def test_mock_provider_initialization():
    mock1 = MockModelProvider()
    assert mock1.model_name == "mock-coding-model"
    assert mock1.provider_type == ProviderType.MOCK
    assert mock1.supports_exact_token_counting() is False
    assert issubclass(MockModelProvider, BaseModelProvider)

    mock2 = MockModelProvider(model_name="custom-test-model")
    assert mock2.model_name == "custom-test-model"


@pytest.mark.asyncio
async def test_mock_provider_generation_and_queue():
    mock = MockModelProvider()
    mock.queue_text_response("First answer", in_tokens=5, out_tokens=10)
    mock.queue_tool_call(
        tool_name="read_file",
        arguments={"file_path": "README.md"},
        thought="Reading file",
        in_tokens=15,
        out_tokens=20,
    )

    msg = [LLMMessage(role="user", content="Hello")]

    # 1. First queued response: text
    resp1 = await mock.generate(msg)
    assert isinstance(resp1, LLMResponse)
    assert resp1.content == "First answer"
    assert resp1.input_tokens == 5
    assert resp1.output_tokens == 10
    assert len(resp1.tool_calls) == 0
    assert resp1.finish_reason == "stop"

    # 2. Second queued response: tool call
    resp2 = await mock.generate(msg)
    assert isinstance(resp2, LLMResponse)
    assert resp2.content == "Reading file"
    assert len(resp2.tool_calls) == 1
    assert resp2.tool_calls[0].tool_name == "read_file"
    assert resp2.tool_calls[0].arguments == {"file_path": "README.md"}
    assert resp2.finish_reason == "tool_call"


@pytest.mark.asyncio
async def test_mock_provider_token_counting():
    mock = MockModelProvider()
    count_str = await mock.count_tokens("12345678")
    assert count_str == 2

    messages = [
        LLMMessage(role="system", content="1234"),
        LLMMessage(role="user", content="12345678"),
    ]
    count_msgs = await mock.count_tokens(messages)
    assert count_msgs == 3  # (4 + 8) // 4 = 3


# ==============================================================================
# 2. Provider Error Simulation
# ==============================================================================

@pytest.mark.asyncio
async def test_mock_provider_error_simulation():
    mock = MockModelProvider()
    mock.queue_error(ModelRateLimitError("Rate limit exceeded"))
    mock.queue_error(ModelAuthenticationError("Invalid API key"))

    msg = [LLMMessage(role="user", content="Ping")]

    with pytest.raises(ModelRateLimitError) as exc_info:
        await mock.generate(msg)
    assert "Rate limit exceeded" in str(exc_info.value)

    with pytest.raises(ModelAuthenticationError) as exc_info2:
        await mock.generate(msg)
    assert "Invalid API key" in str(exc_info2.value)


# ==============================================================================
# 3. Provider Factory & Selection
# ==============================================================================

def test_provider_factory_selection():
    # 1. No credentials configured -> Mock provider fallback for offline execution
    cfg_empty = EngineConfig(gemini_api_key=None, use_vertex=False)
    p1 = ProviderFactory.create_provider(cfg_empty)
    assert isinstance(p1, MockModelProvider)
    assert p1.provider_type == ProviderType.MOCK

    # 2. USE_VERTEX=false with GEMINI_API_KEY -> GeminiProvider
    cfg_gemini = EngineConfig(
        use_vertex=False,
        gemini_api_key="ai-studio-secret-key-xyz",
        model_name="gemini-2.5-flash",
    )
    p2 = ProviderFactory.create_provider(cfg_gemini)
    assert isinstance(p2, GeminiProvider)
    assert p2.provider_type == ProviderType.GEMINI_STUDIO
    assert p2.model_name == "gemini-2.5-flash"

    # 3. USE_VERTEX=true with Project & Region -> VertexAIProvider
    cfg_vertex = EngineConfig(
        use_vertex=True,
        google_cloud_project="my-hackathon-gcp-project",
        gcp_region="europe-west1",
        model_name="gemini-2.5-pro",
    )
    p3 = ProviderFactory.create_provider(cfg_vertex)
    assert isinstance(p3, VertexAIProvider)
    assert p3.provider_type == ProviderType.VERTEX_AI
    assert p3.model_name == "gemini-2.5-pro"


def test_provider_factory_explicit_injection():
    # Explicit injection overrides config
    custom_mock = MockModelProvider(model_name="injected-mock")
    cfg = EngineConfig(use_vertex=True, google_cloud_project="proj")
    p = ProviderFactory.create_provider(cfg, mock_provider=custom_mock)
    assert p is custom_mock
    assert p.model_name == "injected-mock"


def test_provider_factory_force_mock_flag():
    cfg = EngineConfig(gemini_api_key="real-key", use_vertex=False)
    p = ProviderFactory.create_provider(cfg, force_mock=True)
    assert isinstance(p, MockModelProvider)


# ==============================================================================
# 4. Missing Credentials & Invalid Configuration Handling
# ==============================================================================

def test_gemini_missing_api_key():
    with pytest.raises(ConfigurationError) as exc_info:
        GeminiProvider(api_key="")
    assert "GEMINI_API_KEY is required" in str(exc_info.value)


def test_vertex_missing_project_id():
    with pytest.raises(ConfigurationError) as exc_info:
        VertexAIProvider(project_id="")
    assert "GOOGLE_CLOUD_PROJECT must be specified" in str(exc_info.value)


# ==============================================================================
# 5. Message and Tool Payload Normalization
# ==============================================================================

def test_gemini_message_conversion():
    provider = GeminiProvider(api_key="test-api-key")
    messages = [
        LLMMessage(role="system", content="System instruction"),
        LLMMessage(role="user", content="Write a function"),
        LLMMessage(
            role="model",
            content="Thinking",
            tool_calls=[LLMToolCall(call_id="c1", tool_name="list_files", arguments={"path": "."})],
        ),
        LLMMessage(
            role="tool",
            tool_name="list_files",
            content="['main.py']",
        ),
    ]

    contents = provider._convert_messages_to_gemini(messages)
    # System message is routed separately to systemInstruction, not contents
    assert len(contents) == 3
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "Write a function"
    assert contents[1]["role"] == "model"
    assert "functionCall" in contents[1]["parts"][1]
    assert contents[2]["role"] == "user"
    assert "functionResponse" in contents[2]["parts"][0]


def test_gemini_tool_conversion():
    provider = GeminiProvider(api_key="test-api-key")
    tools = [
        {
            "name": "read_file",
            "description": "Read file contents",
            "parameters": {
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
                "required": ["file_path"],
            },
        }
    ]
    converted = provider._convert_tools_to_gemini(tools)
    assert converted is not None
    assert len(converted) == 1
    assert "functionDeclarations" in converted[0]
    decl = converted[0]["functionDeclarations"][0]
    assert decl["name"] == "read_file"
    assert "file_path" in decl["parameters"]["properties"]


def test_vertex_message_and_tool_conversion():
    provider = VertexAIProvider(project_id="test-proj")
    messages = [
        LLMMessage(role="user", content="Create a test"),
    ]
    tools = [
        {"name": "write_file", "description": "Write", "parameters": {"type": "object"}}
    ]

    contents = provider._convert_messages_to_vertex(messages)
    assert len(contents) == 1
    assert contents[0]["role"] == "user"

    vertex_tools = provider._convert_tools_to_vertex(tools)
    assert vertex_tools is not None
    assert len(vertex_tools[0]["functionDeclarations"]) == 1
    assert vertex_tools[0]["functionDeclarations"][0]["name"] == "write_file"
