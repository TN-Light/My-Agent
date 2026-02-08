"""
LLM Client - Ollama Integration
Local-only LLM inference client.

Phase-D: Quality gate — validates JSON output, retries with simplified prompt.

Focuses solely on API communication.
Logic moved to logic/llm_planner.py
"""
import logging
import json
import time
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Ollama API client with retry logic and graceful degradation.
    """
    
    def __init__(self, base_url: str, model: str, temperature: float = 0.1, timeout: int = 120):
        """
        Initialize the LLM client.
        
        Args:
            base_url: Ollama API endpoint
            model: Model name (e.g., "llama3.2")
            temperature: Sampling temperature (lower = more deterministic)
            timeout: Request timeout in seconds (default 120 for slow models)
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        
        # Test connection
        if not self._test_connection():
            logger.warning(
                f"Cannot connect to Ollama at {base_url}. "
                "Ensure Ollama is running: 'ollama serve'"
            )
        else:
            logger.info(f"LLMClient initialized: {model} @ {base_url}")
    
    def _test_connection(self) -> bool:
        """Test if Ollama is accessible."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama connection test failed: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check if Ollama is running and healthy.
        
        Ollama returns 'Ollama is running' at its root endpoint when healthy.
        
        Returns:
            True if Ollama is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200:
                logger.info("Ollama health check passed")
                return True
            else:
                logger.warning(f"Ollama health check returned status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            logger.error("Ollama health check failed: cannot connect")
            return False
        except requests.exceptions.Timeout:
            logger.error("Ollama health check failed: timed out")
            return False
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    def generate_completion(self, system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
        """
        Call Ollama API to generate text with retry logic and exponential backoff.
        
        Uses /api/chat with proper message role separation for better
        instruction-following and JSON output quality.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            max_retries: Maximum number of retry attempts (default 3)
            
        Returns:
            Raw LLM response text
            
        Raises:
            ConnectionError: If all retry attempts fail
        """
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 2000  # Increased for detailed chart analysis JSON
            }
        }
        
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"LLM request attempt {attempt}/{max_retries}")
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                
                result = response.json()
                if attempt > 1:
                    logger.info(f"LLM request succeeded on attempt {attempt}")
                # /api/chat returns message.content, /api/generate returns response
                message = result.get("message", {})
                if isinstance(message, dict):
                    return message.get("content", "").strip()
                return result.get("response", "").strip()
                
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.warning(f"LLM connection error on attempt {attempt}/{max_retries}: {e}")
            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"LLM request timed out on attempt {attempt}/{max_retries} (timeout={self.timeout}s)")
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"LLM request failed on attempt {attempt}/{max_retries}: {e}")
            
            # Exponential backoff: 1s, 2s, 4s, ...
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)  # 1, 2, 4
                logger.info(f"Retrying in {backoff}s...")
                time.sleep(backoff)
        
        raise ConnectionError(
            f"Ollama request failed after {max_retries} attempts. "
            f"Last error: {last_exception}"
        )

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        required_fields: Optional[list] = None,
        max_retries: int = 3
    ) -> dict:
        """
        Phase-D: Quality-gated JSON generation.
        
        Calls generate_completion and validates the response is valid JSON.
        If JSON parsing fails, retries with a simplified prompt.
        
        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt containing analysis request
            required_fields: List of field names the JSON must contain
            max_retries: Max retry attempts (default 3)
            
        Returns:
            Parsed JSON dict
            
        Raises:
            ValueError: If all attempts produce invalid JSON
        """
        if required_fields is None:
            required_fields = ["symbol", "trend", "support", "resistance"]
        
        last_response = ""
        
        for attempt in range(1, max_retries + 1):
            try:
                if attempt == 1:
                    # First attempt: full prompt
                    raw = self.generate_completion(system_prompt, user_prompt)
                else:
                    # Retry: simplified prompt asking to fix the output
                    repair_prompt = (
                        f"Your previous response was not valid JSON. "
                        f"Please respond with ONLY a valid JSON object containing these fields: "
                        f"{', '.join(required_fields)}.\n\n"
                        f"Previous response (fix this):\n{last_response[:500]}\n\n"
                        f"Return ONLY the corrected JSON, no other text."
                    )
                    raw = self.generate_completion(system_prompt, repair_prompt)
                
                last_response = raw
                
                # Clean markdown code blocks
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    cleaned = "\n".join(lines[1:])
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                
                # Try to extract JSON from mixed text
                if not cleaned.startswith("{"):
                    # Look for JSON object in the response
                    start = cleaned.find("{")
                    end = cleaned.rfind("}") + 1
                    if start >= 0 and end > start:
                        cleaned = cleaned[start:end]
                
                parsed = json.loads(cleaned)
                
                # Validate required fields
                missing = [f for f in required_fields if f not in parsed]
                if missing and attempt < max_retries:
                    logger.warning(
                        f"Phase-D: JSON missing fields {missing} on attempt {attempt}, retrying..."
                    )
                    continue
                
                if attempt > 1:
                    logger.info(f"Phase-D: JSON quality gate passed on attempt {attempt}")
                
                return parsed
                
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Phase-D: JSON parse failed on attempt {attempt}/{max_retries}: {e}"
                )
                if attempt < max_retries:
                    time.sleep(1)
                    continue
            except ConnectionError:
                raise  # Don't swallow connection errors
        
        # All attempts failed — return what we can
        logger.error(f"Phase-D: JSON quality gate failed after {max_retries} attempts")
        raise ValueError(
            f"LLM failed to produce valid JSON after {max_retries} attempts. "
            f"Last response: {last_response[:200]}"
        )
