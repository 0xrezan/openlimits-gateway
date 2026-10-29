from __future__ import annotations

from src.core.app_factory import create_app
from src.settings import get_settings

app = create_app(get_settings())
