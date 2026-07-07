"""Real featured-image generation via SDXL served on the AMD MI300X (ROCm).

Calls a tiny HTTP endpoint (POST /generate {prompt} -> {image_base64}) with
stdlib urllib. Returns a data: URI ready to drop into an <img src>. Best-effort:
returns None on any failure so the pipeline falls back to the placeholder.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional

from . import live


def available() -> bool:
    return live.image_available()


def generate(prompt: str, width: int = 1024, height: int = 576,
             steps: int = 3) -> Optional[str]:
    """Return a data:image/png;base64 URI, or None on failure."""
    try:
        url = live.amd_image_url().rstrip("/") + "/generate"
        headers = {"Content-Type": "application/json"}
        key = live.amd_api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {"prompt": prompt, "width": width, "height": height, "steps": steps}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        b64 = data.get("image_base64")
        return f"data:image/png;base64,{b64}" if b64 else None
    except Exception:
        return None
