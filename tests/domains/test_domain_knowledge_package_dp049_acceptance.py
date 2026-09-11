"""Phase 10.49 — AT-DP-049 connected acceptance test.

DP-049 — Declarative Domain Specialization of the Canonical Phase 8
``KnowledgePackage``.

Connects the full flow using real canonical components:

  real first-party Domain definitions
  → canonical Domain Pack / declarative round-trip
  → DomainCognitiveIntegrationRequest (optional schema)
  → DefaultDomainCognitiveIntegrator
  → ResourceAdapterRegistry / KnowledgeExtractorRegistry
  → InMemoryKnowledgeStore
  → KnowledgePackageBuilder                     (canonical, unchanged)
  → validate_domain_knowledge_package           (Phase 10.49, pure)
  → compose_domain_knowledge_package_schemas    (Phase 10.49, pure)
  → CognitiveValidator / rule selection / execution
  → DomainPresentationItemRef / DomainTraceReferences

Mocks never replace accepted behaviour.  The canonical builder remains the only
knowledge-package construction path; Phase 10.49 only narrows or rejects.
"""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cmm.cognitive import (
    CognitiveValidator,
    Confidence,
    Contradiction,
    ContradictionSeverity,
    ContradictionStatus,
    Evidence,
    ExistingResourceAdapter,
    InMemoryKnowledgeStore,
    KnowledgeExtractorRegistry,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackage,
    PlainTextKnowledgeExtractor,
    Resource,
    ResourceAdapterRegistry,
    ResourceInput,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
    SensitivityLevel,
    TemporalScope,
    TemporalScopeKind,
)
from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
    DomainCognitiveResourceInput,
)
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.concerns.definition import build_concerns_domain_definition
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainKind,
    DomainPackKind,
    DomainReasoningDepth,
    DomainResourceResolutionStatus,
)
from cmm.domains.errors import (
    DomainKnowledgePackageCompositionError,
    DomainKnowledgePackageValidationError,
)
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_composition import (
    compose_domain_knowledge_package_schemas,
)
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
    EffectiveDomainKnowledgePackageSchema,
)
from cmm.domains.knowledge_package_validation import (
    validate_domain_knowledge_package,
)
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
from cmm.domains.manifest import DomainComponentReference, DomainManifest
from cmm.domains.pack import DomainPack, ParsedDomainPack
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
    ResolvedDomainProfile,
)
from cmm.domains.relationships.definition import (
    build_relationships_domain_definition,
)
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceResolution,
)
from cmm.domains.rule_catalog import build_initial_reasoning_rule_catalog
from cmm.domains.rule_execution import DefaultDomainRuleExecutor
from cmm.domains.rule_selection import DefaultDomainRuleSelector
from cmm.domains.university.definition import build_university_domain_definition
from cmm.domains.validation_fragmentation import analyze_fragmentation

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
VALID_FROM = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
VALID_UNTIL = datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)
OBSERVED_AT = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
LAST_VERIFIED_AT = datetime(2026, 9, 2, 11, 0, tzinfo=timezone.utc)

ROOT = Path(__file__).resolve().parents[2]
PHASE_10_49_CANONICAL_MODULES = (
    ROOT / "cmm" / "domains" / "knowledge_package_contracts.py",
    ROOT / "cmm" / "domains" / "knowledge_package_composition.py",
    ROOT / "cmm" / "domains" / "knowledge_package_validation.py",
)

PROHIBITED_PRODUCTION_NAMES = frozenset(
    {
        "DomainKnowledgePackageBuilder",
        "DomainKnowledgePackageRegistry",
        "DomainKnowledgeRegistry",
        "DomainKnowledgePackageLoader",
        "DomainKnowledgeLoader",
        "DomainKnowledgePackageResolver",
        "DomainKnowledgeResolver",
        "DomainKnowledgePackageStore",
        "DomainKnowledgeStore",
        "DomainKnowledgePackageRuntime",
        "DomainKnowledgeRuntime",
        "DomainKnowledgePackageEngine",
        "DomainKnowledgeEngine",
    }
)


