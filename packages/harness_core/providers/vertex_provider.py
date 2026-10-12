"""Google Cloud Vertex AI provider."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

from packages.harness_core.contracts.enums import ProviderType
from packages.harness_core.exceptions.errors import (
    ConfigurationError,
    ModelAuthenticationError,
    ModelRateLimitError,
    ProviderError,
)
from packages.harness_core.providers.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
)

logger = logging.getLogger(__name__)


class VertexAIProvider(BaseLLMProvider):
    """Integrates with Google Cloud Vertex AI endpoint using ADC."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        region: str = "us-central1",
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        if not project_id:
            raise ConfigurationError(
                "GOOGLE_CLOUD_PROJECT must be specified for Vertex AI provider. "
                "Provide project_id or set GOOGLE_CLOUD_PROJECT in environment."
            )
        self._project_id = project_id
        self._region = region
        self._model_name = model_name

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.VERTEX_AI

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_access_token(self) -> str:
        """Obtain bearer access token from Application Default Credentials (ADC)."""
        try:
            import google.auth
            import google.auth.transport.requests

            credentials, project = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            return credentials.token
        except ImportError:
            raise ConfigurationError(
                "google-auth package is required for Vertex AI ADC authentication. "
                "Install with `pip install google-auth` or use GeminiProvider with GEMINI_API_KEY."
            )
        except Exception as e:
            raise ModelAuthenticationError(
                f"Failed to authenticate with Vertex AI via ADC: {str(e)}. "
                "Run `gcloud auth application-default login` or check service account permissions."
            )

    def _get_endpoint_url(self, method: str = "generateContent") -> str:
        return (
            f"https://{self._region}-aiplatform.googleapis.com/v1/"
            f"projects/{self._project_id}/locations/{self._region}/publishers/google/models/"
            f"{self._model_name}:{method}"
        )

    def _convert_messages_to_vertex(
        self, messages: List[LLMMessage]
    ) -> List[Dict[str, Any]]:
        """Map LLM messages to Vertex AI contents payload."""
        contents: List[Dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                continue
            role = "user" if msg.role in ("user", "tool") else "model"
            parts: List[Dict[str, Any]] = []

            if msg.role == "tool":
                parts.append({
                    "functionResponse": {
                        "name": msg.tool_name or "tool_call",
                        "response": {
                            "output": msg.content,
                            "metadata": msg.metadata,
                        },
                    }
                })
            else:
                if msg.content:
                    parts.append({"text": msg.content})
                for tc in msg.tool_calls:
                    parts.append({
                        "functionCall": {
                            "name": tc.tool_name,
                            "args": tc.arguments,
                        }
                    })

            if parts:
                contents.append({"role": role, "parts": parts})
        return contents

    def _convert_tools_to_vertex(
        self, tools: Optional[List[Dict[str, Any]]]
    ) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        declarations = []
        for tool in tools:
            declarations.append({
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            })
        return [{"functionDeclarations": declarations}]

    async def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Call Vertex AI generateContent."""
        token = await asyncio.to_thread(self._get_access_token)
        url = self._get_endpoint_url("generateContent")

        contents = self._convert_messages_to_vertex(messages)
        vertex_tools = self._convert_tools_to_vertex(tools)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }

        if max_output_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_output_tokens

        system_msgs = [m.content for m in messages if m.role == "system"]
        if system_instruction or system_msgs:
            sys_prompt = system_instruction or "\n".join(system_msgs)
            payload["systemInstruction"] = {"parts": [{"text": sys_prompt}]}

        if vertex_tools:
            payload["tools"] = vertex_tools

        resp_data = await asyncio.to_thread(self._send_request, url, payload, token)
        return self._parse_vertex_response(resp_data)

    def _send_request(self, url: str, payload: Dict[str, Any], token: str) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else ""
            if e.code in (401, 403):
                raise ModelAuthenticationError(f"Vertex AI authentication failed: {err_body}")
            if e.code == 429:
                raise ModelRateLimitError(f"Vertex AI quota exceeded: {err_body}")
            raise ProviderError(f"Vertex AI HTTP {e.code}: {err_body}")
        except Exception as e:
            raise ProviderError(f"Vertex AI request failed: {str(e)}")

    def _parse_vertex_response(self, data: Dict[str, Any]) -> LLMResponse:
        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(content="", finish_reason="empty", raw_response=data)

        cand = candidates[0]
        content_parts = cand.get("content", {}).get("parts", [])
        text_chunks: List[str] = []
        tool_calls: List[LLMToolCall] = []

        for p in content_parts:
            if "text" in p:
                text_chunks.append(p["text"])
            elif "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append(
                    LLMToolCall(
                        call_id=f"call_{uuid4().hex[:8]}",
                        tool_name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    )
                )

        usage = data.get("usageMetadata", {})
        return LLMResponse(
            content="\n".join(text_chunks),
            tool_calls=tool_calls,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            finish_reason=cand.get("finishReason", "stop"),
            raw_response=data,
        )

    async def count_tokens(self, text_or_messages: Any) -> int:
        token = await asyncio.to_thread(self._get_access_token)
        url = self._get_endpoint_url("countTokens")
        if isinstance(text_or_messages, str):
            payload = {"contents": [{"parts": [{"text": text_or_messages}]}]}
        elif isinstance(text_or_messages, list):
            payload = {"contents": self._convert_messages_to_vertex(text_or_messages)}
        else:
            payload = {"contents": [{"parts": [{"text": str(text_or_messages)}]}]}

        try:
            resp_data = await asyncio.to_thread(self._send_request, url, payload, token)
            return resp_data.get("totalTokens", 0)
        except Exception as e:
            logger.warning(f"Vertex countTokens failed, using fallback estimate: {e}")
            return max(1, len(str(text_or_messages)) // 4)

    def supports_exact_token_counting(self) -> bool:
        return True
