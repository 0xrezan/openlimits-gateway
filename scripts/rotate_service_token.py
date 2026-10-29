from __future__ import annotations

import secrets


def main() -> None:
    token = secrets.token_urlsafe(32)
    print("New upstream service token:")
    print(token)
    print("Update GATEWAY_UPSTREAM_SERVICE_TOKEN and the trusted main backend allowlist.")


if __name__ == "__main__":
    main()
