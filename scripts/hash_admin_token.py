from __future__ import annotations

import getpass

from src.auth.hashing import hash_api_key


def main() -> None:
    token = getpass.getpass("Admin token: ").strip()
    if not token:
        raise SystemExit("Token must not be empty.")
    print(hash_api_key(token))


if __name__ == "__main__":
    main()
