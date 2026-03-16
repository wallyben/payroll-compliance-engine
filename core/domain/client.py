from __future__ import annotations

from pydantic import BaseModel

_client_store: dict[str, "Client"] = {}


class Client(BaseModel):
    client_id: str
    client_name: str
    payroll_frequency: str
    jurisdiction: str


def create_client(
    client_id: str,
    client_name: str,
    payroll_frequency: str,
    jurisdiction: str,
) -> Client:
    """Create and register a client in the in-memory store."""
    client = Client(
        client_id=client_id,
        client_name=client_name,
        payroll_frequency=payroll_frequency,
        jurisdiction=jurisdiction,
    )
    _client_store[client_id] = client
    return client


def _clear_clients() -> None:
    """Reset the client store — for testing only."""
    _client_store.clear()
