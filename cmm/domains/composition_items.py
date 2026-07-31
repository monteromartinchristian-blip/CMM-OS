"""Phase 10.8 – Composition Items.

Deterministic item/provenance composition, exact-reference deduplication,
effective reasoning profile, and presentation composition helpers.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from cmm.domains.composition_contracts import (
    DomainCompositionConflict,
    DomainCompositionDecision,
    DomainCompositionItem,
    DomainCompositionPolicy,
    EffectiveReasoningProfile,
    PresentationComposition,
)
from cmm.domains.contracts import DomainCapability, DomainDefinition
from cmm.domains.enums import DomainConflictPolicy
from cmm.domains.errors import DomainCompositionContractError
from cmm.domains.identifiers import DomainId

# ═══════════════════════════════════════════════════════════════════════════════
# Exact-reference item composition
# ═══════════════════════════════════════════════════════════════════════════════


def compose_reference_items(
    *,
    category: str,
    definitions: tuple[DomainDefinition, ...],
    value_getter: Callable[[DomainDefinition], tuple[str, ...]],
) -> tuple[tuple[DomainCompositionItem, ...], tuple[DomainCompositionDecision, ...]]:
    """Compose exact-reference items with deterministic ordering and provenance.

    definitions must be ordered: primary first, then supporting in resolver order.
    """
    if not definitions:
        return (), ()

    # Map: identifier -> {domain slugs, primary_contributor, precedence}
    seen: dict[str, tuple[set[str], str, int]] = {}
    all_domains: list[DomainId] = []
    for d in definitions:
        all_domains.append(d.id)

        domain_order = {d.id.slug: i for i, d in enumerate(definitions)}

    for defn in definitions:
        values = value_getter(defn)
        for idx, val in enumerate(values):
            if val in seen:
                slugs_set, primary_slug, _existing_prec = seen[val]
                slugs_set.add(defn.id.slug)
                # Keep first contributor as primary
            else:
                # First time: primary contributor is this domain
                # precedence = domain_order * 1000 + index for stable ordering
                precedence = domain_order[defn.id.slug] * 10000 + idx
                seen[val] = ({defn.id.slug}, defn.id.slug, precedence)

    items: list[DomainCompositionItem] = []
    decisions: list[DomainCompositionDecision] = []

    for identifier in sorted(seen.keys()):
        slugs_set, primary_slug, precedence = seen[identifier]
        # Build ordered contributing_domains matching definition order
        sorted_domains = sorted(slugs_set, key=lambda s: domain_order.get(s, 9999))

        contributing_domains = tuple(
            DomainId.from_str(f"domain:{s}") for s in sorted_domains
        )

        item = DomainCompositionItem(
            category=category,
            identifier=identifier,
            contributing_domains=contributing_domains,
            primary_contributor=DomainId.from_str(f"domain:{primary_slug}"),
            precedence=precedence,
        )
        items.append(item)

        if len(slugs_set) > 1:
            decisions.append(
                DomainCompositionDecision(
                    code="DOMAIN_COMPOSITION_DUPLICATE_COLLAPSED",
                    category=category,
                    identifier=identifier,
                    action="collapsed",
                    domains=contributing_domains,
                    reason=f"Duplicate {category} identifier collapsed from {len(slugs_set)} domains",
                    blocking=False,
                )
            )

    # Sort items deterministically: precedence asc, category, identifier
    items.sort(key=lambda x: (x.precedence, x.category, x.identifier))

    return tuple(items), tuple(decisions)


# ═══════════════════════════════════════════════════════════════════════════════
# Capabilities composition
# ═══════════════════════════════════════════════════════════════════════════════


def _capability_key(cap: DomainCapability) -> str:
    """Stable canonical key for a capability: capability:<kind>:<name>:<version>."""
    return f"capability:{cap.kind}:{cap.name}:{cap.version}"


def compose_capability_items(
    definitions: tuple[DomainDefinition, ...],
) -> tuple[tuple[DomainCompositionItem, ...], tuple[DomainCompositionDecision, ...]]:
    """Compose capability items with deduplication by (kind, name, version)."""
    if not definitions:
        return (), ()

    seen: dict[str, tuple[set[str], str, int]] = {}
    domain_order = {d.id.slug: i for i, d in enumerate(definitions)}

    for defn in definitions:
        for idx, cap in enumerate(defn.capabilities):
            key = _capability_key(cap)
            if key in seen:
                slugs_set, primary_slug, _existing_prec = seen[key]
                slugs_set.add(defn.id.slug)
            else:
                precedence = domain_order[defn.id.slug] * 10000 + idx
                seen[key] = ({defn.id.slug}, defn.id.slug, precedence)

    items: list[DomainCompositionItem] = []
    decisions: list[DomainCompositionDecision] = []

    for key in sorted(seen.keys()):
        slugs_set, primary_slug, precedence = seen[key]
        sorted_domains = sorted(slugs_set, key=lambda s: domain_order.get(s, 9999))
        contributing_domains = tuple(
            DomainId.from_str(f"domain:{s}") for s in sorted_domains
        )

        items.append(
            DomainCompositionItem(
                category="capabilities",
                identifier=key,
                contributing_domains=contributing_domains,
                primary_contributor=DomainId.from_str(f"domain:{primary_slug}"),
                precedence=precedence,
            )
        )

        if len(slugs_set) > 1:
            decisions.append(
                DomainCompositionDecision(
                    code="DOMAIN_COMPOSITION_DUPLICATE_COLLAPSED",
                    category="capabilities",
                    identifier=key,
                    action="collapsed",
                    domains=contributing_domains,
                    reason=f"Duplicate capability collapsed from {len(slugs_set)} domains",
                    blocking=False,
                )
            )

    items.sort(key=lambda x: (x.precedence, x.category, x.identifier))
    return tuple(items), tuple(decisions)


# ═══════════════════════════════════════════════════════════════════════════════
# Effective reasoning profile composition
# ═══════════════════════════════════════════════════════════════════════════════


def compose_reasoning_profile(
    definitions: tuple[DomainDefinition, ...],
) -> tuple[EffectiveReasoningProfile, tuple[DomainCompositionDecision, ...]]:
    """Compose an effective reasoning profile from primary and supporting domains."""
    if not definitions:
        return (
            EffectiveReasoningProfile(base_profile=None),
            (),
        )

    primary = definitions[0]
    supporting = definitions[1:] if len(definitions) > 1 else ()

    base_profile = primary.reasoning_profile or None

    contributing_profiles: list[str] = []
    contributing_domains: list[DomainId] = [primary.id]
    added_rules: set[str] = set()
    required_rules: set[str] = set()
    prohibited_actions: set[str] = set()
    min_confidence: float | None = None
    max_inference_depth: int | None = None
    max_questions: int | None = None
    decisions: list[DomainCompositionDecision] = []

    # Extract structured metadata from primary
    rp_meta = _get_reasoning_profile_metadata(primary)
    if rp_meta is not None:
        min_confidence = _extract_float_max(
            rp_meta, "minimum_confidence", fields_checked=set()
        )
        max_inference_depth = _extract_int_min(rp_meta, "maximum_inference_depth")
        max_questions = _extract_int_min(rp_meta, "maximum_questions_per_turn")
        for rule in rp_meta.get("added_rules", ()):
            if isinstance(rule, str):
                added_rules.add(rule)
        for rule in rp_meta.get("required_rules", ()):
            if isinstance(rule, str):
                required_rules.add(rule)
        for action in rp_meta.get("prohibited_actions", ()):
            if isinstance(action, str):
                prohibited_actions.add(action)

    # Process supporting domains
    for sup_def in supporting:
        if sup_def.reasoning_profile:
            profile_id = sup_def.reasoning_profile
            if profile_id not in contributing_profiles:
                contributing_profiles.append(profile_id)
        if sup_def.id.slug not in {d.slug for d in contributing_domains}:
            contributing_domains.append(sup_def.id)

        rp_meta = _get_reasoning_profile_metadata(sup_def)
        if rp_meta is not None:
            sup_conf = _extract_float_value(rp_meta, "minimum_confidence")
            if sup_conf is not None and (
                min_confidence is None or sup_conf > min_confidence
            ):
                min_confidence = sup_conf

            sup_depth = _extract_int_value(rp_meta, "maximum_inference_depth")
            if sup_depth is not None and (
                max_inference_depth is None or sup_depth < max_inference_depth
            ):
                max_inference_depth = sup_depth

            sup_questions = _extract_int_value(rp_meta, "maximum_questions_per_turn")
            if sup_questions is not None and (
                max_questions is None or sup_questions < max_questions
            ):
                max_questions = sup_questions

            for rule in rp_meta.get("added_rules", ()):
                if isinstance(rule, str):
                    added_rules.add(rule)
            for rule in rp_meta.get("required_rules", ()):
                if isinstance(rule, str):
                    required_rules.add(rule)
            for action in rp_meta.get("prohibited_actions", ()):
                if isinstance(action, str):
                    prohibited_actions.add(action)

    profile = EffectiveReasoningProfile(
        base_profile=base_profile,
        contributing_profiles=tuple(contributing_profiles),
        contributing_domains=tuple(contributing_domains),
        added_rules=tuple(sorted(added_rules)),
        required_rules=tuple(sorted(required_rules)),
        prohibited_actions=tuple(sorted(prohibited_actions)),
        minimum_confidence=min_confidence,
        maximum_inference_depth=max_inference_depth,
        maximum_questions_per_turn=max_questions,
    )

    return profile, tuple(decisions)


def _get_reasoning_profile_metadata(
    definition: DomainDefinition,
) -> Mapping[str, Any] | None:
    """Safely extract reasoning_profile metadata from a definition's metadata."""
    meta = definition.metadata
    if meta is None:
        return None
    rp = meta.get("reasoning_profile")
    if rp is None:
        return None
    if isinstance(rp, Mapping):
        return rp
    return None


