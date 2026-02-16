# src/perception/vlm/vlm_client.py
"""
VLM (Vision-Language Model) client for UI detection.
Supports Claude (Anthropic), GPT-4V (OpenAI), and other VLM APIs.
"""

import os
import base64
import json
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from io import BytesIO
import cv2
import numpy as np

from .ui_parser import UIParser, UIAnalysisResult
from .prompt_templates import get_ui_discovery_prompt


class VLMClient(ABC):
    """Abstract base class for VLM clients."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = ""):
        self.api_key = api_key
        self.model_name = model_name
        self.parser = UIParser()

    @abstractmethod
    def analyze_ui(self, image_path: str, prompt: Optional[str] = None, 
                   **kwargs) -> UIAnalysisResult:
        """Analyze UI in image and return detected elements."""
        pass

    def encode_image_to_base64(self, image_path: str) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.standard_b64encode(image_file.read()).decode("utf-8")

    def encode_numpy_to_base64(self, image_array: np.ndarray, fmt: str = ".jpg") -> str:
        """Encode numpy array to base64 string."""
        success, buffer = cv2.imencode(fmt, image_array)
        if not success:
            raise ValueError("Failed to encode image")
        return base64.standard_b64encode(buffer).decode("utf-8")

    def get_image_dimensions(self, image_path: str) -> tuple:
        """Get image width and height."""
        img = cv2.imread(image_path)
        if img is None:
            return None, None
        height, width = img.shape[:2]
        return width, height


class ClaudeVLMClient(VLMClient):
    """Claude (Anthropic) Vision API client."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "claude-3-5-sonnet-20241022"):
        super().__init__(api_key or os.getenv("ANTHROPIC_API_KEY"), model_name)
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")

    def analyze_ui(self, image_path: str, prompt: Optional[str] = None, 
                   **kwargs) -> UIAnalysisResult:
        """Analyze UI using Claude Vision API."""
        prompt = prompt or get_ui_discovery_prompt()
        
        try:
            # Encode image
            image_data = self.encode_image_to_base64(image_path)
            
            # Get image dimensions
            width, height = self.get_image_dimensions(image_path)
            
            # Call Claude API
            message = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
            )
            
            # Parse response
            response_text = message.content[0].text
            return self.parser.parse_vlm_response(response_text, width, height)
        
        except Exception as e:
            from .ui_parser import UIAnalysisResult
            return UIAnalysisResult(
                elements=[],
                parse_successful=False,
                parse_error=f"Claude API error: {str(e)}"
            )


class GPT4VClient(VLMClient):
    """GPT-4V (OpenAI) Vision API client."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4-vision-preview"):
        super().__init__(api_key or os.getenv("OPENAI_API_KEY"), model_name)
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")

    def analyze_ui(self, image_path: str, prompt: Optional[str] = None, 
                   **kwargs) -> UIAnalysisResult:
        """Analyze UI using GPT-4V API."""
        prompt = prompt or get_ui_discovery_prompt()
        
        try:
            # Encode image
            image_data = self.encode_image_to_base64(image_path)
            
            # Get image dimensions
            width, height = self.get_image_dimensions(image_path)
            
            # Call GPT-4V API
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
                max_tokens=4096,
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            return self.parser.parse_vlm_response(response_text, width, height)
        
        except Exception as e:
            from .ui_parser import UIAnalysisResult
            return UIAnalysisResult(
                elements=[],
                parse_successful=False,
                parse_error=f"GPT-4V API error: {str(e)}"
            )


class LocalVLMClient(VLMClient):
    """Local VLM client using open-source models (e.g., LLaVA, Qwen)."""

    def __init__(self, model_name: str = "llava-hf/llava-1.5-7b-hf"):
        super().__init__(None, model_name)
        try:
            from transformers import AutoProcessor, AutoModelForCausalLM
            import torch
            
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.processor = AutoProcessor.from_pretrained(model_name)
            dtype = torch.float16 if self.device == "cuda" else torch.float32

            # Most text-only/causal models
            try:
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=dtype,
                    device_map="auto"
                )
            except Exception:
                # Vision-language checkpoints (e.g., LLaVA) require different model classes.
                try:
                    from transformers import AutoModelForVision2Seq
                    self.model = AutoModelForVision2Seq.from_pretrained(
                        model_name,
                        torch_dtype=dtype,
                        device_map="auto"
                    )
                except Exception:
                    from transformers import LlavaForConditionalGeneration
                    self.model = LlavaForConditionalGeneration.from_pretrained(
                        model_name,
                        torch_dtype=dtype,
                        device_map="auto"
                    )
        except ImportError:
            raise ImportError(
                "transformers/torch not installed. Install with: "
                "pip install torch torchvision transformers sentencepiece accelerate"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize local model '{model_name}': {e}")

    def analyze_ui(self, image_path: str, prompt: Optional[str] = None, 
                   **kwargs) -> UIAnalysisResult:
        """Analyze UI using local VLM."""
        prompt = prompt or get_ui_discovery_prompt()
        
        try:
            from PIL import Image
            import torch
            
            # Load and prepare image
            image = Image.open(image_path).convert("RGB")
            width, height = image.size

            if "llava" in self.model_name.lower() and "<image>" not in prompt:
                prompt = f"<image>\n{prompt}"
            
            # Prepare inputs
            inputs = self.processor(text=prompt, images=image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate response
            with torch.no_grad():
                output_ids = self.model.generate(**inputs, max_new_tokens=2048)
            
            # Decode response
            response_text = self.processor.decode(output_ids[0], skip_special_tokens=True)
            
            # Remove the prompt from response
            response_text = response_text.replace(prompt, "").strip()
            
            return self.parser.parse_vlm_response(response_text, width, height)
        
        except Exception as e:
            from .ui_parser import UIAnalysisResult
            return UIAnalysisResult(
                elements=[],
                parse_successful=False,
                parse_error=f"Local VLM error: {str(e)}"
            )


def get_vlm_client(provider: str = "claude", **kwargs) -> VLMClient:
    """
    Factory function to get VLM client.
    
    Args:
        provider: "claude", "gpt4v", or "local"
        **kwargs: Provider-specific arguments
    
    Returns:
        VLMClient instance
    """
    provider = provider.lower().strip()
    
    if provider == "claude":
        return ClaudeVLMClient(**kwargs)
    elif provider in ["gpt4v", "openai", "gpt-4v"]:
        return GPT4VClient(**kwargs)
    elif provider == "local":
        return LocalVLMClient(**kwargs)
    else:
        raise ValueError(f"Unknown VLM provider: {provider}")
