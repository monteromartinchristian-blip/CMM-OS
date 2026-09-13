"""Declarative provider manifests for the Provider Registry.

A manifest declares the transport, auth and billing defaults for one
OpenAI-compatible provider. Manifests never carry credential material: secrets
stay in native secret storage and are referenced by accepted connections (see
``kernel.llm.provider_connections``).

Base-URL rule (narrow by design): ``default_base_url`` must use ``https``
unless the host is a local development target — ``localhost``, ``127.0.0.1`` or
``::1`` may use plain ``http`` so a locally hosted custom provider can be
registered. No other host, scheme or "development mode" flag relaxes the rule,
so a public endpoint can never be downgraded to cleartext by mistake.

Auth rule: this module serves first-wave providers only, so ``auth_scheme`` is
pinned to :data:`FIRST_WAVE_AUTH_SCHEME` (``"bearer"``) at construction. A
permissive rule would let a manifest declare an auth scheme no client code can
honour and fail later at request time; rejecting it here keeps failures at the
boundary. Widening the allowlist is a deliberate future change, not a silent
default.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from kernel.llm.provider_connections import BillingClass

# The only auth scheme first-wave OpenAI-compatible providers use; pinned at
# construction so transport code never sees an unimplementable scheme.
FIRST_WAVE_AUTH_SCHEME: str = "bearer"

# Hosts allowed to use plain http for local development. Compared against the
# lowercase URL host exactly, so lookalikes such as "localhost.evil.example"
# stay subject to the HTTPS rule.
_ALLOWED_HTTP_DEV_HOSTS: tuple[str, ...] = ("localhost", "127.0.0.1", "::1")


def _normalize_identifier(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized


def _normalize_lookup_key(value: str) -> str | None:
    """Apply the registry's canonical id normalization; None for blank input."""
    normalized = value.strip().lower()
    return normalized or None


def _normalize_tuple(value: tuple[str, ...], *, label: str) -> tuple[str, ...]:
    # A bare string is a sequence of characters, so coerce it into a
    # single-element tuple rather than iterating its characters.
    normalized = (value,) if isinstance(value, str) else tuple(value)
    if any(not item.strip() for item in normalized):
        raise ValueError(f"{label} cannot contain empty values")
    return normalized


@dataclass(frozen=True, slots=True)
class ProviderManifest:
    """Declared transport/auth/billing defaults for one provider; no secrets."""

    provider_id: str
    display_name: str
    billing_class: BillingClass
    default_base_url: str
    auth_scheme: str
    models_path: str = "/models"
    api_styles: tuple[str, ...] = ("chat_completions",)
    activation_allowlist: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider_id",
            _normalize_identifier(self.provider_id, label="Provider id"),
        )
        if not self.display_name.strip():
            raise ValueError("display_name cannot be empty")
        object.__setattr__(self, "display_name", self.display_name.strip())

        # Coerce enum-typed fields so bare strings cannot enter the inventory
        # through dataclasses.replace()-based mutation paths.
        object.__setattr__(self, "billing_class", BillingClass(self.billing_class))

        object.__setattr__(
            self,
            "default_base_url",
            self._validated_base_url(self.default_base_url),
        )

        scheme = self.auth_scheme.strip().lower()
        if scheme != FIRST_WAVE_AUTH_SCHEME:
            raise ValueError(
                f"auth_scheme must be '{FIRST_WAVE_AUTH_SCHEME}' for "
                "first-wave manifests"
            )
        object.__setattr__(self, "auth_scheme", scheme)

        models_path = self.models_path.strip()
        if not models_path:
            raise ValueError("models_path cannot be empty")
        if not models_path.startswith("/"):
            raise ValueError("models_path must be absolute")
        object.__setattr__(self, "models_path", models_path)

        object.__setattr__(
            self,
            "api_styles",
            _normalize_tuple(self.api_styles, label="api_styles"),
        )
        object.__setattr__(
            self,
            "activation_allowlist",
            _normalize_tuple(self.activation_allowlist, label="activation_allowlist"),
        )

    @staticmethod
    def _validated_base_url(value: str) -> str:
        """Return the stripped URL, enforcing the documented HTTPS rule."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("default_base_url cannot be empty")
        if normalized.startswith("https://"):
            return normalized
        if (
            normalized.startswith("http://")
            and (urlsplit(normalized).hostname or "") in _ALLOWED_HTTP_DEV_HOSTS
        ):
            return normalized
        raise ValueError(
            "default_base_url must use https (http is allowed only for "
            "localhost, 127.0.0.1 or ::1)"
        )


class ProviderManifestRegistry:
    """In-memory catalog of provider manifests, keyed by normalized id."""

    def __init__(self) -> None:
        self._items: dict[str, ProviderManifest] = {}

    def register(self, manifest: ProviderManifest) -> ProviderManifest:
        """Store ``manifest`` under its normalized id; reject duplicates."""
        key = manifest.provider_id
        if key in self._items:
            raise ValueError(f"duplicate provider_id: {key}")
        self._items[key] = manifest
        return manifest

    def get(self, provider_id: str) -> ProviderManifest | None:
        """Look up by normalized id; unknown or blank ids return ``None``."""
        key = _normalize_lookup_key(provider_id)
        if key is None:
            return None
        return self._items.get(key)

    def list(self, provider_id: str | None = None) -> tuple[ProviderManifest, ...]:
        """Return manifests sorted by id, optionally filtered by provider."""
        values = tuple(self._items[key] for key in sorted(self._items))
        if provider_id is None:
            return values
        wanted = _normalize_lookup_key(provider_id)
        return tuple(m for m in values if m.provider_id == wanted)
