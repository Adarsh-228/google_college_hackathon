"""Google AI Studio Gemini provider."""

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


class GeminiProvider(BaseLLMProvider):
    """Integrates with Google AI Studio Gemini API."""

    API_BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        if not api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is required for GeminiProvider. "
                "Provide it in constructor or set GEMINI_API_KEY in environment."
            )
        self._api_key = api_key
        self._model_name = model_name

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GEMINI_STUDIO

    @property
    def model_name(self) -> str:
        return self._model_name

    def _convert_messages_to_gemini(
        self, messages: List[LLMMessage]
    ) -> List[Dict[str, Any]]:
        """Map standard LLMMessages to Gemini contents structure."""
        contents: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                # System instructions handled separately in config
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

    def _convert_tools_to_gemini(
        self, tools: Optional[List[Dict[str, Any]]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Convert standard JSON schemas to Gemini functionDeclarations."""
        if not tools:
            return None

        declarations: List[Dict[str, Any]] = []
        for tool in tools:
            decl = {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            }
            declarations.append(decl)

        return [{"functionDeclarations": declarations}]

    async def generate(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Execute generateContent API call."""
        url = f"{self.API_BASE}/models/{self._model_name}:generateContent?key={self._api_key}"

        contents = self._convert_messages_to_gemini(messages)
        gemini_tools = self._convert_tools_to_gemini(tools)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if max_output_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_output_tokens

        # Check for system instruction
        system_msgs = [m.content for m in messages if m.role == "system"]
        if system_instruction or system_msgs:
            sys_prompt = system_instruction or "\n".join(system_msgs)
            payload["systemInstruction"] = {
                "parts": [{"text": sys_prompt}]
            }

        if gemini_tools:
            payload["tools"] = gemini_tools

        # Run non-blocking HTTP call
        resp_data = await asyncio.to_thread(self._send_request, url, payload)
        return self._parse_gemini_response(resp_data)

    def _send_request(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute synchronized HTTP POST request."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else ""
            if e.code in (401, 403):
                raise ModelAuthenticationError(f"Gemini API authentication failed: {err_body}")
            if e.code == 429:
                raise ModelRateLimitError(f"Gemini API rate limit exceeded: {err_body}")
            raise ProviderError(f"Gemini API HTTP {e.code}: {err_body}")
        except Exception as e:
            raise ProviderError(f"Gemini API request failed: {str(e)}")

    def _parse_gemini_response(self, data: Dict[str, Any]) -> LLMResponse:
        """Parse Gemini JSON response into LLMResponse."""
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
        in_tokens = usage.get("promptTokenCount", 0)
        out_tokens = usage.get("candidatesTokenCount", 0)

        return LLMResponse(
            content="\n".join(text_chunks),
            tool_calls=tool_calls,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            finish_reason=cand.get("finishReason", "stop"),
            raw_response=data,
        )

    async def count_tokens(self, text_or_messages: Any) -> int:
        """Count tokens via countTokens API."""
        url = f"{self.API_BASE}/models/{self._model_name}:countTokens?key={self._api_key}"
        if isinstance(text_or_messages, str):
            payload = {"contents": [{"parts": [{"text": text_or_messages}]}]}
        elif isinstance(text_or_messages, list):
            payload = {"contents": self._convert_messages_to_gemini(text_or_messages)}
        else:
            payload = {"contents": [{"parts": [{"text": str(text_or_messages)}]}]}

        try:
            resp_data = await asyncio.to_thread(self._send_request, url, payload)
            return resp_data.get("totalTokens", 0)
        except Exception as e:
            logger.warning(f"Gemini token counting failed, using estimate: {e}")
            # Fallback estimation: ~4 chars per token
            raw = str(text_or_messages)
            return max(1, len(raw) // 4)

    def supports_exact_token_counting(self) -> bool:
        return True
