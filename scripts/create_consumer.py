from __future__ import annotations

import argparse
import asyncio

from src.bootstrap import create_container
from src.settings import get_settings


async def _run(args: argparse.Namespace) -> None:
    container = await create_container(get_settings())
    try:
        async with container.uow() as uow:
            consumer = await uow.consumers.create(
                name=args.name,
                description=args.description,
                allowed_ips=args.allowed_ip or [],
                metadata_json={},
            )
            issued = None
            if args.issue_key:
                issued = await container.key_service.issue_key(
                    uow,
                    consumer_id=consumer.id,
                    name="bootstrap",
                    scopes=[],
                    expires_at=None,
                )
        print(f"consumer_id={consumer.id}")
        if issued is not None:
            print(f"api_key={issued.api_key}")
    finally:
        await container.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a gateway consumer.")
    parser.add_argument("name")
    parser.add_argument("--description")
    parser.add_argument("--allowed-ip", action="append")
    parser.add_argument("--issue-key", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
