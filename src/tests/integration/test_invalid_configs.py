from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import ConfigValidationError
from src.routes.loader import load_route_file


def test_invalid_route_config_duplicate_codes(tmp_path: Path) -> None:
    path = tmp_path / "routes.yaml"
    path.write_text(
        (
            "version: 1\n"
            "routes:\n"
            "  - code: dup\n"
            "    public_path_prefix: /a/\n"
            "    upstream_path_prefix: /a/\n"
            "    methods: [GET]\n"
            "    policy_code: default\n"
            "  - code: dup\n"
            "    public_path_prefix: /b/\n"
            "    upstream_path_prefix: /b/\n"
            "    methods: [GET]\n"
            "    policy_code: default\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigValidationError):
        load_route_file(path)
