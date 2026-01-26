import time
from typing import Optional

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

_CACHE = {}


def _load_model(model_name: str = "google/flan-t5-small", device: Optional[str] = None):
    key = (model_name, device)
    if key in _CACHE:
        return _CACHE[key]
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model.to(device)
    _CACHE[key] = (tokenizer, model, device)
    return tokenizer, model, device


def rewrite_steps(text: str,
                  model_name: str = "google/flan-t5-small",
                  device: Optional[str] = None,
                  max_length: int = 512,
                  num_beams: int = 4,
                  temperature: float = 0.0) -> str:
    """Rewrite arbitrary generated text into a concise, numbered, imperative list.

    Returns the rewritten text (string) ready for step extraction.
    """
    tokenizer, model, device = _load_model(model_name, device)
    prompt = (
        "Rewrite the following UI instructions into a concise, numbered, imperative list. "
        "Keep each step short and actionable. Preserve order if present.\n\n"
        f"Input:\n{text}\n\nNumbered steps:\n"
    )
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_length)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_length=max_length,
            num_beams=num_beams,
            temperature=temperature,
            early_stopping=True,
        )
    decoded = tokenizer.decode(out[0], skip_special_tokens=True)
    return decoded.strip()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        txt = " ".join(sys.argv[1:])
    else:
        txt = "Open the app and go to settings."
    t0 = time.time()
    print(rewrite_steps(txt))
    print(f"rewritten in {time.time()-t0:.2f}s")
