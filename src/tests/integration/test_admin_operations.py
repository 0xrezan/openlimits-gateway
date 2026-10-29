from __future__ import annotations

from pathlib import Path

import yaml

from src.api.admin import _write_yaml_atomically


def test_admin_config_write_is_atomic(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    _write_yaml_atomically(path, {"version": 1, "policies": [{"code": "default"}]})
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["policies"][0]["code"] == "default"
