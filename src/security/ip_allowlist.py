from __future__ import annotations

from ipaddress import ip_address, ip_network


def ip_allowed(client_ip: str | None, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    if client_ip is None:
        return False
    address = ip_address(client_ip)
    return any(address in ip_network(network) for network in allowlist)