def _extract_float_max(
    meta: Mapping[str, Any], key: str, fields_checked: set[str]
) -> float | None:
    """Extract a finite float value."""
    if key in fields_checked:
        return None
    fields_checked.add(key)
    val = meta.get(key)
    if val is None:
        return None
    if isinstance(val, bool):
        # Validate contract error on explicit bool
        raise DomainCompositionContractError(
            f"reasoning_profile.{key} must be a number, not a boolean",
            field=f"metadata.reasoning_profile.{key}",
        )
    if isinstance(val, (int, float)):
        f = float(val)
        if not math.isfinite(f):
            raise DomainCompositionContractError(
                f"reasoning_profile.{key} must be a finite number",
                field=f"metadata.reasoning_profile.{key}",
            )
        if not (0.0 <= f <= 1.0):
            return None
        return f
    return None


def _extract_float_value(meta: Mapping[str, Any], key: str) -> float | None:
    """Extract a non-bool float value."""
    val = meta.get(key)
    if val is None:
        return None
    if isinstance(val, bool):
        raise DomainCompositionContractError(
            f"reasoning_profile.{key} must be a number, not a boolean",
            field=f"metadata.reasoning_profile.{key}",
        )
    if isinstance(val, (int, float)):
        f = float(val)
        if not math.isfinite(f):
            raise DomainCompositionContractError(
                f"reasoning_profile.{key} must be a finite number",
                field=f"metadata.reasoning_profile.{key}",
            )
        return f
    return None


