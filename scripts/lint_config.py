from __future__ import annotations

from src.routes.loader import load_limit_file, load_policy_file, load_route_file
from src.settings import get_settings


def main() -> None:
    settings = get_settings()
    load_route_file(settings.route_config)
    load_policy_file(settings.policy_config)
    load_limit_file(settings.limit_config)
    print("Config is valid.")


if __name__ == "__main__":
    main()
