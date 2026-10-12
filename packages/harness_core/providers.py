import os
import re
import json
import time
from typing import Dict, Any, List, Optional, Tuple

class LLMResponse:
    def __init__(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tokens_in_uncached: int = 0,
        tokens_in_cached: int = 0,
        tokens_out: int = 0,
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.tokens_in_uncached = tokens_in_uncached
        self.tokens_in_cached = tokens_in_cached
        self.tokens_out = tokens_out

class VertexAIClient:
    """
    Google Cloud Vertex AI & Google AI Studio adapter for Gemini 2.5 Flash / Pro.
    Tracks prompt-caching metadata and computes cache-aware token costs.
    """

    def __init__(
        self,
        model_id: str = "gemini-2.5-flash",
        project_id: Optional[str] = None,
        location: str = "us-central1",
        api_key: Optional[str] = None,
    ):
        self.model_id = model_id
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from google import genai
            if self.project_id:
                self._client = genai.Client(vertexai=True, project=self.project_id, location=self.location)
            elif self.api_key:
                self._client = genai.Client(api_key=self.api_key)
        except Exception:
            self._client = None

    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Invokes Gemini via Vertex AI or Google AI Studio."""
        if not self._client:
            raise RuntimeError("Gemini Client not initialized. Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT.")

        # Estimate tokens as fallback if usage_metadata is missing
        prompt_str = system_prompt + "\n".join([str(m) for m in messages])
        estimated_in = max(1, len(prompt_str) // 4)

        try:
            # Call Gemini
            response = self._client.models.generate_content(
                model=self.model_id,
                contents=prompt_str,
            )
            text_out = response.text or ""
            tokens_out = len(text_out) // 4
            
            # Check usage metadata if provided by SDK
            tokens_cached = 0
            tokens_uncached = estimated_in
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                meta = response.usage_metadata
                tokens_cached = getattr(meta, "cached_content_token_count", 0) or 0
                total_in = getattr(meta, "prompt_token_count", estimated_in) or estimated_in
                tokens_uncached = max(0, total_in - tokens_cached)
                tokens_out = getattr(meta, "candidates_token_count", tokens_out) or tokens_out

            return LLMResponse(
                content=text_out,
                tool_calls=[],
                tokens_in_uncached=tokens_uncached,
                tokens_in_cached=tokens_cached,
                tokens_out=tokens_out,
            )
        except Exception as e:
            raise RuntimeError(f"Vertex AI Gemini invocation failed: {str(e)}")

class MockLLMClient:
    """
    Deterministic offline simulator for Gemini agent trajectories.
    Allows zero-token offline testing of all 5 benchmark scenarios.
    """

    def __init__(self, scenario: str = "task_01_off_by_one"):
        self.scenario = scenario
        self.turn_count = 0

    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        self.turn_count += 1
        
        # Calculate mock token values
        prompt_len = sum(len(str(m.get("content", ""))) for m in messages)
        tokens_in = max(200, prompt_len // 4)
        tokens_cached = int(tokens_in * 0.4) if self.turn_count > 2 else 0
        tokens_uncached = max(0, tokens_in - tokens_cached)

        # -------------------------------------------------------------
        # Scenario: task_03_stuck_loop_api (Simulates 5-warning & 8-breaker)
        # -------------------------------------------------------------
        if "stuck_loop" in self.scenario:
            # Emits the exact same failing tool call repeatedly
            return LLMResponse(
                content="Retrying failing API call with identical payload...",
                tool_calls=[{
                    "name": "bash",
                    "args": {"command": "python -c 'import sys; sys.exit(1)'"}
                }],
                tokens_in_uncached=tokens_uncached,
                tokens_in_cached=tokens_cached,
                tokens_out=40,
            )

        # -------------------------------------------------------------
        # Scenario: Standard testbed resolution path
        # -------------------------------------------------------------
        if self.turn_count == 1:
            # Turn 1: Create initial plan
            return LLMResponse(
                content="I will first create a plan to resolve this issue.",
                tool_calls=[{
                    "name": "update_plan",
                    "args": {
                        "plan": [
                            {"content": "Inspect repository and failing test", "status": "in_progress"},
                            {"content": "Read source code and locate bug", "status": "pending"},
                            {"content": "Apply patch and verify tests", "status": "pending"},
                        ]
                    }
                }],
                tokens_in_uncached=tokens_uncached,
                tokens_in_cached=tokens_cached,
                tokens_out=60,
            )

        elif self.turn_count == 2:
            # Turn 2: Run pytest to see the failure
            return LLMResponse(
                content="Now running pytest to reproduce the bug.",
                tool_calls=[{
                    "name": "bash",
                    "args": {"command": "pytest -v"}
                }],
                tokens_in_uncached=tokens_uncached,
                tokens_in_cached=tokens_cached,
                tokens_out=50,
            )

        elif self.turn_count == 3:
            # Turn 3: Inspect source file with full read
            target_file = "app.py"
            if "auth_token" in self.scenario:
                target_file = "auth.py"
            elif "parser" in self.scenario or "verbose" in self.scenario:
                target_file = "parser.py"
            elif "circular" in self.scenario:
                target_file = "service.py"

            return LLMResponse(
                content=f"Reading {target_file} to inspect the bug logic.",
                tool_calls=[{
                    "name": "read_file",
                    "args": {"path": target_file, "offset": 1, "limit": 2000}
                }],
                tokens_in_uncached=tokens_uncached,
                tokens_in_cached=tokens_cached,
                tokens_out=50,
            )

        elif self.turn_count == 4:
            # Turn 4: Apply surgical edit
            if "off_by_one" in self.scenario:
                return LLMResponse(
                    content="Fixing the off-by-one pagination slice.",
                    tool_calls=[{
                        "name": "edit_file",
                        "args": {
                            "path": "app.py",
                            "old_text": "return items[start:end - 1]",
                            "new_text": "return items[start:end]",
                        }
                    }],
                    tokens_in_uncached=tokens_uncached,
                    tokens_in_cached=tokens_cached,
                    tokens_out=60,
                )
            elif "auth_token" in self.scenario:
                return LLMResponse(
                    content="Masking token before logging.",
                    tool_calls=[{
                        "name": "edit_file",
                        "args": {
                            "path": "auth.py",
                            "old_text": "logger.info(f'Token: {raw_token}')",
                            "new_text": "logger.info(f'Token: {raw_token[:4]}***')",
                        }
                    }],
                    tokens_in_uncached=tokens_uncached,
                    tokens_in_cached=tokens_cached,
                    tokens_out=60,
                )
            else:
                return LLMResponse(
                    content="Updating code to resolve edge cases.",
                    tool_calls=[{
                        "name": "bash",
                        "args": {"command": "echo 'fix applied'"}
                    }],
                    tokens_in_uncached=tokens_uncached,
                    tokens_in_cached=tokens_cached,
                    tokens_out=40,
                )

        elif self.turn_count == 5:
            # Turn 5: Run pytest again to verify
            return LLMResponse(
                content="Verifying that all tests now pass.",
                tool_calls=[{
                    "name": "bash",
                    "args": {"command": "pytest -v"}
                }],
                tokens_in_uncached=tokens_uncached,
                tokens_in_cached=tokens_cached,
                tokens_out=50,
            )

        else:
            # Turn 6+: Done!
            return LLMResponse(
                content="The bug has been fixed and verified with pytest. Task complete!",
                tool_calls=[],
                tokens_in_uncached=tokens_uncached,
                tokens_in_cached=tokens_cached,
                tokens_out=80,
            )
