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

The URL is parsed once with :func:`urllib.parse.urlsplit` and validated
structurally before it is stored: the scheme must be ``http`` or ``https``
(case-insensitively — the stored value carries the lowercase scheme), the
authority must be present, and it must not carry userinfo, since
``https://localhost@evil.example/v1`` resolves to a different host than the
string suggests and ``user:password@host`` would smuggle credential-shaped
material into a field that must never hold secrets. Trailing slashes are
stripped so two manifests declaring the same endpoint hold identical strings.

Auth rule: this module serves first-wave providers only, so ``auth_scheme`` is
pinned to :data:`FIRST_WAVE_AUTH_SCHEME` (``"bearer"``) at construction. A
permissive rule would let a manifest declare an auth scheme no client code can
honour and fail later at request time; rejecting it here keeps failures at the
boundary. Widening the allowlist is a deliberate future change, not a silent
default.

Tuple rules: ``api_styles`` entries are stripped and lowercased and must be
non-empty and drawn from :data:`KNOWN_API_STYLES` — an unknown style is a
configuration error better caught at the boundary than at request time.
``activation_allowlist`` entries are stripped but **not** lowercased: provider
model ids are case-sensitive (spec §4), so folding case would silently break
activation matching. ``api_styles`` must contain at least one entry.

Authority rule: a manifest is *metadata*, never provider identity.
:class:`ProviderManifestRegistry` is bound to the canonical
:class:`~kernel.llm.provider_registry.ProviderRegistry` at construction and
every registration first resolves ``manifest.provider_id`` through it, so a
manifest can never introduce a provider the canonical registry does not hold.
This registry does not register providers itself: bootstrapping canonical
identity is the first-wave bootstrap's job
(:func:`kernel.llm.first_wave_providers.register_first_wave_providers`), which
registers the ``ProviderSpec`` *before* its bound manifest.

Isolation rule (MAJOR-V2-03): ``requires_isolation`` is declarative provider
policy — immutable metadata that says whether a connection for this provider may
only become ``CONNECTED`` through a CMM-owned isolation profile. It defaults to
``False`` and must be a real ``bool``: a truthy string or integer is rejected at
construction rather than coerced, so the policy can never be half-declared. It is
deliberately *not* derived from :class:`~kernel.llm.provider_connections.BillingClass`
— a subscription surface such as ``qwen-token-plan`` stays a non-isolated
provider unless its own declaration says otherwise (spec §6.3/§6.4).

Non-divergence rule (MAJOR-V2-01): metadata is stored as a binding to the exact
canonical ``ProviderSpec`` *instance* resolved at registration, and it is active
only while ``provider_registry.get(provider_id) is bound_spec``. Removing the
provider — or re-registering the same id as a different ``ProviderSpec`` object,
including through ``replace_existing=True`` — makes the metadata stale: ``get()``
returns ``None``, ``list()`` omits it, and the stale binding is purged from the
internal map on that same lookup. Identity equality by ``provider_id`` alone is
deliberately insufficient, so a re-created identity can never revive the
previous metadata. Lookups are the only purge site: there is no callback,
observer or synchronization path from ``ProviderRegistry`` into this catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from kernel.llm.exceptions import ProviderError
from kernel.llm.provider_connections import BillingClass
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

# The only auth scheme first-wave OpenAI-compatible providers use; pinned at
# construction so transport code never sees an unimplementable scheme.
FIRST_WAVE_AUTH_SCHEME: str = "bearer"

# Styles this module's client code can honour; validating against them keeps
# unsupported styles from reaching request time.
KNOWN_API_STYLES: tuple[str, ...] = ("chat_completions",)

# Hosts allowed to use plain http for local development. Compared against the
# lowercase URL host exactly, so lookalikes such as "localhost.evil.example"
# stay subject to the HTTPS rule.
_ALLOWED_HTTP_DEV_HOSTS: tuple[str, ...] = ("localhost", "127.0.0.1", "::1")


def _normalize_identifier(value: str, *, label: str) -> str:
    """Strip and lowercase an identifier; reject blank input."""
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized


def _normalize_lookup_key(value: str) -> str | None:
    """Apply the registry's canonical id normalization; None for blank input."""
    normalized = value.strip().lower()
    return normalized or None


