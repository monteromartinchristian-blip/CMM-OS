from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.permission_catalog import build_initial_permission_catalog
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_evaluator import evaluate_domain_policy

HIGH_IMPACT_CAPABILITIES = (
    PermissionCapability.COMMUNICATION_EXTERNAL,
    PermissionCapability.PUBLICATION,
    PermissionCapability.SCHEDULE_MODIFY,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.IRREVERSIBLE_CHANGE,
    PermissionCapability.KNOWLEDGE_DELETE,
    PermissionCapability.MEDICAL_DECISION,
    PermissionCapability.MEDICAL_ACTION,
    PermissionCapability.LEGAL_DECISION,
    PermissionCapability.LEGAL_ACTION,
    PermissionCapability.FINANCIAL_DECISION,
    PermissionCapability.FINANCIAL_ACTION,
    PermissionCapability.FINANCIAL_SPEND,
    PermissionCapability.PERMISSION_MODIFY,
    PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
)


def test_initial_catalog_never_silently_allows_high_impact_capabilities():
    for policy in build_initial_permission_catalog():
        for action in HIGH_IMPACT_CAPABILITIES:
            result = evaluate_domain_policy(
                policy,
                DomainPermissionRequest(
                    f"catalog:{policy.domain_id}:{action.value}",
                    action,
                    policy.domain_id,
                    "actor",
                    "session",
                    sensitivity_level=(
                        "confidential"
                        if action is PermissionCapability.SENSITIVE_INFERENCE_PERSIST
                        else None
                    ),
                ),
            )
            assert result.effect is not PermissionOutcome.ALLOW, (
                policy.domain_id,
                action.value,
            )


def test_initial_catalog_is_conservative_for_external_and_persistent_access():
    prohibited = {
        PermissionCapability.SEARCH_EXTERNAL,
        PermissionCapability.MODEL_EXTERNAL,
        PermissionCapability.MEMORY_WRITE,
    }
    for policy in build_initial_permission_catalog():
        for action in prohibited:
            result = evaluate_domain_policy(
                policy,
                DomainPermissionRequest(
                    f"catalog:{policy.domain_id}:{action.value}",
                    action,
                    policy.domain_id,
                    "actor",
                    "session",
                    sensitivity_level="internal",
                ),
            )
            assert result.effect is PermissionOutcome.DENY
