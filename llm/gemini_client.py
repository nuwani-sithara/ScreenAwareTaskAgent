"""Google Gemini API client wrapper with same interface as OllamaClient.

Usage:
    from llm.gemini_client import GeminiClient
    c = GeminiClient(api_key="AIza...")
    text = c.generate("Hello world", model="gemini-1.5-flash")

Compatible with OllamaClient interface for drop-in replacement.
"""
import os
import logging
from typing import Optional

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
        
        # Lazy import to avoid dependency if not used
        self._genai = None
    
    def _ensure_genai(self):
        """Lazy import of google.generativeai library"""
        if self._genai is None:
            try:
                import google.generativeai as genai
                self._genai = genai
                if self.api_key:
                    self._genai.configure(api_key=self.api_key)
            except ImportError:
                logger.error("❌ google-generativeai library not installed. Run: pip install google-generativeai")
                raise ImportError("google-generativeai library required for GeminiClient. Install with: pip install google-generativeai")
    
    def generate(
        self, 
        prompt: str, 
        model: str = "gemini-1.5-flash", 
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
        
        import time
        start = time.time()
        
        try:
            logger.info(f"💎 Calling Gemini API: model={model}, max_tokens={max_tokens}")
            
            # Create model instance
            gemini_model = self._genai.GenerativeModel(model)
            
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
            
            # Generate content
            response = gemini_model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Extract text from response
            text = response.text.strip()
            
            elapsed = time.time() - start
            logger.info(f"✅ Gemini responded in {elapsed:.2f}s")
            
            return text
            
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"❌ Gemini API error after {elapsed:.2f}s: {e}")
            raise
    
    def list_models(self) -> list:
        """List available Gemini models"""
        if not self.api_key:
            return []
        
        try:
            self._ensure_genai()
            models = self._genai.list_models()
            return [m.name for m in models if 'generateContent' in m.supported_generation_methods]
        except Exception as e:
            logger.warning(f"Failed to list Gemini models: {e}")
            return ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]  # Default list


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
