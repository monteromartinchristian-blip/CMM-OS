"""Phase 9.18 – Knowledge Candidate Extractor.

Extracts candidate knowledge items from evaluated execution results, goal outcomes,
operations, validations, recovery histories, side effects, and user preferences.
Enforces strict filtering against internal reasoning, unconfirmed preferences, secrets,
and unverified/invalidated data.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from typing import Any

from cmm.agent_runtime.enums import KnowledgeCandidateKind
from cmm.agent_runtime.knowledge_update_contracts import (
    KnowledgeProvenance,
    KnowledgeUpdateCandidate,
)

# Common secret detection patterns (tokens, passwords, private keys)
_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(api[_-]?key|secret|password|token|bearer|private[_-]?key)\s*[:=]\s*['\"]?\w+"
    ),
    re.compile(r"-----BEGIN\s+(RSA|EC|DSA|OPENSSH)\s+PRIVATE\s+KEY-----"),
)

_INTERNAL_REASONING_KEYS = {
    "chain_of_thought",
    "internal_reasoning",
    "hidden_reasoning",
    "private_reasoning",
    "scratchpad",
}


def _contains_secret_data(text: str) -> bool:
    """Helper to detect potential secret payload strings."""
    if not isinstance(text, str):
        return False
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def _contains_internal_reasoning_payload(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).strip().lower() in _INTERNAL_REASONING_KEYS:
                return True
            if _contains_internal_reasoning_payload(value):
                return True
        return False
    if isinstance(payload, (list, tuple, set)):
        return any(_contains_internal_reasoning_payload(item) for item in payload)
    return False


class KnowledgeCandidateExtractor:
    """Autonomous candidate knowledge extractor operating on evaluated runtime outputs."""

    def extract_candidates(
        self,
        outcome_eval: Any | None = None,
        completion_decision: Any | None = None,
        goal: Any | None = None,
        operation_results: Sequence[Any] | None = None,
        validations: Sequence[Any] | None = None,
        recovery_history: Sequence[Any] | None = None,
        checkpoints: Sequence[Any] | None = None,
        transaction_results: Sequence[Any] | None = None,
        side_effects: Sequence[Any] | None = None,
        regressions: Sequence[Any] | None = None,
        debt_items: Sequence[Any] | None = None,
        acquired_knowledge: Sequence[Any] | None = None,
        remaining_gaps: Sequence[Any] | None = None,
        user_confirmed_preferences: Sequence[Any] | None = None,
        generated_artifacts: Sequence[Any] | None = None,
        source_run_id: str = "run-default",
        source_goal_id: str = "goal-default",
        workflow_id: str | None = None,
        iteration_id: str | None = None,
    ) -> tuple[KnowledgeUpdateCandidate, ...]:
        """Extract candidate items across all 17 supported knowledge candidate kinds."""
        candidates: list[KnowledgeUpdateCandidate] = []

        base_prov = KnowledgeProvenance(
            source_run_id=source_run_id,
            source_goal_id=source_goal_id,
            workflow_id=workflow_id,
            iteration_id=iteration_id,
            outcome_evaluation_id=getattr(outcome_eval, "evaluation_id", None),
        )

        # 1. CREATED_GOAL candidate
        if goal is not None:
            goal_id = getattr(goal, "goal_id", str(goal))
            title = getattr(goal, "title", str(goal))
            if not _contains_secret_data(title):
                candidates.append(
                    KnowledgeUpdateCandidate(
                        candidate_id=f"cand-goal-created-{uuid.uuid4().hex[:8]}",
                        kind=KnowledgeCandidateKind.CREATED_GOAL,
                        title=f"Goal Created: {title}",
                        content={
                            "goal_id": goal_id,
                            "title": title,
                            "kind": str(getattr(goal, "kind", "general")),
                        },
                        provenance=base_prov,
                        confidence=1.0,
                        relevance_score=0.9,
                        reusable=True,
                        scope={"goal_id": goal_id},
                        evidence_ids=(goal_id,),
                    )
                )

        # 2. COMPLETED_GOAL candidate
        if completion_decision is not None and getattr(
            completion_decision, "decision_kind", None
        ) in ("complete", "complete_partially"):
            dec_kind = getattr(completion_decision, "decision_kind", "complete")
            dec_val = getattr(dec_kind, "value", str(dec_kind))
            candidates.append(
                KnowledgeUpdateCandidate(
                    candidate_id=f"cand-goal-comp-{uuid.uuid4().hex[:8]}",
                    kind=KnowledgeCandidateKind.COMPLETED_GOAL,
                    title=f"Goal Outcome: {source_goal_id} ({dec_val})",
                    content={
                        "goal_id": source_goal_id,
                        "decision": dec_val,
                        "reasons": list(getattr(completion_decision, "reasons", ())),
                    },
                    provenance=base_prov,
                    confidence=getattr(completion_decision, "confidence", 0.95),
                    relevance_score=0.95,
                    reusable=True,
                    scope={"goal_id": source_goal_id},
                    evidence_ids=(
                        getattr(completion_decision, "decision_id", source_goal_id),
                    ),
                )
            )

        # 3. OPERATION_RESULT candidates
        if operation_results:
            for op in operation_results:
                op_id = getattr(
                    op,
                    "execution_id",
                    getattr(op, "operation_id", str(uuid.uuid4().hex[:8])),
                )
                success = getattr(
                    op, "success", getattr(op, "status", "") in ("success", "completed")
                )
                summary = getattr(
                    op, "summary", getattr(op, "operation_type", "operation")
                )
                if not _contains_secret_data(str(summary)):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-op-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.OPERATION_RESULT,
                            title=f"Operation Result: {summary}",
                            content={
                                "operation_id": op_id,
                                "success": bool(success),
                                "summary": str(summary),
                            },
                            provenance=base_prov,
                            confidence=0.9 if success else 0.7,
                            relevance_score=0.8,
                            reusable=True,
                            evidence_ids=(op_id,),
                        )
                    )

        # 4. VALIDATED_STATE candidates
        if validations:
            for val in validations:
                val_id = getattr(
                    val,
                    "result_id",
                    getattr(val, "validation_id", str(uuid.uuid4().hex[:8])),
                )
                passed = getattr(val, "passed", getattr(val, "success", False))
                val_name = getattr(
                    val, "validator_name", getattr(val, "name", "validation")
                )
                if passed:
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-val-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.VALIDATED_STATE,
                            title=f"Validated State: {val_name}",
                            content={"validator": val_name, "passed": True},
                            provenance=base_prov,
                            confidence=0.98,
                            relevance_score=0.9,
                            reusable=True,
                            evidence_ids=(val_id,),
                        )
                    )

        # 5. STRUCTURAL_CHANGE candidates
        if side_effects:
            for se in side_effects:
                se_id = getattr(se, "effect_id", str(uuid.uuid4().hex[:8]))
                kind = getattr(se, "kind", getattr(se, "type", "structural_change"))
                desc = getattr(se, "description", str(se))
                if not _contains_secret_data(desc):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-struct-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.STRUCTURAL_CHANGE,
                            title=f"Structural Change: {desc[:60]}",
                            content={"change_kind": str(kind), "description": desc},
                            provenance=base_prov,
                            confidence=0.9,
                            relevance_score=0.85,
                            reusable=True,
                            evidence_ids=(se_id,),
                        )
                    )

        # 6. DECISION candidates (structured only, never freeform rationale/CoT)
        if completion_decision is not None and hasattr(
            completion_decision, "decision_kind"
        ):
            selected = getattr(completion_decision, "decision_kind", None)
            selected_value = getattr(selected, "value", str(selected))
            reasons = tuple(getattr(completion_decision, "reasons", ()))
            content = {"decision_kind": selected_value, "reasons": list(reasons)}
            if selected_value and not _contains_internal_reasoning_payload(content):
                candidates.append(
                    KnowledgeUpdateCandidate(
                        candidate_id=f"cand-dec-{uuid.uuid4().hex[:8]}",
                        kind=KnowledgeCandidateKind.DECISION,
                        title=f"Runtime Decision: {source_goal_id}",
                        content=content,
                        provenance=base_prov,
                        confidence=0.9,
                        relevance_score=0.8,
                        reusable=True,
                        evidence_ids=(
                            getattr(completion_decision, "decision_id", "dec-1"),
                        ),
                    )
                )

        # 7. CONSTRAINT candidates
        if remaining_gaps:
            for gap in remaining_gaps:
                gap_id = getattr(gap, "gap_id", str(uuid.uuid4().hex[:8]))
                gap_desc = getattr(gap, "description", str(gap))
                if not _contains_secret_data(gap_desc):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-const-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.CONSTRAINT,
                            title=f"Constraint / Knowledge Gap: {gap_desc[:60]}",
                            content={"gap_description": gap_desc},
                            provenance=base_prov,
                            confidence=0.85,
                            relevance_score=0.75,
                            reusable=True,
                            evidence_ids=(gap_id,),
                        )
                    )

        # 8. EXPLICIT_PREFERENCE candidates (Only explicit / user confirmed!)
        if user_confirmed_preferences:
            for pref in user_confirmed_preferences:
                pref_id = getattr(pref, "pref_id", str(uuid.uuid4().hex[:8]))
                key = getattr(pref, "key", getattr(pref, "name", str(pref)))
                val = getattr(pref, "value", True)
                if not _contains_secret_data(str(key)) and not _contains_secret_data(
                    str(val)
                ):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-pref-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.EXPLICIT_PREFERENCE,
                            title=f"Explicit User Preference: {key}",
                            content={"key": key, "value": val, "user_confirmed": True},
                            provenance=base_prov,
                            confidence=1.0,
                            relevance_score=0.95,
                            reusable=True,
                            evidence_ids=(pref_id,),
                        )
                    )

        # 9. REPRODUCIBLE_ERROR candidates (Requires >1 occurrence or explicit reproduction flag)
        if recovery_history:
            for rec in recovery_history:
                attempts = getattr(rec, "attempts", getattr(rec, "attempt_count", 1))
                error_msg = getattr(rec, "error_message", str(rec))
                is_reproducible = attempts > 1 or getattr(rec, "reproducible", False)
                if is_reproducible and not _contains_secret_data(error_msg):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-err-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.REPRODUCIBLE_ERROR,
                            title=f"Reproducible Error: {error_msg[:60]}",
                            content={
                                "error_message": error_msg,
                                "attempt_count": attempts,
                            },
                            provenance=base_prov,
                            confidence=0.88,
                            relevance_score=0.8,
                            reusable=True,
                            evidence_ids=(getattr(rec, "rec_id", "rec-1"),),
                        )
                    )

        # 10. FAILED_STRATEGY candidates
        if recovery_history:
            for rec in recovery_history:
                strat = getattr(rec, "failed_strategy", getattr(rec, "strategy", None))
                if strat and not getattr(rec, "recovered", False):
                    strat_name = getattr(strat, "value", str(strat))
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-failed-strat-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.FAILED_STRATEGY,
                            title=f"Failed Strategy: {strat_name}",
                            content={"strategy": strat_name},
                            provenance=base_prov,
                            confidence=0.85,
                            relevance_score=0.8,
                            reusable=True,
                            evidence_ids=(getattr(rec, "rec_id", "rec-1"),),
                        )
                    )

        # 11. SUCCESSFUL_STRATEGY candidates
        if recovery_history:
            for rec in recovery_history:
                strat = getattr(
                    rec, "recovery_strategy", getattr(rec, "strategy", None)
                )
                if strat and getattr(rec, "recovered", True):
                    strat_name = getattr(strat, "value", str(strat))
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-succ-strat-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.SUCCESSFUL_STRATEGY,
                            title=f"Successful Recovery Strategy: {strat_name}",
                            content={"strategy": strat_name},
                            provenance=base_prov,
                            confidence=0.92,
                            relevance_score=0.85,
                            reusable=True,
                            evidence_ids=(getattr(rec, "rec_id", "rec-1"),),
                        )
                    )

        # 12. DEPENDENCY candidates
        if checkpoints:
            for chk in checkpoints:
                chk_id = getattr(chk, "checkpoint_id", str(uuid.uuid4().hex[:8]))
                deps = getattr(chk, "dependencies", ())
                if deps:
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-dep-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.DEPENDENCY,
                            title=f"Dependency Mapping ({len(deps)} items)",
                            content={"dependencies": list(deps)},
                            provenance=base_prov,
                            confidence=0.9,
                            relevance_score=0.8,
                            reusable=True,
                            evidence_ids=(chk_id,),
                        )
                    )

        # 13. CONTRADICTION candidates
        if regressions:
            for reg in regressions:
                reg_id = getattr(reg, "regression_id", str(uuid.uuid4().hex[:8]))
                desc = getattr(reg, "description", str(reg))
                if not _contains_secret_data(desc):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-contra-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.CONTRADICTION,
                            title=f"State Contradiction / Regression: {desc[:60]}",
                            content={"description": desc},
                            provenance=base_prov,
                            confidence=0.9,
                            relevance_score=0.85,
                            reusable=True,
                            evidence_ids=(reg_id,),
                        )
                    )

        # 14. TECHNICAL_DEBT candidates
        if debt_items:
            for debt in debt_items:
                debt_id = getattr(debt, "debt_id", str(uuid.uuid4().hex[:8]))
                summary = getattr(debt, "summary", str(debt))
                if not _contains_secret_data(summary):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-debt-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.TECHNICAL_DEBT,
                            title=f"Technical Debt: {summary[:60]}",
                            content={"debt_summary": summary},
                            provenance=base_prov,
                            confidence=0.88,
                            relevance_score=0.8,
                            reusable=True,
                            evidence_ids=(debt_id,),
                        )
                    )

        # 15. GENERATED_ARTIFACT candidates
        if generated_artifacts:
            for art in generated_artifacts:
                art_id = getattr(art, "artifact_id", str(uuid.uuid4().hex[:8]))
                name = getattr(art, "name", str(art))
                path = getattr(art, "path", "")
                if not _contains_secret_data(name) and not _contains_secret_data(path):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-art-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.GENERATED_ARTIFACT,
                            title=f"Generated Artifact: {name}",
                            content={"name": name, "path": path},
                            provenance=base_prov,
                            confidence=0.95,
                            relevance_score=0.85,
                            reusable=True,
                            evidence_ids=(art_id,),
                        )
                    )

        # 16. NEW_CAPABILITY candidates
        if acquired_knowledge:
            for acq in acquired_knowledge:
                acq_id = getattr(acq, "knowledge_id", str(uuid.uuid4().hex[:8]))
                cap_name = getattr(acq, "topic", getattr(acq, "capability", str(acq)))
                if not _contains_secret_data(cap_name):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-cap-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.NEW_CAPABILITY,
                            title=f"Acquired Capability: {cap_name}",
                            content={"capability": cap_name},
                            provenance=base_prov,
                            confidence=0.9,
                            relevance_score=0.85,
                            reusable=True,
                            evidence_ids=(acq_id,),
                        )
                    )

        # 17. UPDATED_RESOURCE candidates
        if transaction_results:
            for tx in transaction_results:
                tx_id = getattr(tx, "transaction_id", str(uuid.uuid4().hex[:8]))
                res = getattr(tx, "resource", getattr(tx, "target", str(tx)))
                if not _contains_secret_data(str(res)):
                    candidates.append(
                        KnowledgeUpdateCandidate(
                            candidate_id=f"cand-res-{uuid.uuid4().hex[:8]}",
                            kind=KnowledgeCandidateKind.UPDATED_RESOURCE,
                            title=f"Updated Resource: {res}",
                            content={"resource": str(res)},
                            provenance=base_prov,
                            confidence=0.9,
                            relevance_score=0.8,
                            reusable=True,
                            evidence_ids=(tx_id,),
                        )
                    )

        return tuple(candidates)