def _extract_int_min(meta: Mapping[str, Any], key: str) -> int | None:
    """Extract a positive int."""
    val = meta.get(key)
    if val is None:
        return None
    if isinstance(val, bool):
        raise DomainCompositionContractError(
            f"reasoning_profile.{key} must be an integer, not a boolean",
            field=f"metadata.reasoning_profile.{key}",
        )
    if isinstance(val, int):
        return val
    return None


def _extract_int_value(meta: Mapping[str, Any], key: str) -> int | None:
    """Extract positive int value from supporting domain metadata."""
    val = meta.get(key)
    if val is None:
        return None
    if isinstance(val, bool):
        raise DomainCompositionContractError(
            f"reasoning_profile.{key} must be an integer, not a boolean",
            field=f"metadata.reasoning_profile.{key}",
        )
    if isinstance(val, int):
        return val
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Presentation composition
# ═══════════════════════════════════════════════════════════════════════════════


def compose_presentation(
    definitions: tuple[DomainDefinition, ...],
    policy: DomainCompositionPolicy,
) -> tuple[
    PresentationComposition,
    tuple[DomainCompositionDecision, ...],
    tuple[DomainCompositionConflict, ...],
]:
    """Compose presentation from primary and supporting domains."""
    if not definitions:
        return (
            PresentationComposition(
                values=MappingProxyType({}),
                provenance=MappingProxyType({}),
            ),
            (),
            (),
        )

    primary = definitions[0]
    supporting = definitions[1:]
    conflict_policy = policy.conflict_policy

    # Start with primary values
    values: dict[str, Any] = {}
    provenance: dict[str, Any] = {}

    # Copy primary presentation
    primary_pp = primary.presentation_policy
    if primary_pp:
        for key, val in primary_pp.items():
            if isinstance(key, str):
                values[key] = val
                provenance[key] = [str(primary.id)]

    decisions: list[DomainCompositionDecision] = []
    conflicts: list[DomainCompositionConflict] = []

    # Supporting domains fill missing keys
    for sup_def in supporting:
        sup_pp = sup_def.presentation_policy
        if not sup_pp:
            continue
        for key, val in sup_pp.items():
            if not isinstance(key, str):
                continue
            if key not in values:
                # Key absent: fill
                values[key] = val
                provenance[key] = [str(sup_def.id)]
                decisions.append(
                    DomainCompositionDecision(
                        code="DOMAIN_COMPOSITION_SUPPORTING_ADDED",
                        category="presentation",
                        identifier=key,
                        action="added",
                        domains=(DomainId.from_str(str(sup_def.id)),),
                        reason="Supporting domain adds missing presentation key",
                    )
                )
            else:
                existing_val = values[key]
                # Compare values: if mappings, recurse; else check equality
                if _values_equal(existing_val, val):
                    # Same value: merge provenance
                    prov_list = provenance.get(key, [])
                    if isinstance(prov_list, list):
                        prov_list.append(str(sup_def.id))
                    decisions.append(
                        DomainCompositionDecision(
                            code="DOMAIN_COMPOSITION_DUPLICATE_COLLAPSED",
                            category="presentation",
                            identifier=key,
                            action="provenance_merged",
                            domains=(
                                DomainId.from_str(str(primary.id)),
                                DomainId.from_str(str(sup_def.id)),
                            ),
                            reason="Same presentation value, provenance merged",
                        )
                    )
                else:
                    # Conflict: different values
                    if conflict_policy == DomainConflictPolicy.BLOCK_ON_CONFLICT:
                        conflict = DomainCompositionConflict(
                            code="DOMAIN_COMPOSITION_PRESENTATION_CONFLICT",
                            category="presentation",
                            domains=(
                                DomainId.from_str(str(primary.id)),
                                DomainId.from_str(str(sup_def.id)),
                            ),
                            severity="blocking",
                            message=f"Presentation conflict on key '{key}'",
                            blocking=True,
                            resolved=False,
                        )
                        conflicts.append(conflict)
                    elif conflict_policy == DomainConflictPolicy.PRIMARY_PRECEDENCE:
                        # Primary wins, record resolved conflict
                        conflict = DomainCompositionConflict(
                            code="DOMAIN_COMPOSITION_PRESENTATION_CONFLICT",
                            category="presentation",
                            domains=(
                                DomainId.from_str(str(primary.id)),
                                DomainId.from_str(str(sup_def.id)),
                            ),
                            severity="warning",
                            message=f"Presentation conflict on key '{key}', primary precedence applied",
                            blocking=False,
                            resolved=True,
                            resolution="primary_precedence",
                        )
                        conflicts.append(conflict)
                        decisions.append(
                            DomainCompositionDecision(
                                code="DOMAIN_COMPOSITION_PRIMARY_PRECEDENCE",
                                category="presentation",
                                identifier=key,
                                action="primary_wins",
                                domains=(
                                    DomainId.from_str(str(primary.id)),
                                    DomainId.from_str(str(sup_def.id)),
                                ),
                                reason="Primary value retained due to PRIMARY_PRECEDENCE",
                            )
                        )
                    else:
                        # MOST_RESTRICTIVE: preserve primary, record partial conflict
                        conflict = DomainCompositionConflict(
                            code="DOMAIN_COMPOSITION_PRESENTATION_CONFLICT",
                            category="presentation",
                            domains=(
                                DomainId.from_str(str(primary.id)),
                                DomainId.from_str(str(sup_def.id)),
                            ),
                            severity="warning",
                            message=f"Presentation conflict on key '{key}', primary value retained (MOST_RESTRICTIVE does not infer)",
                            blocking=False,
                            resolved=False,
                        )
                        conflicts.append(conflict)

    # Recursively compose nested mappings
    _compose_nested_mappings(
        values, provenance, definitions, conflict_policy, decisions, conflicts, ""
    )

    # Sort values keys deterministically
    sorted_values = {k: values[k] for k in sorted(values.keys())}
    sorted_provenance = {k: provenance.get(k, []) for k in sorted(values.keys())}

    return (
        PresentationComposition(
            values=MappingProxyType(sorted_values),
            provenance=MappingProxyType(sorted_provenance),
            conflicts=tuple(conflicts),
        ),
        tuple(decisions),
        tuple(conflicts),
    )