class _Checkpointer:
    """Deterministic acceptance checkpoints."""

    def __init__(self) -> None:
        self.points: list[str] = []

    def checkpoint(self, name: str) -> None:
        self.points.append(name)


# ── Real canonical fixtures ───────────────────────────────────────────────────


def _binding() -> DomainResourceBinding:
    return DomainResourceBinding(
        id="binding-049",
        resource_id="resource-049",
        definition_id="definition-049",
        domain_id=DomainId("health"),
        adapter="existing_resource",
        provenance=("clinical-registry-01",),
        permissions=("resource.read",),
        sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
        temporal_scope={
            "valid_from": VALID_FROM,
            "valid_until": VALID_UNTIL,
            "observed_at": OBSERVED_AT,
            "last_verified_at": LAST_VERIFIED_AT,
        },
        source_priority=17,
        reliability=0.73,
    )


def _resolution(binding: DomainResourceBinding) -> DomainResourceResolution:
    return DomainResourceResolution(
        id="resolution-049",
        resource_id=binding.resource_id,
        status=DomainResourceResolutionStatus.RESOLVED,
        trace_id="resolution-trace-049",
        resolved_at=NOW,
        bindings=(binding,),
    )


def _canonical_resource(binding: DomainResourceBinding) -> Resource:
    return Resource(
        id=binding.resource_id,
        domain="domain:health",
        kind=ResourceKind.DOCUMENT,
        source=ResourceSourceKind.LOCAL_FILE,
        content=(
            "The follow-up appointment is scheduled for October 15.\n"
            "Which clinic is the appointment at?\n"
        ),
        provenance=ResourceProvenance(
            source_id=binding.resource_id,
            source_type=ResourceSourceKind.LOCAL_FILE,
            retrieved_at=NOW,
        ),
        reliability=Confidence(0.9),
        temporal_scope=ResourceTemporalScope(
            valid_from=VALID_FROM,
            valid_until=VALID_UNTIL,
            observed_at=OBSERVED_AT,
            last_verified_at=LAST_VERIFIED_AT,
        ),
        sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
        permissions=(
            ResourcePermission(
                allowed_operations=(
                    ResourcePermissionOperation.READ,
                    ResourcePermissionOperation.INFER,
                )
            ),
        ),
    )


def _resource_input(binding: DomainResourceBinding) -> DomainCognitiveResourceInput:
    return DomainCognitiveResourceInput(
        resolution=_resolution(binding),
        binding=binding,
        source=ResourceInput(
            id=binding.resource_id,
            payload=_canonical_resource(binding),
            source_kind=ResourceSourceKind.LOCAL_FILE,
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
        ),
        extractor_name="plain_text",
    )


def _store() -> InMemoryKnowledgeStore:
    """Seed two matching facts and one canonical contradiction.

    Each fact carries canonical Phase 8 provenance (``Evidence`` bound to the
    source resource) and a non-unknown ``TemporalScope``, because Health's
    canonical semantics require documented, sourced and temporally valid
    clinical information. The Health schema therefore exercises its provenance
    and temporal floor against this fixture instead of skipping it.
    """
    store = InMemoryKnowledgeStore()
    for item in (
        KnowledgeItem(
            id="fact-049-a",
            statement=(
                "Health information review: the patient reports a stable trend."
            ),
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.91, source="clinical-registry-01"),
            resource_id="resource-049",
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            evidence=(
                Evidence(
                    id="evidence-049-a",
                    resource_id="resource-049",
                    fragment=("The follow-up appointment is scheduled for October 15."),
                    confidence=Confidence(0.9),
                ),
            ),
            temporal_scope=TemporalScope(
                kind=TemporalScopeKind.POINT_IN_TIME,
                observed_at=OBSERVED_AT,
                last_verified_at=LAST_VERIFIED_AT,
            ),
            created_at=NOW,
            updated_at=NOW,
        ),
        KnowledgeItem(
            id="fact-049-b",
            statement=(
                "Health information review: the patient reports an unstable trend."
            ),
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.72, source="clinical-registry-02"),
            resource_id="resource-049",
            sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
            evidence=(
                Evidence(
                    id="evidence-049-b",
                    resource_id="resource-049",
                    fragment=("Which clinic is the appointment at?"),
                    confidence=Confidence(0.9),
                ),
            ),
            temporal_scope=TemporalScope(
                kind=TemporalScopeKind.POINT_IN_TIME,
                observed_at=OBSERVED_AT,
                last_verified_at=LAST_VERIFIED_AT,
            ),
            created_at=NOW,
            updated_at=NOW,
        ),
    ):
        InMemoryKnowledgeStore.save_item(store, item)
    InMemoryKnowledgeStore.save_contradiction(
        store,
        Contradiction(
            id="contradiction-049",
            item_a_id="fact-049-a",
            item_b_id="fact-049-b",
            severity=ContradictionSeverity.MEDIUM,
            created_at=NOW,
        ),
    )
    return store


