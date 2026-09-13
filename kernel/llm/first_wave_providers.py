"""First-wave provider manifests for the Provider Registry.

This module is pure declaration: it holds the transport/auth/billing defaults
for the eight approved first-wave OpenAI-compatible providers (spec §2, plan
Task 3) and registers them into a :class:`ProviderManifestRegistry`. Nothing
here performs network I/O, and no credential material — not a key, not a token,
not a keychain reference — appears in a manifest: secrets live in native secret
storage and are referenced by accepted connections (see
``kernel.llm.provider_connections``).

Base URLs are the providers' documented public OpenAI-compatible endpoints. A
manifest carries no per-provider subclass and no model catalog: model ids are
only knowable from a live ``/models`` response, so runtime discovery remains the
authoritative catalog (spec §7) and no provider model id is hardcoded here.

``activation_allowlist`` is empty for every first-wave provider. That is a
deliberate policy, not an omission:

* Activation is discovery-driven by default. A non-empty allowlist narrows
  routing to explicitly approved provider model ids, which requires an id that
  has actually been observed.
* NVIDIA NIM's approved scope starts at Kimi K3, but its provider model id is
  only knowable from a live ``/models`` call. This plan performs no live calls,
  so the allowlist stays empty and NVIDIA activation defaults to manual
  approval. Inventing an id would silently activate a route that no discovery
  result could confirm.

Billing classes follow spec §2 exactly, including the mandatory separation of
``qwen-token-plan`` (subscription) from ``qwen-cloud`` (PAYG): identical models
may be exposed by both, but they must remain distinct providers so quota and
account state can never be shared implicitly (spec §13).

Error taxonomy: this module raises :class:`ValueError` for every configuration
error it detects directly — a blank registry, a blank or duplicate provider id,
and a failed cross-manifest invariant — mirroring
:mod:`kernel.llm.provider_manifests`, whose validator raises ``ValueError`` for
malformed field values. Invalid field values never reach this module's code
paths: the :class:`ProviderManifest` constructor rejects them at the boundary.
"""

from __future__ import annotations

from kernel.llm.provider_connections import BillingClass
from kernel.llm.provider_manifests import (
    FIRST_WAVE_AUTH_SCHEME,
    ProviderManifest,
    ProviderManifestRegistry,
)

# Documented public OpenAI-compatible endpoints, keyed by provider id. Values
# are canonical (lowercase scheme, no trailing slash) so the validator's
# trailing-slash normalization is a no-op rather than a silent rewrite.
QWEN_TOKEN_PLAN_BASE_URL: str = (
    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
)
COMMANDCODE_BASE_URL: str = "https://api.commandcode.ai/v1"
QWEN_CLOUD_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
# Pinned by the plan's global constraints and spec §2; bearer auth.
KIRA_BASE_URL: str = "https://kiraai.vn/api/v1"
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
OPENCODE_ZEN_BASE_URL: str = "https://opencode.ai/zen/v1"
NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

# Declared in plan order (plan Task 3, spec §2). Registration is order-free —
# the registry sorts by id — but tests compare the returned tuple against this
# order, so it is part of the contract.
_FIRST_WAVE_MANIFESTS: tuple[ProviderManifest, ...] = (
    ProviderManifest(
        provider_id="qwen-token-plan",
        display_name="Qwen Token Plan",
        billing_class=BillingClass.SUBSCRIPTION,
        default_base_url=QWEN_TOKEN_PLAN_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="commandcode",
        display_name="CommandCode API",
        billing_class=BillingClass.API,
        default_base_url=COMMANDCODE_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="qwen-cloud",
        display_name="Qwen Cloud PAYG",
        billing_class=BillingClass.PAYG,
        default_base_url=QWEN_CLOUD_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="deepseek",
        display_name="DeepSeek API",
        billing_class=BillingClass.PAYG,
        default_base_url=DEEPSEEK_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="kira",
        display_name="Kira AI",
        billing_class=BillingClass.FREE_OR_API,
        default_base_url=KIRA_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="openrouter",
        display_name="OpenRouter",
        billing_class=BillingClass.API,
        default_base_url=OPENROUTER_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="opencode-zen",
        display_name="OpenCode Zen",
        billing_class=BillingClass.FREE_OR_API,
        default_base_url=OPENCODE_ZEN_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
    ProviderManifest(
        provider_id="nvidia-nim",
        display_name="NVIDIA NIM",
        billing_class=BillingClass.FREE_OR_API,
        default_base_url=NVIDIA_NIM_BASE_URL,
        auth_scheme=FIRST_WAVE_AUTH_SCHEME,
    ),
)


def _validated_manifests() -> tuple[ProviderManifest, ...]:
    """Return the declared manifests after checkable invariants hold."""
    if not _FIRST_WAVE_MANIFESTS:
        raise ValueError("first-wave manifests cannot be empty")

    provider_ids = tuple(manifest.provider_id for manifest in _FIRST_WAVE_MANIFESTS)
    if any(not provider_id for provider_id in provider_ids):
        raise ValueError("provider_id cannot be empty")
    if len(set(provider_ids)) != len(provider_ids):
        raise ValueError("duplicate provider_id in first-wave manifests")

    # Subscription and PAYG surfaces of the same vendor must never collapse into
    # one provider: shared quota/account state would follow implicitly (spec §13).
    if "qwen-token-plan" not in provider_ids or "qwen-cloud" not in provider_ids:
        raise ValueError(
            "qwen-token-plan and qwen-cloud must both be registered as "
            "separate providers"
        )

    return _FIRST_WAVE_MANIFESTS


def register_first_wave_manifests(
    registry: ProviderManifestRegistry,
) -> tuple[ProviderManifest, ...]:
    """Register every approved first-wave manifest into ``registry``.

    Returns the manifests in declaration order (plan Task 3, spec §2), so callers
    can render them deterministically without re-sorting. Raises ``ValueError``
    for a blank or duplicate provider id, for a missing Qwen subscription/PAYG
    pair, and for whatever the registry itself rejects (an already-registered
    provider id).
    """
    manifests = _validated_manifests()
    for manifest in manifests:
        registry.register(manifest)
    return manifests
