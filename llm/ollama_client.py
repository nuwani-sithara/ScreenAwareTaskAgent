"""Simple Ollama client wrapper with HTTP and CLI fallback.

Usage:
    from llm.ollama_client import OllamaClient
    c = OllamaClient()
    text = c.generate("Hello world", model="mistral")

This module attempts to use Ollama HTTP API at http://127.0.0.1:11434/api/generate
and falls back to the `ollama` CLI when HTTP is not available.
"""
import json
import re
import shlex
import subprocess
from typing import Optional

DEFAULT_HTTP_URL = "http://127.0.0.1:11434/api/generate"


def _strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes and spinner characters from text."""
    # Remove CSI sequences: ESC [ ... (letter)
    text = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', text)
    # Remove OSC sequences: ESC ] ... (BEL or ESC \)
    text = re.sub(r'\x1b\].*?(\x07|\x1b\\)', '', text)
    # Remove other escape sequences
    text = re.sub(r'\x1b[=>]', '', text)
    # Remove CSI-like sequences without ESC: [?digits+letter or [letter
    text = re.sub(r'\[(?:\??\d+;?)*[a-zA-Z]', '', text)
    # Remove remaining bracket sequences (aggressive cleanup)
    text = re.sub(r'\[\d*[A-Z]', '', text)
    # Clean up any remaining ]]] or similar artifacts
    text = re.sub(r'\]{2,}', '', text)
    # Remove Braille pattern characters used for spinners (U+2800 to U+28FF)
    text = re.sub(r'[\u2800-\u28FF]', '', text)
    # Clean up excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


class OllamaClient:
    def __init__(self, http_url: str = DEFAULT_HTTP_URL, cli_cmd: str = "ollama"):
        self.http_url = http_url
        self.cli_cmd = cli_cmd
        # Lazy import of requests to avoid adding hard dependency until used
        self._requests = None

    def _ensure_requests(self):
        if self._requests is None:
            try:
                import requests
                self._requests = requests
            except Exception:
                self._requests = None

    def list_models(self) -> list:
        """Try to list available Ollama models (HTTP then CLI)."""
        self._ensure_requests()
        if self._requests:
            try:
                r = self._requests.get(self.http_url.replace('/api/generate', '/api/models'), timeout=2)
                if r.ok:
                    return r.json()
            except Exception:
                pass
        # CLI fallback
        try:
            out = subprocess.check_output([self.cli_cmd, 'list'], stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
            return out.splitlines()
        except Exception:
            return []

    def generate(self, prompt: str, model: str = "mistral", max_tokens: int = 100, timeout: int = 30, **kwargs) -> str:
        """Generate text using Ollama model.

        Tries HTTP API first, then CLI fallback.
        Returns generated text (string).
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Try HTTP
        self._ensure_requests()
        body = {
            "model": model,
            "prompt": prompt,
            "stream": False,  # Disable streaming for simpler/faster response
            "options": {
                "num_predict": max_tokens,  # Limit token generation (reduced to 150)
                "temperature": 0.3,  # Lower temperature for faster, more deterministic output
                "top_p": 0.5,  # Restrict token selection for speed
                "top_k": 20,  # Limit vocabulary for faster generation
                "repeat_penalty": 1.2,  # Discourage repetition
                "num_ctx": 512,  # Reduce context window for speed
                "stop": ["\n\n\n", "Example:", "Note:", "Additional", "Remember"]  # Stop early
            }
        }
        body.update(kwargs)
        
        import time
        start = time.time()
        logger.info(f"📡 Sending to Ollama: max_tokens={max_tokens}, temp=0.3, top_p=0.5")

        if self._requests:
            try:
                # Ollama may return chunked/streaming responses; for simplicity send as regular request
                r = self._requests.post(self.http_url, json=body, timeout=timeout)
                if r.ok:
                    try:
                        data = r.json()
                        # Ollama with stream=false returns {"response": "text"}
                        if isinstance(data, dict):
                            if 'response' in data:
                                elapsed = time.time() - start
                                logger.info(f"✅ Ollama responded in {elapsed:.2f}s")
                                return data['response']
                            if 'text' in data:
                                return data['text']
                            # sometimes 'choices' list
                            if 'choices' in data and isinstance(data['choices'], list) and data['choices']:
                                c = data['choices'][0]
                                if isinstance(c, dict) and 'content' in c:
                                    return c['content']
                                if isinstance(c, str):
                                    return c
                        # fallback to raw text
                        return r.text
                    except Exception:
                        return r.text
            except Exception:
                # fall through to CLI
                pass

        # CLI fallback: use `ollama run MODEL PROMPT` (run returns text by default)
        try:
            # Put prompt as a single argument
            cmd = [self.cli_cmd, 'run', model, prompt]
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
            # Strip ANSI escape codes from terminal output
            text = _strip_ansi_codes(out).strip()
            # Attempt to parse streaming JSON lines produced by some Ollama models
            parts = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and 'response' in obj:
                        parts.append(obj.get('response') or '')
                        continue
                except Exception:
                    # not JSON — fall back to raw line
                    pass
                parts.append(line)

            # If we parsed multiple parts, join them to produce the final text
            if parts:
                joined = ''.join(parts).strip()
                # If joined still looks like JSON fragments, try regex extraction of response fields
                if '{' in joined and '"response"' in joined:
                    try:
                        import re as _re
                        matches = _re.findall(r'"response"\s*:\s*"(.*?)"', joined)
                        if matches:
                            # unescape JSON string escapes
                            cleaned = ''.join([json.loads(f'"{m}"') for m in matches])
                            return cleaned.strip()
                    except Exception:
                        pass
                return joined
            # As a last resort, try to extract response fields from the raw text using regex
            try:
                import re as _re
                matches = _re.findall(r'"response"\s*:\s*"(.*?)"', text)
                if matches:
                    cleaned = ''.join([json.loads(f'"{m}"') for m in matches])
                    return cleaned.strip()
            except Exception:
                pass
            return text
        except Exception as e:
            return f"[Ollama run failed: {e}]"


if __name__ == '__main__':
    c = OllamaClient()
    print('Available models (sample):', c.list_models())
    print(c.generate('Say hello.', model='mistral'))