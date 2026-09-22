import json
import logging
import re
from typing import Any, Dict, Optional, Tuple
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.base_url = settings.LLM_BASE_URL
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    async def check_health(self) -> bool:
        """Check if local Ollama server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def check_health_sync(self) -> bool:
        """Synchronous health check for startup & scripts."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def generate_json(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Generate strict JSON output using Ollama API with format="json".
        Returns (parsed_json_dict, is_live_llm).
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(f"{self.base_url}/api/generate", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data.get("response", "").strip()
                    parsed = self._clean_and_parse_json(raw_text)
                    if parsed is not None:
                        return parsed, True
                    logger.warning(f"Failed to parse LLM response: {raw_text}")
        except Exception as e:
            logger.warning(f"LLM request error: {e}")

        return None, False

    def generate_json_sync(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Synchronous generation for CLI scripts."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(f"{self.base_url}/api/generate", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data.get("response", "").strip()
                    parsed = self._clean_and_parse_json(raw_text)
                    if parsed is not None:
                        return parsed, True
                    logger.warning(f"Failed to parse LLM response: {raw_text}")
        except Exception as e:
            logger.warning(f"LLM request error: {e}")

        return None, False

    def _clean_and_parse_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse JSON from LLM output, stripping code blocks if any."""
        if not raw_text:
            return None

        # Clean code fence wrappers
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt regex extraction of outermost JSON object
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        return None

llm_client = LLMClient()
