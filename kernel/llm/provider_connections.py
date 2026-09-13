from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum


def _normalize_identifier(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized


class BillingClass(str, Enum):
    SUBSCRIPTION = "subscription"
    PAYG = "payg"
    API = "api"
    FREE_OR_API = "free_or_api"

class ConnectionStatus(str, Enum):
    DETECTED = "detected"
    CONNECTED = "connected"
    AUTH_REQUIRED = "auth_required"
    WARNING = "warning"
    UNAVAILABLE = "unavailable"

@dataclass(frozen=True, slots=True)
class ProviderConnection:
    connection_id: str
    provider_id: str
    display_name: str
    billing_class: BillingClass
    credential_ref: str | None
    endpoint: str
    isolation_profile_ref: str | None
    status: ConnectionStatus
    created_at: datetime | None = None
    last_validated_at: datetime | None = None

    def __post_init__(self) -> None:
        normalized_provider_id = _normalize_identifier(
            self.provider_id, label="Provider id"
        )
        object.__setattr__(self, "provider_id", normalized_provider_id)

        normalized_endpoint = self.endpoint.strip()
        if not normalized_endpoint:
            raise ValueError("endpoint cannot be empty")
        object.__setattr__(self, "endpoint", normalized_endpoint)

        if self.credential_ref is not None:
            ref = self.credential_ref.strip()
            lowered = ref.lower()
            if lowered.startswith(("sk-", "api-key", "password=")):
                raise ValueError(
                    "credential_ref must not contain plaintext secrets"
                )
            object.__setattr__(self, "credential_ref", ref)

        if self.credential_ref is not None and not self.credential_ref.startswith("keychain://"):
            raise ValueError(
                "credential_ref must use a secure ref scheme such as keychain://"
            )

class ProviderConnectionRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ProviderConnection] = {}

    def register(self, connection: ProviderConnection) -> ProviderConnection:
        key = connection.connection_id.strip()
        if not key:
            raise ValueError("connection_id cannot be empty")
        if key in self._items:
            raise ValueError(f"duplicate connection_id: {key}")
        self._items[key] = connection
        return connection

    def get(self, connection_id: str) -> ProviderConnection | None:
        return self._items.get(connection_id)

    def list(self, provider_id: str | None = None) -> tuple[ProviderConnection, ...]:
        values = tuple(self._items.values())
        if provider_id is None:
            return values
        return tuple(v for v in values if v.provider_id == provider_id)

    def update_status(
        self,
        connection_id: str,
        status: ConnectionStatus,
        *,
        validated_at: datetime | None = None,
    ) -> ProviderConnection:
        current = self._items[connection_id]
        updated = replace(
            current,
            status=status,
            last_validated_at=validated_at or current.last_validated_at,
        )
        self._items[connection_id] = updated
        return updated
