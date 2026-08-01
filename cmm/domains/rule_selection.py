"""Pure selection of common reasoning rules from resolved Domain Profiles."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cmp_to_key
from typing import Protocol, runtime_checkable

from cmm.cognitive.enums import (
    ReasoningRuleCategory,
    ReasoningRuleScope,
    ReasoningRuleStatus,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRule, _semver_key
from cmm.cognitive.reasoning_rule_registry import ReasoningRuleRegistry
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import (
    DomainRuleSelectionDecisionCode,
    DomainRuleSelectionStatus,
    DomainRuleSource,
)
from cmm.domains.errors import DomainRuleConfigurationError, DomainRuleSelectionError
from cmm.domains.profile_contracts import ResolvedDomainProfile
from cmm.domains.rule_contracts import (
    DomainRuleExecutionPlan,
    DomainRuleSelectionConflict,
    DomainRuleSelectionDecision,
    DomainRuleSelectionPolicy,
    DomainRuleSourceRecord,
    SelectedReasoningRule,
)

_GROUP_ORDER = {
    DomainRuleSource.GLOBAL_MANDATORY: 0,
    DomainRuleSource.SECURITY: 1,
    DomainRuleSource.PRIMARY_DOMAIN: 2,
    DomainRuleSource.SUPPORTING_DOMAIN: 3,
    DomainRuleSource.OPTIONAL: 4,
    DomainRuleSource.PRESENTATION: 5,
}


@dataclass(slots=True)
class _Candidate:
    rule_id: str
    version: str | None
    sources: list[DomainRuleSourceRecord]
    required: bool
    group: DomainRuleSource


def _parse_reference(reference: str) -> tuple[str, str | None]:
    if "@" not in reference:
        return reference, None
    rule_id, version = reference.rsplit("@", 1)
    if not rule_id or not version:
        raise DomainRuleSelectionError("invalid versioned rule reference", field="reference")
    _semver_key(version)
    return rule_id, version


def _definition_cmp(left: SelectedReasoningRule, right: SelectedReasoningRule) -> int:
    left_group = _GROUP_ORDER[left.group]
    right_group = _GROUP_ORDER[right.group]
    if left_group != right_group:
        return -1 if left_group < right_group else 1
    if left.definition.priority != right.definition.priority:
        return -1 if left.definition.priority > right.definition.priority else 1
    left_precedence = min((source.precedence for source in left.sources), default=0)
    right_precedence = min((source.precedence for source in right.sources), default=0)
    if left_precedence != right_precedence:
        return -1 if left_precedence < right_precedence else 1
    if left.definition.id != right.definition.id:
        return -1 if left.definition.id < right.definition.id else 1
    left_version = _semver_key(left.definition.version)
    right_version = _semver_key(right.definition.version)
    if left_version == right_version:
        return 0
    return -1 if left_version > right_version else 1


@runtime_checkable
class DomainRuleSelector(Protocol):
    def select(
        self,
        *,
        registry: ReasoningRuleRegistry,
        profile: ResolvedDomainProfile,
        composition: DomainComposition | None = None,
        global_mandatory_rules: tuple[str, ...] = (),
        security_rules: tuple[str, ...] = (),
        effective_permissions: tuple[str, ...] = (),
        requested_rule_ids: tuple[str, ...] = (),
        policy: DomainRuleSelectionPolicy | None = None,
    ) -> DomainRuleExecutionPlan: ...


class DefaultDomainRuleSelector:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise DomainRuleConfigurationError("clock must be callable", field="clock")
        if id_factory is not None and not callable(id_factory):
            raise DomainRuleConfigurationError("id_factory must be callable", field="id_factory")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: f"domain-rule-plan-{uuid.uuid4()}")

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise DomainRuleSelectionError("clock must return a timezone-aware datetime", field="clock")
        return value

    def _id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise DomainRuleSelectionError("id_factory must return a non-empty string", field="id_factory")
        return value.strip()

    def select(
        self,
        *,
        registry: ReasoningRuleRegistry,
        profile: ResolvedDomainProfile,
        composition: DomainComposition | None = None,
        global_mandatory_rules: tuple[str, ...] = (),
        security_rules: tuple[str, ...] = (),
        effective_permissions: tuple[str, ...] = (),
        requested_rule_ids: tuple[str, ...] = (),
        policy: DomainRuleSelectionPolicy | None = None,
    ) -> DomainRuleExecutionPlan:
        if not isinstance(profile, ResolvedDomainProfile):
            raise DomainRuleSelectionError("profile must be a ResolvedDomainProfile", field="profile")
        if not isinstance(registry, ReasoningRuleRegistry):
            raise DomainRuleSelectionError("registry must satisfy ReasoningRuleRegistry", field="registry")
        if composition is not None and not isinstance(composition, DomainComposition):
            raise DomainRuleSelectionError("composition must be a DomainComposition", field="composition")
        policy = policy or DomainRuleSelectionPolicy()
        if not isinstance(policy, DomainRuleSelectionPolicy):
            raise DomainRuleSelectionError("policy must be a DomainRuleSelectionPolicy", field="policy")

        active_domains = (str(profile.primary_domain), *(str(x) for x in profile.supporting_domains))
        domain_precedence = {domain: index for index, domain in enumerate(active_domains)}
        permitted = set(effective_permissions)
        if profile.permissions is not None:
            permitted &= set(profile.permissions)
        denied = set(policy.denied_permissions)
        prohibited = {_parse_reference(ref)[0] for ref in profile.prohibited_rules}
        candidates: dict[tuple[str, str | None], _Candidate] = {}
        source_order = 0

        def add(
            reference: str,
            source: DomainRuleSource,
            required: bool,
            domain_id: str | None = None,
            *,
            precedence: int | None = None,
            metadata: dict[str, object] | None = None,
        ) -> None:
            nonlocal source_order
            rule_id, version = _parse_reference(reference)
            record = DomainRuleSourceRecord(
                source=source,
                reference=reference,
                required=required,
                domain_id=domain_id,
                profile_name=profile.profile_names[-1] if profile.profile_names else None,
                precedence=source_order if precedence is None else precedence,
                metadata=metadata or {},
            )
            source_order += 1
            key = (rule_id, version)
            existing = candidates.get(key)
            if existing is None:
                group = source
                if source in {DomainRuleSource.PROFILE, DomainRuleSource.COMPOSITION}:
                    group = DomainRuleSource.PRIMARY_DOMAIN
                candidates[key] = _Candidate(rule_id, version, [record], required, group)
            else:
                existing.sources.append(record)
                existing.required = existing.required or required
                if _GROUP_ORDER.get(source, 99) < _GROUP_ORDER.get(existing.group, 99):
                    existing.group = source

        for reference in global_mandatory_rules:
            add(reference, DomainRuleSource.GLOBAL_MANDATORY, True)
        for reference in security_rules:
            add(reference, DomainRuleSource.SECURITY, True)
        for reference in profile.required_rules:
            add(reference, DomainRuleSource.PROFILE, True)
        if composition is not None and composition.effective_profile is not None:
            for reference in composition.effective_profile.required_rules:
                add(reference, DomainRuleSource.COMPOSITION, True)
            for reference in composition.effective_profile.added_rules:
                add(reference, DomainRuleSource.COMPOSITION, False)
        if composition is not None:
            composition_required = (
                set(composition.effective_profile.required_rules)
                if composition.effective_profile is not None
                else set()
            )
            for item in composition.rules:
                add(
                    item.identifier,
                    DomainRuleSource.COMPOSITION,
                    item.identifier in composition_required,
                    str(item.primary_contributor),
                    precedence=item.precedence,
                    metadata={
                        "category": item.category,
                        "contributing_domains": [str(domain) for domain in item.contributing_domains],
                        "composition_item_metadata": item.to_dict()["metadata"],
                    },
                )
        if policy.include_optional:
            for reference in profile.optional_rules:
                add(reference, DomainRuleSource.OPTIONAL, False)
        if policy.include_requested:
            for reference in requested_rule_ids:
                add(reference, DomainRuleSource.EXPLICIT_REQUEST, False)

        selected: list[SelectedReasoningRule] = []
        selected_indexes: dict[tuple[str, str], int] = {}
        decisions: list[DomainRuleSelectionDecision] = []
        conflicts: list[DomainRuleSelectionConflict] = []
        omitted: list[str] = []
        blocked: list[str] = []
        all_missing_permissions: list[str] = []

        candidate_ids = {candidate.rule_id for candidate in candidates.values()}
        for reference in profile.prohibited_rules:
            prohibited_id, _ = _parse_reference(reference)
            if prohibited_id in candidate_ids:
                continue
            source = DomainRuleSourceRecord(
                source=DomainRuleSource.PROFILE,
                reference=reference,
                required=False,
                profile_name=profile.profile_names[-1] if profile.profile_names else None,
            )
            omitted.append(prohibited_id)
            decisions.append(DomainRuleSelectionDecision(
                code=DomainRuleSelectionDecisionCode.RULE_PROHIBITED,
                rule_id=prohibited_id,
                included=False,
                message="Rule excluded by prohibited_rules.",
                sources=(source,),
            ))

        for candidate in candidates.values():
            sources = tuple(candidate.sources)
            global_mandatory = any(x.source is DomainRuleSource.GLOBAL_MANDATORY for x in sources)
            is_prohibited = candidate.rule_id in prohibited
            if is_prohibited and not global_mandatory:
                code = "REQUIRED_RULE_PROHIBITED" if candidate.required else "OPTIONAL_RULE_PROHIBITED"
                if candidate.required:
                    blocked.append(candidate.rule_id)
                    conflicts.append(DomainRuleSelectionConflict(code=code, rule_id=candidate.rule_id,
                        message="A required rule is prohibited.", sources=sources))
                else:
                    omitted.append(candidate.rule_id)
                decisions.append(DomainRuleSelectionDecision(
                    code=DomainRuleSelectionDecisionCode.RULE_PROHIBITED, rule_id=candidate.rule_id,
                    included=False, message="Rule excluded by prohibited_rules.", sources=sources))
                continue
            if is_prohibited and global_mandatory:
                blocked.append(candidate.rule_id)
                conflicts.append(DomainRuleSelectionConflict(
                    code="GLOBAL_MANDATORY_RULE_PROHIBITED", rule_id=candidate.rule_id,
                    message="A global mandatory rule cannot be prohibited.", sources=sources,
                ))

            rule: ReasoningRule | None = (
                registry.get(candidate.rule_id, candidate.version)
                if candidate.version is not None else registry.resolve(candidate.rule_id)
            )
            if rule is None:
                registered_definitions = tuple(
                    definition
                    for definition in registry.inspect_definitions()
                    if definition.id == candidate.rule_id
                    and (candidate.version is None or definition.version == candidate.version)
                )
                if registered_definitions:
                    disabled_definition = max(
                        registered_definitions,
                        key=lambda definition: _semver_key(definition.version),
                    )
                    rule = registry.get(
                        disabled_definition.id, disabled_definition.version
                    )
            if rule is None:
                if candidate.required:
                    blocked.append(candidate.rule_id)
                    conflicts.append(DomainRuleSelectionConflict(
                        code="REQUIRED_RULE_MISSING", rule_id=candidate.rule_id,
                        message="A required rule has no resolvable implementation.", sources=sources,
                    ))
                else:
                    omitted.append(candidate.rule_id)
                decisions.append(DomainRuleSelectionDecision(
                    code=DomainRuleSelectionDecisionCode.RULE_MISSING, rule_id=candidate.rule_id,
                    included=False, message="Rule implementation was not found.", sources=sources,
                ))
                continue
            definition = rule.definition
            if definition.status is ReasoningRuleStatus.DISABLED:
                if candidate.required:
                    blocked.append(candidate.rule_id)
                    conflicts.append(DomainRuleSelectionConflict(
                        code="REQUIRED_RULE_DISABLED", rule_id=candidate.rule_id,
                        message="A required rule is disabled.", sources=sources,
                    ))
                else:
                    omitted.append(candidate.rule_id)
                decisions.append(DomainRuleSelectionDecision(
                    code=DomainRuleSelectionDecisionCode.RULE_DISABLED, rule_id=candidate.rule_id,
                    included=False, message="Rule is disabled.", sources=sources,
                ))
                continue
            if definition.scope is ReasoningRuleScope.DOMAIN and definition.domain_id not in active_domains:
                if candidate.required:
                    blocked.append(candidate.rule_id)
                    conflicts.append(DomainRuleSelectionConflict(
                        code="RULE_DOMAIN_MISMATCH", rule_id=candidate.rule_id,
                        message="Rule domain is not active.", sources=sources,
                    ))
                else:
                    omitted.append(candidate.rule_id)
                decisions.append(DomainRuleSelectionDecision(
                    code=DomainRuleSelectionDecisionCode.DOMAIN_MISMATCH, rule_id=candidate.rule_id,
                    included=False, message="Rule domain is not active.", sources=sources,
                ))
                continue
            missing = tuple(sorted((set(definition.required_permissions) - permitted) | (set(definition.required_permissions) & denied)))
            if missing:
                all_missing_permissions.extend(missing)
                if candidate.required:
                    blocked.append(candidate.rule_id)
                    conflicts.append(DomainRuleSelectionConflict(
                        code="REQUIRED_RULE_PERMISSION_MISSING", rule_id=candidate.rule_id,
                        message="Required permissions are missing or denied.", sources=sources,
                        missing_permissions=missing,
                    ))
                else:
                    omitted.append(candidate.rule_id)
                decisions.append(DomainRuleSelectionDecision(
                    code=DomainRuleSelectionDecisionCode.PERMISSION_MISSING, rule_id=candidate.rule_id,
                    included=False, message="Required permissions are missing or denied.", sources=sources,
                    missing_permissions=missing,
                ))
                continue

            group = candidate.group
            if definition.category is ReasoningRuleCategory.PRESENTATION:
                group = DomainRuleSource.PRESENTATION
            elif definition.scope is ReasoningRuleScope.DOMAIN and group not in {
                DomainRuleSource.OPTIONAL, DomainRuleSource.EXPLICIT_REQUEST
            }:
                group = (DomainRuleSource.PRIMARY_DOMAIN if definition.domain_id == active_domains[0]
                         else DomainRuleSource.SUPPORTING_DOMAIN)
            elif group is DomainRuleSource.EXPLICIT_REQUEST:
                group = DomainRuleSource.OPTIONAL
            precedence = domain_precedence.get(definition.domain_id or "", 0)
            normalized_sources = tuple(
                DomainRuleSourceRecord(
                    source=x.source, reference=x.reference, required=x.required,
                    domain_id=x.domain_id or definition.domain_id, profile_name=x.profile_name,
                    precedence=(
                        x.precedence
                        if x.source is DomainRuleSource.COMPOSITION
                        else precedence if definition.domain_id else x.precedence
                    ),
                    metadata=x.metadata,
                ) for x in sources
            )
            selected_rule = SelectedReasoningRule(
                definition=definition, sources=normalized_sources, group=group,
                required=candidate.required or global_mandatory,
            )
            resolved_key = (definition.id, definition.version)
            existing_index = selected_indexes.get(resolved_key)
            if existing_index is None:
                selected_indexes[resolved_key] = len(selected)
                selected.append(selected_rule)
            else:
                existing = selected[existing_index]
                merged_source_list = list(existing.sources)
                for source in selected_rule.sources:
                    if source not in merged_source_list:
                        merged_source_list.append(source)
                merged_sources = tuple(merged_source_list)
                merged_group = existing.group
                if _GROUP_ORDER.get(selected_rule.group, 99) < _GROUP_ORDER.get(existing.group, 99):
                    merged_group = selected_rule.group
                selected[existing_index] = SelectedReasoningRule(
                    definition=definition,
                    sources=merged_sources,
                    group=merged_group,
                    required=existing.required or selected_rule.required,
                )
            decisions.append(DomainRuleSelectionDecision(
                code=DomainRuleSelectionDecisionCode.RULE_SELECTED, rule_id=candidate.rule_id,
                included=True, message="Rule selected for execution.", sources=normalized_sources,
            ))

        selected.sort(key=cmp_to_key(_definition_cmp))
        blocked_unique = tuple(dict.fromkeys(blocked))
        omitted_unique = tuple(dict.fromkeys(omitted))
        if conflicts:
            status = DomainRuleSelectionStatus.BLOCKED
        elif omitted_unique:
            status = DomainRuleSelectionStatus.PARTIAL
        else:
            status = DomainRuleSelectionStatus.READY
        contributing_domains = tuple(str(x) for x in (profile.primary_domain, *profile.supporting_domains))
        return DomainRuleExecutionPlan(
            id=self._id(), status=status, selected_rules=tuple(selected), decisions=tuple(decisions),
            conflicts=tuple(conflicts), omitted_rule_ids=omitted_unique,
            blocked_rule_ids=blocked_unique,
            missing_permissions=tuple(dict.fromkeys(sorted(all_missing_permissions))),
            contributing_profiles=profile.profile_names,
            contributing_domains=contributing_domains,
            created_at=self._now(),
            metadata={"profile_id": profile.id, "composition_id": composition.id if composition else None},
        )


__all__ = ["DefaultDomainRuleSelector", "DomainRuleSelector"]
