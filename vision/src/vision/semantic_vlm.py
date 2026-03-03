import hashlib
import os
import tempfile
from typing import Dict, Optional

import cv2
import numpy as np

_SEMANTIC_CACHE: Dict[str, str] = {}


def _hash_image(crop: np.ndarray, label: str, type_hint: str) -> str:
    h = hashlib.sha256()
    h.update(crop.tobytes())
    h.update(label.encode("utf-8", errors="ignore"))
    h.update(type_hint.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _fallback_description(label: str, type_hint: str) -> str:
    human_type = (type_hint or "ui element").replace("_", " ").strip()
    if label:
        if human_type in {"button", "link", "tab"}:
            return f"Interactive {human_type} labeled '{label}', likely used for navigation or action."
        if human_type in {"input field", "dropdown", "checkbox"}:
            return f"{human_type.capitalize()} for '{label}', likely part of user input flow."
        return f"{human_type.capitalize()} showing '{label}' in the current interface."
    return f"{human_type.capitalize()} detected in this screen and likely relevant to user interaction."


def describe_ui_element(
    vlm_client,
    crop: np.ndarray,
    label: str = "",
    type_hint: str = "unknown",
) -> str:
    if crop is None or crop.size == 0:
        return _fallback_description(label, type_hint)

    key = _hash_image(crop, label, type_hint)
    if key in _SEMANTIC_CACHE:
        return _SEMANTIC_CACHE[key]

    if vlm_client is None:
        desc = _fallback_description(label, type_hint)
        _SEMANTIC_CACHE[key] = desc
        return desc

    prompt = (
        "Describe this UI element and its likely function in one concise sentence. "
        "Mention visible text if present and explain likely action or role."
    )
    desc = ""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        temp_path = tmp.name
    try:
        cv2.imwrite(temp_path, crop)
        result = vlm_client.analyze_ui(temp_path, prompt=prompt)
        if result and result.parse_successful and result.elements:
            desc = str(result.elements[0].description or "").strip()
    except Exception:
        desc = ""
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

    if not desc:
        desc = _fallback_description(label, type_hint)
    _SEMANTIC_CACHE[key] = desc
    return desc
