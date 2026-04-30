"""Google Gemini API client wrapper with same interface as OllamaClient.

Usage:
    from llm.gemini_client import GeminiClient
    c = GeminiClient(api_key="AIza...")
    text = c.generate("Hello world", model="gemini-1.5-flash")

Compatible with OllamaClient interface for drop-in replacement.

Uses the modern ``google-genai`` SDK when available, and falls back to
``google-generativeai`` only for backward compatibility.
"""
import os
import logging
from typing import Optional
import time

logger = logging.getLogger(__name__)


class GeminiClient:
    """Google Gemini API client matching OllamaClient interface"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Google API key. If None, reads from GEMINI_API_KEY or GOOGLE_API_KEY env var
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("⚠️ No Gemini API key provided. Set GEMINI_API_KEY env var or pass api_key parameter.")
        
        # Lazy initialization to avoid hard dependency if not used
        self._sdk = None  # "google-genai" or "google-generativeai"
        self._client = None
        self._genai = None

    @staticmethod
    def _is_model_unavailable(error_text: str) -> bool:
        msg = (error_text or "").lower()
        return (
            "not found" in msg
            or "no longer available" in msg
            or "not available to new users" in msg
            or "unsupported model" in msg
        )

    @staticmethod
    def _is_transient_error(error_text: str) -> bool:
        msg = (error_text or "").lower()
        return (
            "503" in msg
            or "unavailable" in msg
            or "high demand" in msg
            or "resource_exhausted" in msg
            or "quota exceeded" in msg
            or "429" in msg
            or "deadline exceeded" in msg
            or "timed out" in msg
            or "timeout" in msg
            or "rate limit" in msg
        )

    def _model_candidates(self, requested_model: str) -> list[str]:
        candidates: list[str] = []
        if requested_model:
            candidates.append(requested_model)

        preferred = [
            "models/gemini-2.5-flash",
            "models/gemini-flash-latest",
            "models/gemini-2.5-pro",
            "models/gemini-pro-latest",
            "models/gemini-1.5-flash",
        ]

        for m in preferred:
            if m not in candidates:
                candidates.append(m)

        # Add discovered text-generation models last (if available), preserving order and uniqueness.
        for m in self.list_models():
            if m not in candidates:
                candidates.append(m)

        return candidates
    
    def _ensure_genai(self):
        """Initialize Gemini SDK client lazily.

        Preference order:
        1. google-genai (new SDK)
        2. google-generativeai (legacy fallback)
        """
        if self._sdk is not None:
            return

        try:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            self._sdk = "google-genai"
            logger.info("Using Gemini SDK: google-genai")
            return
        except ImportError:
            pass

        try:
            import google.generativeai as genai

            self._genai = genai
            if self.api_key:
                self._genai.configure(api_key=self.api_key)
            self._sdk = "google-generativeai"
            logger.warning("Using legacy Gemini SDK: google-generativeai. Install google-genai to avoid deprecation warnings.")
            return
        except ImportError as exc:
            logger.error("❌ Gemini SDK not installed. Install with: pip install google-genai")
            raise ImportError(
                "Gemini SDK required. Install with: pip install google-genai"
            ) from exc
    
    def generate(
        self, 
        prompt: str, 
        model: str = "models/gemini-2.5-flash", 
        max_tokens: int = 500,
        timeout: int = 30,
        **kwargs
    ) -> str:
        """
        Generate text using Gemini API.
        
        Args:
            prompt: Input prompt text
            model: Model name (gemini-1.5-flash, gemini-1.5-pro, gemini-pro)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            **kwargs: Additional Gemini API parameters
            
        Returns:
            Generated text string
        """
        if not self.api_key:
            raise ValueError("Gemini API key not set. Set GEMINI_API_KEY env var or pass to constructor.")
        
        self._ensure_genai()

        # Configure generation parameters
        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.3),
        }

        # Add optional parameters
        if "top_p" in kwargs:
            generation_config["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            generation_config["top_k"] = kwargs["top_k"]
        # Force JSON output to avoid markdown wrappers and thinking model prefixes
        if "response_mime_type" in kwargs:
            generation_config["response_mime_type"] = kwargs["response_mime_type"]

        candidates = self._model_candidates(model)
        max_retries_per_model = int(kwargs.get("max_retries_per_model", 2))
        last_error: Exception | None = None

        for model_index, candidate_model in enumerate(candidates):
            for attempt in range(max_retries_per_model + 1):
                start = time.time()
                try:
                    logger.info(
                        "💎 Calling Gemini API: model=%s, attempt=%d/%d",
                        candidate_model,
                        attempt + 1,
                        max_retries_per_model + 1,
                    )

                    if self._sdk == "google-genai":
                        try:
                            response = self._client.models.generate_content(
                                model=candidate_model,
                                contents=prompt,
                                config=generation_config,
                            )
                        except TypeError:
                            response = self._client.models.generate_content(
                                model=candidate_model,
                                contents=prompt,
                            )
                    else:
                        gemini_model = self._genai.GenerativeModel(candidate_model)
                        try:
                            response = gemini_model.generate_content(
                                prompt,
                                generation_config=generation_config,
                                request_options={"timeout": timeout},
                            )
                        except TypeError:
                            response = gemini_model.generate_content(
                                prompt,
                                generation_config=generation_config,
                            )

                    text = ""
                    if getattr(response, "text", None):
                        text = response.text.strip()
                    try:
                        for part in response.candidates[0].content.parts:
                            if getattr(part, "thought", False):
                                continue
                            text += getattr(part, "text", "") or ""
                        text = text.strip()
                    except Exception:
                        pass
                    if not text:
                        text = str(response).strip()

                    elapsed = time.time() - start
                    logger.info("✅ Gemini responded in %.2fs using %s", elapsed, candidate_model)
                    return text

                except Exception as e:
                    elapsed = time.time() - start
                    last_error = e
                    err_text = str(e)
                    logger.warning(
                        "Gemini error after %.2fs on model=%s attempt=%d: %s",
                        elapsed,
                        candidate_model,
                        attempt + 1,
                        err_text,
                    )

                    if self._is_model_unavailable(err_text):
                        logger.warning("Model unavailable, switching model from %s", candidate_model)
                        break

                    if self._is_transient_error(err_text) and attempt < max_retries_per_model:
                        backoff_s = min(8.0, 1.5 * (2 ** attempt))
                        logger.info("Transient Gemini error, retrying in %.1fs", backoff_s)
                        time.sleep(backoff_s)
                        continue

                    # Non-transient or retries exhausted for this model -> try next model
                    break

            # Move to next model candidate
            if model_index < len(candidates) - 1:
                logger.info("Trying next Gemini model candidate")

        if last_error is not None:
            logger.error("❌ Gemini API failed across all model candidates: %s", last_error)
            raise last_error
        raise RuntimeError("Gemini API failed without a specific exception")
    
    def list_models(self) -> list:
        """List available Gemini models"""
        if not self.api_key:
            return []

        def _is_supported_text_model(name: str) -> bool:
            lowered = name.lower()
            blocked_fragments = (
                "tts",
                "embedding",
                "realtime",
                "live",
                "audio",
                "imagegeneration",
                "imagen",
                "veo",
                "gemma",
            )
            if any(fragment in lowered for fragment in blocked_fragments):
                return False
            return "generatecontent" in lowered or "gemini" in lowered or "flash" in lowered or "pro" in lowered
        
        try:
            self._ensure_genai()
            if self._sdk == "google-genai":
                models = self._client.models.list()
                names = []
                for model in models:
                    name = getattr(model, "name", None)
                    supported_methods = getattr(model, "supported_generation_methods", []) or []
                    if name and ("generateContent" in supported_methods or _is_supported_text_model(name)):
                        names.append(name)
                return names

            models = self._genai.list_models()
            return [m.name for m in models if 'generateContent' in getattr(m, 'supported_generation_methods', []) and _is_supported_text_model(m.name)]
        except Exception as e:
            logger.warning(f"Failed to list Gemini models: {e}")
            return [
                "models/gemini-2.5-flash",
                "models/gemini-2.5-pro",
                "models/gemini-flash-latest",
            ]


if __name__ == '__main__':
    # Test script
    import sys
    
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("Usage: python gemini_client.py [API_KEY]")
        print("Or set GEMINI_API_KEY environment variable")
        sys.exit(1)
    
    client = GeminiClient(api_key=api_key)
    print("Testing Gemini client...")
    result = client.generate("Say hello in one sentence.", model="gemini-1.5-flash", max_tokens=50)
    print(f"Response: {result}")