def _normalize_tuple(value: tuple[str, ...], *, label: str) -> tuple[str, ...]:
    """Coerce to a tuple of stripped entries; reject blanks (bare str = one item)."""
    # A bare string is a sequence of characters, so coerce it into a
    # single-element tuple rather than iterating its characters.
    normalized = (value,) if isinstance(value, str) else tuple(value)
    if any(not item.strip() for item in normalized):
        raise ValueError(f"{label} cannot contain empty values")
    return tuple(item.strip() for item in normalized)


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
    requires_isolation: bool = False

    def __post_init__(self) -> None:
        """Normalize every field and reject invalid manifests at construction."""
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

        api_styles = tuple(
            style.strip().lower()
            for style in _normalize_tuple(self.api_styles, label="api_styles")
        )
        if not api_styles:
            raise ValueError("api_styles cannot be empty")
        unsupported = [style for style in api_styles if style not in KNOWN_API_STYLES]
        if unsupported:
            raise ValueError(
                f"unsupported api_styles entry: {unsupported[0]!r} "
                f"(known: {', '.join(KNOWN_API_STYLES)})"
            )
        object.__setattr__(self, "api_styles", api_styles)

        # Deliberately not lowercased: provider model ids are case-sensitive.
        object.__setattr__(
            self,
            "activation_allowlist",
            _normalize_tuple(self.activation_allowlist, label="activation_allowlist"),
        )

        # Declarative policy, never a derived or coerced value: a truthy string
        # would silently declare isolation for the wrong reason.
        if not isinstance(self.requires_isolation, bool):
            raise TypeError("requires_isolation must be a bool")

    @staticmethod
    def _validated_base_url(value: str) -> str:
        """Return the normalized URL, enforcing the documented HTTPS rule."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("default_base_url cannot be empty")

        parts = urlsplit(normalized)
        scheme = parts.scheme.lower()
        # A URL with no authority at all ("http:localhost/v1", "http:/localhost/v1")
        # is malformed, not a localhost target: reject it under the same
        # documented HTTPS rule rather than reporting a separate host error.
        if not parts.netloc or scheme not in ("http", "https"):
            raise ValueError(
                "default_base_url must use https (http is allowed only for "
                "localhost, 127.0.0.1 or ::1)"
            )
        if parts.username is not None or parts.password is not None:
            raise ValueError(
                "default_base_url cannot contain userinfo (user:password@host)"
            )
        hostname = parts.hostname or ""
        if scheme == "http" and hostname not in _ALLOWED_HTTP_DEV_HOSTS:
            raise ValueError(
                "default_base_url must use https (http is allowed only for "
                "localhost, 127.0.0.1 or ::1)"
            )

        # Store the lowercase scheme so manifests declaring the same endpoint
        # hold identical strings regardless of the case they were declared in.
        prefix = normalized[: len(parts.scheme)]
        return (scheme + normalized[len(prefix) :]).rstrip("/")


@dataclass(frozen=True, slots=True)
class _ManifestBinding:
    """One manifest together with the canonical instance it was bound to."""

    provider: ProviderSpec
    manifest: ProviderManifest


class ProviderManifestRegistry:
    """Provider-bound metadata catalog; never a second provider inventory.

    The catalog is keyed by normalized provider id, but its authority is the
    canonical :class:`ProviderRegistry` it was constructed with: a manifest
    whose provider is absent there is rejected with the canonical registry's
    ``ProviderError``. Each entry additionally remembers the exact
    ``ProviderSpec`` instance it was registered against, and only that instance
    keeps the entry active (module docstring, MAJOR-V2-01). That makes
    divergence structurally impossible rather than merely discouraged — there
    is no API here that can create provider identity, and no synchronization
    path against a second authority.
    """

    def __init__(self, provider_registry: ProviderRegistry) -> None:
        """Bind the catalog to the canonical provider authority."""
        if not isinstance(provider_registry, ProviderRegistry):
            raise TypeError("provider_registry must be a ProviderRegistry")
        self._provider_registry = provider_registry
        self._items: dict[str, _ManifestBinding] = {}

    @property
    def provider_registry(self) -> ProviderRegistry:
        """Return the canonical authority this metadata catalog is bound to."""
        return self._provider_registry

    def register(self, manifest: ProviderManifest) -> ProviderManifest:
        """Store ``manifest`` bound to its canonical provider; reject duplicates.

        The provider must already exist in the bound canonical registry:
        metadata never creates provider identity (MAJOR-01). Raises the
        canonical ``ProviderError`` for an unregistered provider and
        ``ValueError`` for a duplicate manifest — where "duplicate" means an
        entry that is *still active*. A stale entry (its bound provider was
        removed or replaced) is purged here instead of blocking the id, so a
        re-created provider identity can take fresh metadata while the previous
        manifest stays permanently dead.
        """
        provider = self._provider_registry.get(manifest.provider_id)
        key = manifest.provider_id
        if self._active_manifest(key) is not None:
            raise ValueError(f"duplicate provider_id: {key}")
        self._items[key] = _ManifestBinding(provider=provider, manifest=manifest)
        return manifest

    def get(self, provider_id: str) -> ProviderManifest | None:
        """Look up by normalized id; unknown, blank or stale ids return ``None``."""
        key = _normalize_lookup_key(provider_id)
        if key is None:
            return None
        return self._active_manifest(key)

    def list(self, provider_id: str | None = None) -> tuple[ProviderManifest, ...]:
        """Return active manifests sorted by id, optionally filtered by provider."""
        # Iterating a snapshot of the keys keeps the lazy purge performed by
        # ``_active_manifest`` safe to run inside this comprehension.
        values = tuple(
            manifest
            for key in sorted(self._items)
            if (manifest := self._active_manifest(key)) is not None
        )
        if provider_id is None:
            return values
        wanted = _normalize_lookup_key(provider_id)
        return tuple(m for m in values if m.provider_id == wanted)

    def _active_manifest(self, provider_id: str) -> ProviderManifest | None:
        """Return the manifest while its bound provider is still canonical.

        ``provider_id`` is already normalized. A missing provider, or a
        canonical entry that is a different object than the bound one, drops
        the stale binding and reports ``None``.
        """
        binding = self._items.get(provider_id)
        if binding is None:
            return None
        try:
            current = self._provider_registry.get(provider_id)
        except ProviderError:
            self._items.pop(provider_id, None)
            return None
        if current is not binding.provider:
            self._items.pop(provider_id, None)
            return None
        return binding.manifest