def _store_state(store: InMemoryKnowledgeStore) -> dict[str, object]:
    return {
        "items": [item.serialize() for item in store.list_items()],
        "evidence": [evidence.serialize() for evidence in store.list_evidence()],
        "relations": [relation.serialize() for relation in store.list_relations()],
        "contradictions": [
            contradiction.serialize() for contradiction in store.list_contradictions()
        ],
        "bundles": [bundle.serialize() for bundle in store.list_bundles()],
    }


def _manifest_for(definition: object) -> DomainManifest:
    """Build a coherent manifest for a real first-party definition."""

    def _components(ids: tuple[str, ...]) -> tuple[DomainComponentReference, ...]:
        return tuple(
            DomainComponentReference(id=item, path=f"{item.replace('.', '/')}.json")
            for item in ids
        )

    return DomainManifest(
        id=definition.manifest_id,  # type: ignore[attr-defined]
        domain_id=definition.id,  # type: ignore[attr-defined]
        schema_version="1",
        package_version=definition.version,  # type: ignore[attr-defined]
        pack_kind=DomainPackKind.INTERNAL,
        resources=_components(definition.resources),  # type: ignore[attr-defined]
        rules=_components(definition.rules),  # type: ignore[attr-defined]
        operations=_components(definition.operations),  # type: ignore[attr-defined]
        workflows=_components(definition.workflows),  # type: ignore[attr-defined]
        validators=_components(definition.validators),  # type: ignore[attr-defined]
    )


def _profile() -> ResolvedDomainProfile:
    return ResolvedDomainProfile(
        id="profile-049",
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("university"),),
        profile_names=("HealthProfile",),
        required_rules=(),
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=None,
        priority_resource_kinds=(),
        prohibited_resource_kinds=(),
        minimum_confidence=0.8,
        reasoning_depth=DomainReasoningDepth.DEEP,
        allowed_inferences=None,
        prohibited_inferences=(),
        maximum_questions=3,
        escalation_rules=(),
        prohibited_actions=(),
        question_policy=DomainQuestionPolicy(),
        presentation_policy=DomainPresentationPolicy(),
        memory_policy=DomainMemoryPolicy(),
        temporal_policy=DomainTemporalPolicy(),
        production_policy=DomainProductionPolicy(),
        permissions=None,
        modifications=(),
        trace_id="profile-trace-049",
        resolved_at=NOW,
    )


def _composition() -> DomainComposition:
    return DomainComposition(
        id="composition-049",
        resolution_id="resolution-result-049",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("university"),),
        composed_at=NOW,
    )


def _integrator(store: InMemoryKnowledgeStore) -> DefaultDomainCognitiveIntegrator:
    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(ExistingResourceAdapter())
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(PlainTextKnowledgeExtractor())
    return DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=store,
        rule_registry=build_initial_reasoning_rule_catalog(),
        cognitive_validator=CognitiveValidator(),
        rule_selector=DefaultDomainRuleSelector(clock=lambda: NOW),
        rule_executor=DefaultDomainRuleExecutor(clock=lambda: NOW),
        clock=lambda: NOW,
    )