def _values_equal(a: Any, b: Any) -> bool:
    """Check if two presentation values are equal for composition purposes."""
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        # Recursively compare nested mappings
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_values_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return tuple(a) == tuple(b)
    return a == b


def _compose_nested_mappings(
    values: dict[str, Any],
    provenance: dict[str, Any],
    definitions: tuple[DomainDefinition, ...],
    conflict_policy: DomainConflictPolicy,
    decisions: list[DomainCompositionDecision],
    conflicts: list[DomainCompositionConflict],
    path_prefix: str,
) -> None:
    """Recursively compose nested mappings for existing values."""
    for key, val in list(values.items()):
        if not isinstance(val, Mapping):
            continue
        full_key = f"{path_prefix}.{key}" if path_prefix else key

        # Build a nested composition from all domain presentation policies
        nested_values: dict[str, Any] = dict(val)
        nested_prov: dict[str, Any] = {
            k: provenance.get(full_key, []) for k in nested_values
        }

        for defn in definitions[1:]:  # supporting
            sup_pp = defn.presentation_policy
            if not sup_pp:
                continue
            sup_nested = sup_pp.get(key)
            if not isinstance(sup_nested, Mapping):
                continue
            for nk, nv in sup_nested.items():
                if not isinstance(nk, str):
                    continue
                if nk not in nested_values:
                    nested_values[nk] = nv
                    nested_prov[nk] = [str(defn.id)]
                    decisions.append(
                        DomainCompositionDecision(
                            code="DOMAIN_COMPOSITION_SUPPORTING_ADDED",
                            category="presentation",
                            identifier=f"{full_key}.{nk}"
                            if path_prefix
                            else f"{key}.{nk}",
                            action="added",
                            domains=(DomainId.from_str(str(defn.id)),),
                        )
                    )
                elif _values_equal(nested_values[nk], nv):
                    # merge provenance
                    plist = nested_prov.get(nk, [])
                    if isinstance(plist, list):
                        plist.append(str(defn.id))
                else:
                    # nested conflict
                    if conflict_policy == DomainConflictPolicy.BLOCK_ON_CONFLICT:
                        conflicts.append(
                            DomainCompositionConflict(
                                code="DOMAIN_COMPOSITION_PRESENTATION_CONFLICT",
                                category="presentation",
                                domains=(
                                    DomainId.from_str(str(definitions[0].id)),
                                    DomainId.from_str(str(defn.id)),
                                ),
                                severity="blocking",
                                message=f"Presentation conflict on nested key '{full_key}.{nk}'"
                                if full_key
                                else f"Presentation conflict on nested key '{key}.{nk}'",
                                blocking=True,
                                resolved=False,
                            )
                        )
                    else:
                        conflicts.append(
                            DomainCompositionConflict(
                                code="DOMAIN_COMPOSITION_PRESENTATION_CONFLICT",
                                category="presentation",
                                domains=(
                                    DomainId.from_str(str(definitions[0].id)),
                                    DomainId.from_str(str(defn.id)),
                                ),
                                severity="warning",
                                message=f"Presentation conflict on nested key '{full_key}.{nk}'"
                                if full_key
                                else f"Presentation conflict on nested key '{key}.{nk}'",
                                blocking=False,
                                resolved=(
                                    conflict_policy
                                    == DomainConflictPolicy.PRIMARY_PRECEDENCE
                                ),
                            )
                        )

        # Update the nested value with composed result
        values[key] = nested_values
        prov_key = full_key
        for nk in sorted(nested_values.keys()):
            nested_prov_key = f"{prov_key}.{nk}" if prov_key else nk
            provenance[nested_prov_key] = nested_prov.get(nk, [])


__all__ = [
    "compose_capability_items",
    "compose_presentation",
    "compose_reasoning_profile",
    "compose_reference_items",
]
