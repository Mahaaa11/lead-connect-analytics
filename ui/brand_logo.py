"""Lead & Connect official logo asset."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "lead_connect_logo.png"


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    if not LOGO_PATH.is_file():
        raise FileNotFoundError(f"Logo introuvable : {LOGO_PATH}")
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def logo_img_html(*, css_class: str = "lc-logo-img", max_width: str = "300px") -> str:
    return (
        f'<img src="{logo_data_uri()}" alt="Lead &amp; Connect" '
        f'class="{css_class}" style="max-width:{max_width};width:100%;height:auto;" />'
    )