def _request(
    binding: DomainResourceBinding, **overrides: object
) -> DomainCognitiveIntegrationRequest:
    data: dict[str, object] = {
        "request_id": "request-049",
        "resolution_context_id": "resolution-context-049",
        "resolution_result_id": "resolution-result-049",
        "objective": "Review health information",
        "composition": _composition(),
        "profile": _profile(),
        "resources": (_resource_input(binding),),
        "actor_id": "actor-049",
        "session_id": "session-049",
        "effective_permissions": ("resource.read",),
    }
    data.update(overrides)
    return DomainCognitiveIntegrationRequest(**data)  # type: ignore[arg-type]


# ── AT-DP-049 ─────────────────────────────────────────────────────────────────


def test_at_dp049_connected_acceptance() -> None:
    """Connected AT-DP-049 acceptance covering scenarios A–J."""
    cp = _Checkpointer()

    # ── Scenario A: real first-party ownership ────────────────────────────
    health = build_health_domain_definition()
    university = build_university_domain_definition()
    health_schema = health.knowledge_package_schema
    university_schema = university.knowledge_package_schema

    assert isinstance(health_schema, DomainKnowledgePackageSchema)
    assert isinstance(university_schema, DomainKnowledgePackageSchema)
    assert health_schema is not None and university_schema is not None
    assert str(health_schema.domain_id) == "domain:health"
    assert str(university_schema.domain_id) == "domain:university"
    assert health_schema.minimum_sensitivity is SensitivityLevel.SENSITIVE
    assert university_schema.minimum_sensitivity is SensitivityLevel.INTERNAL
    assert health_schema.base_schema == "KnowledgePackage"
    cp.checkpoint("01-real-first-party-ownership")

    # ── Scenario B: canonical Domain Pack round-trip ──────────────────────
    manifest = _manifest_for(health)
    pack = DomainPack(definition=health, manifest=manifest, root_path="/opt/health")
    restored_pack = DomainPack.from_dict(pack.to_dict())
    restored_parsed = ParsedDomainPack.from_dict(
        ParsedDomainPack(definition=health, manifest=manifest).to_dict()
    )

    assert restored_pack.definition.knowledge_package_schema == health_schema
    assert restored_parsed.definition.knowledge_package_schema == health_schema
    assert restored_pack.to_dict() == pack.to_dict()

    declarative = ParsedDomainPack.from_declarative_dict(
        {
            "id": "health",
            "version": health.version,
            "name": health.name,
            "display_name": health.display_name,
            "description": health.description,
            "author": "CMM OS",
            "license": "internal",
            "knowledge_package_schema": health_schema.to_dict(),
        }
    )
    assert declarative.definition.knowledge_package_schema == health_schema
    assert DomainKind.PERSONAL is health.kind
    cp.checkpoint("02-canonical-pack-round-trip")

    # ── Scenario G: real multi-domain composition (most restrictive) ──────
    effective = compose_domain_knowledge_package_schemas(
        (health_schema, university_schema)
    )
    assert isinstance(effective, EffectiveDomainKnowledgePackageSchema)
    assert effective.source_schema_ids == tuple(
        sorted((health_schema.id, university_schema.id))
    )
    assert effective.domain_ids == (
        DomainId("health"),
        DomainId("university"),
    )
    assert effective.minimum_sensitivity is SensitivityLevel.SENSITIVE
    assert effective.required_sections == ("objective",)
    assert effective.prohibited_sections == ()
    # Order independence.
    reversed_effective = compose_domain_knowledge_package_schemas(
        (university_schema, health_schema)
    )
    assert reversed_effective == effective
    cp.checkpoint("03-effective-schema-composed")

    # ── Scenario C/Step 12: canonical builder + integrator path ───────────
    store = _store()
    store_before = _store_state(store)
    binding = _binding()
    integrator = _integrator(store)

    unauthorized = replace(_request(binding), effective_permissions=())
    with pytest.raises(Exception) as blocked:
        integrator.integrate(unauthorized)
    assert "resource.read" in blocked.value.details["missing_permissions"]

    result = integrator.integrate(_request(binding, knowledge_package_schema=effective))
    package = result.knowledge_package

    assert type(package) is KnowledgePackage
    assert result.request_id == "request-049"
    assert result.trace_references.knowledge_package_ids == (package.id,)
    assert _store_state(store) == store_before
    cp.checkpoint("04-canonical-package-built")

    # ── Scenario D: canonical semantic preservation ───────────────────────
    assert package.objective == "Review health information"
    assert package.schema_version == 1
    assert package.provenance
    assert "fact-049-a" in package.provenance

    fact_a = next(item for item in package.facts if item.id == "fact-049-a")
    assert fact_a.kind is KnowledgeKind.FACT
    assert fact_a.confidence.value == 0.91
    assert fact_a.resource_id == binding.resource_id

    contradiction = next(
        c for c in package.contradictions if c.id == "contradiction-049"
    )
    assert contradiction.item_a_id == "fact-049-a"
    assert contradiction.item_b_id == "fact-049-b"

    adapted = result.adapted_resources[0]
    assert type(adapted) is Resource
    assert adapted.id == binding.resource_id
    assert adapted.sensitivity is SensitivityLevel.HIGHLY_SENSITIVE
    assert adapted.temporal_scope.valid_from == VALID_FROM
    assert adapted.temporal_scope.valid_until == VALID_UNTIL
    assert adapted.temporal_scope.observed_at == OBSERVED_AT
    assert adapted.temporal_scope.last_verified_at == LAST_VERIFIED_AT
    assert adapted.provenance.source_id == binding.resource_id

    assert package.resources and package.resources[0].id == binding.resource_id
    assert package.missing_information == ()
    assert package.unknowns == ()
    cp.checkpoint("05-semantics-preserved")

    # ── Scenario E: valid schema acceptance ───────────────────────────────
    assert validate_domain_knowledge_package(package, effective) is package
    assert validate_domain_knowledge_package(package, health_schema) is package
    cp.checkpoint("06-valid-schema-accepted")

    # ── Scenario F: fail-closed violation + unchanged serialization ───────
    serialized_before = package.serialize()
    unsatisfiable = DomainKnowledgePackageSchema(
        id="knowledge-package-schema:at-dp-049-strict",
        domain_id=DomainId("health"),
        version="1",
        field_policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="hypotheses",
                required_non_empty=True,
            ),
        ),
    )
    with pytest.raises(DomainKnowledgePackageValidationError) as invalid:
        validate_domain_knowledge_package(package, unsatisfiable)

    assert invalid.value.field == "hypotheses"
    assert package.serialize() == serialized_before
    cp.checkpoint("07-fail-closed-violation")

    # ── Scenario I: authority boundary ────────────────────────────────────
    opaque = DomainKnowledgePackageSchema(
        id="knowledge-package-schema:at-dp-049-opaque",
        domain_id=DomainId("health"),
        version="1",
        required_sections=("objective",),
        validator_refs=("validator:opaque-never-executed",),
    )
    # The opaque reference is carried verbatim and never resolved or executed.
    assert validate_domain_knowledge_package(package, opaque) is package
    assert opaque.to_dict()["validator_refs"] == ["validator:opaque-never-executed"]

    # No sensitivity downgrade: composition takes the strongest floor by rank.
    assert (
        compose_domain_knowledge_package_schemas(
            (opaque, health_schema)
        ).minimum_sensitivity
        is SensitivityLevel.SENSITIVE
    )
    assert (
        compose_domain_knowledge_package_schemas(
            (
                DomainKnowledgePackageSchema(
                    id="knowledge-package-schema:public",
                    domain_id=DomainId("general"),
                    version="1",
                    minimum_sensitivity=SensitivityLevel.PUBLIC,
                ),
                health_schema,
            )
        ).minimum_sensitivity
        is SensitivityLevel.SENSITIVE
    )

    # No provider/model authority surface and no permission grant.
    declared = set(health_schema.to_dict())
    assert declared == {
        "id",
        "domain_id",
        "version",
        "base_schema",
        "required_sections",
        "optional_sections",
        "prohibited_sections",
        "field_policies",
        "minimum_sensitivity",
        "validator_refs",
        "metadata",
    }
    text = json.dumps(health_schema.to_dict(), sort_keys=True).lower()
    for token in ("model", "provider", "api_key", "endpoint", "http://", "https://"):
        assert token not in text

    # No permission/sensitivity/authority attribute exists on the schema types.
    assert not hasattr(health_schema, "permissions")
    assert not hasattr(health_schema, "grants")

    # The validation helper is pure: no store writes, no opaque execution.
    store_after_validation = _store_state(store)
    validate_domain_knowledge_package(package, health_schema)
    assert _store_state(store) == store_after_validation
    cp.checkpoint("08-authority-boundary")

    # ── Scenario J: anti-fragmentation ────────────────────────────────────
    for module in PHASE_10_49_CANONICAL_MODULES:
        source = module.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module))
        defined = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert defined & PROHIBITED_PRODUCTION_NAMES == set()
        assert analyze_fragmentation(source, module.name) == []

    integration_source = (
        ROOT / "cmm" / "domains" / "cognitive_integration.py"
    ).read_text(encoding="utf-8")
    assert "KnowledgePackageBuilder(" in integration_source
    cp.checkpoint("09-anti-fragmentation")

    assert cp.points == [
        "01-real-first-party-ownership",
        "02-canonical-pack-round-trip",
        "03-effective-schema-composed",
        "04-canonical-package-built",
        "05-semantics-preserved",
        "06-valid-schema-accepted",
        "07-fail-closed-violation",
        "08-authority-boundary",
        "09-anti-fragmentation",
    ]


