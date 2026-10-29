from __future__ import annotations

from pydantic import BaseModel


class ReloadConfigResponse(BaseModel):
    reloaded: bool