# ── Scenario H: irreconcilable conflict fails in both input orders ────────────


def test_dp049_general_accepts_canonical_observation_only_package() -> None:
    """A canonical non-fact package must be accepted where Domain policy allows.

    General is the broad compatibility Domain: it must not force a factual
    section merely because the common V1 template did. The package below is a
    valid canonical Phase 8 ``KnowledgePackage`` with an objective and
    observations but no facts.
    """
    general = build_general_domain_definition()
    general_schema = general.knowledge_package_schema
    assert isinstance(general_schema, DomainKnowledgePackageSchema)
    assert str(general_schema.domain_id) == "domain:general"

    package = KnowledgePackage(
        id="knowledge-package:dp049-observation-only",
        objective="Review general information",
        domain="domain:general",
        observations=(
            KnowledgeItem(
                id="observation-049-a",
                statement=(
                    "General information review: the reported situation is stable."
                ),
                kind=KnowledgeKind.OBSERVATION,
                confidence=Confidence(0.6),
                sensitivity=SensitivityLevel.INTERNAL,
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
        created_at=NOW,
    )

    assert package.facts == ()
    assert package.observations

    assert validate_domain_knowledge_package(package, general_schema) is package


def test_dp049_resolved_contradiction_preserved_without_mutation() -> None:
    """A canonical resolved contradiction is preserved unchanged.

    The package is produced by the real connected path (canonical builder via
    ``DefaultDomainCognitiveIntegrator``) and validated against the real Health
    schema, which declares ``preserve_contradictions=True``. A resolved
    contradiction that is still present in ``package.contradictions`` has not
    been erased: resolution is visibility, not erasure, so validation must
    return the identical object with identical serialization and status.
    """
    health = build_health_domain_definition()
    health_schema = health.knowledge_package_schema
    assert isinstance(health_schema, DomainKnowledgePackageSchema)
    policies = {policy.field_name: policy for policy in health_schema.field_policies}
    assert policies["contradictions"].preserve_contradictions is True

    store = _store()
    store_before = _store_state(store)
    integrator = _integrator(store)
    result = integrator.integrate(
        _request(_binding(), knowledge_package_schema=health_schema)
    )
    built = result.knowledge_package

    resolved = replace(
        built.contradictions[0],
        status=ContradictionStatus.RESOLVED,
        preferred_id="fact-049-a",
        preference_reason="Stronger clinical source",
    )
    package = replace(built, contradictions=(resolved,))
    before = package.serialize()

    validated = validate_domain_knowledge_package(package, health_schema)

    assert validated is package
    assert package.serialize() == before
    assert package.contradictions[0].status is ContradictionStatus.RESOLVED
    assert _store_state(store) == store_before


def test_dp049_real_first_party_schemas_are_substantively_differentiated() -> None:
    """Two real schemas must differ in policy body, not merely in identity.

    Health and Relationships are both ``SENSITIVE``, so the difference proven
    here cannot be attributed to ``id``, ``domain_id``, ``metadata`` or
    ``minimum_sensitivity``.
    """
    health = build_health_domain_definition().knowledge_package_schema
    relationships = build_relationships_domain_definition().knowledge_package_schema
    assert isinstance(health, DomainKnowledgePackageSchema)
    assert isinstance(relationships, DomainKnowledgePackageSchema)

    # Same sensitivity floor, so sensitivity cannot explain the difference.
    assert health.minimum_sensitivity is SensitivityLevel.SENSITIVE
    assert relationships.minimum_sensitivity is SensitivityLevel.SENSITIVE
    assert health.id != relationships.id
    assert health.domain_id != relationships.domain_id

    health_policies = {policy.field_name: policy for policy in health.field_policies}
    relationship_policies = {
        policy.field_name: policy for policy in relationships.field_policies
    }

    assert health.field_policies != relationships.field_policies

    # Health demands documented, sourced, temporally valid clinical evidence.
    assert health_policies["facts"].required_non_empty is True
    assert health_policies["facts"].require_provenance is True
    assert health_policies["facts"].require_temporal_scope is True
    assert health_policies["observations"].require_provenance is True
    assert health_policies["observations"].require_temporal_scope is True

    # Relationships keeps factual certainty optional and fences only observed
    # interaction evidence.
    assert relationship_policies["facts"].required_non_empty is False
    assert relationship_policies["facts"].require_provenance is False
    assert relationship_policies["facts"].require_temporal_scope is False
    assert relationship_policies["observations"].require_provenance is True
    assert relationship_policies["observations"].require_temporal_scope is False


def test_dp049_life_plan_canonical_path_reachability() -> None:
    """A real Life Plan package must be buildable and valid on the canonical path.

    Life Plan semantics are expressed with reachable policies only: recorded
    facts must retain provenance. The schema must not hard-require
    ``active_goals``, because the canonical ``KnowledgePackageBuilder`` invoked
    by ``DefaultDomainCognitiveIntegrator`` never populates that field. The
    package built through the real seam therefore carries no active goals while
    the real Life Plan schema still accepts it.
    """
    life_plan = build_life_plan_domain_definition()
    life_plan_schema = life_plan.knowledge_package_schema
    assert isinstance(life_plan_schema, DomainKnowledgePackageSchema)
    assert str(life_plan_schema.domain_id) == "domain:life-plan"

    life_plan_policies = {
        policy.field_name: policy for policy in life_plan_schema.field_policies
    }
    # Life Plan declares no hard field requirement at all.
    assert not any(
        policy.required_non_empty for policy in life_plan_schema.field_policies
    )
    assert life_plan_policies["facts"].require_provenance is True

    store = _store()
    store_before = _store_state(store)
    integrator = _integrator(store)
    result = integrator.integrate(
        _request(_binding(), knowledge_package_schema=life_plan_schema)
    )

    package = result.knowledge_package
    assert package is not None
    assert type(package) is KnowledgePackage
    # Builder-unreachable goal state stays empty, yet validation succeeds.
    assert package.active_goals == ()
    assert validate_domain_knowledge_package(package, life_plan_schema) is package
    assert _store_state(store) == store_before


def test_dp049_concerns_canonical_path_reachability() -> None:
    """A real Concerns package must be buildable and valid on the canonical path.

    Concerns semantics are expressed with reachable policies only: uncertainty
    and contradictions stay visible. The schema must not hard-require
    ``missing_information``, because the canonical
    ``DomainCognitiveIntegrationRequest`` seam cannot carry it. The package built
    through the real seam therefore records no missing information while the real
    Concerns schema still accepts it.
    """
    concerns = build_concerns_domain_definition()
    concerns_schema = concerns.knowledge_package_schema
    assert isinstance(concerns_schema, DomainKnowledgePackageSchema)
    assert str(concerns_schema.domain_id) == "domain:concerns"

    concerns_policies = {
        policy.field_name: policy for policy in concerns_schema.field_policies
    }
    # Concerns declares no hard field requirement at all.
    assert not any(
        policy.required_non_empty for policy in concerns_schema.field_policies
    )
    assert "missing_information" not in concerns_policies
    assert concerns_policies["contradictions"].preserve_contradictions is True

    store = _store()
    store_before = _store_state(store)
    integrator = _integrator(store)
    result = integrator.integrate(
        _request(_binding(), knowledge_package_schema=concerns_schema)
    )

    package = result.knowledge_package
    assert type(package) is KnowledgePackage
    # Integration-unreachable missing information stays empty; contradictions
    # stay visible and validation succeeds.
    assert package.missing_information == ()
    assert package.contradictions
    assert validate_domain_knowledge_package(package, concerns_schema) is package
    assert _store_state(store) == store_before


def test_dp049_distinct_policy_composition_is_most_restrictive() -> None:
    """Composing two real schemas must carry the most-restrictive combination.

    Life Plan and Relationships contribute genuinely different, reachable
    restrictions: Life Plan fences recorded facts behind provenance while
    Relationships fences observed evidence behind provenance. Neither source
    alone carries both, so the effective schema must reflect both.
    """
    life_plan = build_life_plan_domain_definition().knowledge_package_schema
    relationships = build_relationships_domain_definition().knowledge_package_schema
    assert isinstance(life_plan, DomainKnowledgePackageSchema)
    assert isinstance(relationships, DomainKnowledgePackageSchema)
    assert life_plan.field_policies != relationships.field_policies

    effective = compose_domain_knowledge_package_schemas((life_plan, relationships))
    assert isinstance(effective, EffectiveDomainKnowledgePackageSchema)
    assert effective == compose_domain_knowledge_package_schemas(
        (relationships, life_plan)
    )

    effective_policies = {
        policy.field_name: policy for policy in effective.field_policies
    }
    source_policies = [
        {policy.field_name: policy for policy in schema.field_policies}
        for schema in (life_plan, relationships)
    ]

    # Every effective field policy is the most-restrictive combination.
    for field_name, policy in effective_policies.items():
        contributing = [
            policies[field_name]
            for policies in source_policies
            if field_name in policies
        ]
        assert policy.required_non_empty == any(
            item.required_non_empty for item in contributing
        )
        assert policy.require_provenance == any(
            item.require_provenance for item in contributing
        )
        assert policy.require_temporal_scope == any(
            item.require_temporal_scope for item in contributing
        )
        assert policy.preserve_uncertainty == any(
            item.preserve_uncertainty for item in contributing
        )
        assert policy.preserve_contradictions == any(
            item.preserve_contradictions for item in contributing
        )

    # Life Plan contributes the provenance floor on recorded facts only.
    assert effective_policies["facts"].require_provenance is True
    assert effective_policies["facts"].require_temporal_scope is False
    # Relationships contributes the provenance floor on observed evidence.
    assert effective_policies["observations"].require_provenance is True

    # Neither source alone carries both restrictions.
    assert source_policies[0]["observations"].require_provenance is False
    assert source_policies[1]["facts"].require_provenance is False

    # The strongest floor wins and can never be lowered.
    assert effective.minimum_sensitivity is SensitivityLevel.SENSITIVE


@pytest.mark.parametrize("reverse", (False, True))
def test_at_dp049_irreconcilable_conflict_fails_closed(reverse: bool) -> None:
    """Required/prohibited conflict must fail deterministically in both orders."""
    requiring = DomainKnowledgePackageSchema(
        id="knowledge-package-schema:at-dp-049-requiring",
        domain_id=DomainId("health"),
        version="1",
        required_sections=("hypotheses",),
    )
    prohibiting = DomainKnowledgePackageSchema(
        id="knowledge-package-schema:at-dp-049-prohibiting",
        domain_id=DomainId("university"),
        version="1",
        prohibited_sections=("hypotheses",),
    )
    schemas = (prohibiting, requiring) if reverse else (requiring, prohibiting)

    with pytest.raises(DomainKnowledgePackageCompositionError) as conflict:
        compose_domain_knowledge_package_schemas(schemas)

    assert tuple(conflict.value.details["conflict"]) == ("hypotheses",)
