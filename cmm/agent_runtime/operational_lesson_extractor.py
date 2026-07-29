"""Phase 9.18 – Operational Lesson Extractor.

Extracts reusable operational lessons from execution traces and recovery histories
with explicit evidence requirements and fail-safe rejection when evidence is missing.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from typing import Any

from cmm.agent_runtime.enums import OperationalLessonKind
from cmm.agent_runtime.knowledge_update_contracts import (
    KnowledgeExpirationPolicy,
    OperationalLesson,
)

_INSECURE_WORKAROUND_PATTERNS = [
    re.compile(
        r"(?i)(chmod\s+777|disable\s+auth|ignore\s+ssl|no\s+verify|skip\s+validation)"
    ),
]


class OperationalLessonExtractor:
    """Extracts auditable and reusable operational lessons from runtime traces."""

    def _build_lesson(
        self,
        *,
        lesson_id_prefix: str,
        statement: str,
        kind: OperationalLessonKind,
        evidence_id: str | None,
        scope: dict[str, Any],
        confidence: float,
        source_run_id: str,
        source_goal_id: str,
        expiration_seconds: float | None = None,
    ) -> OperationalLesson | None:
        if not evidence_id:
            return None
        expiration = (
            KnowledgeExpirationPolicy(ttl_seconds=expiration_seconds)
            if expiration_seconds is not None
            else None
        )
        return OperationalLesson(
            lesson_id=f"{lesson_id_prefix}-{uuid.uuid4().hex[:8]}",
            statement=statement,
            kind=kind,
            evidence_ids=(evidence_id,),
            scope=scope,
            confidence=confidence,
            reusable=True,
            expiration=expiration,
            source_run_ids=(source_run_id,),
            source_goal_ids=(source_goal_id,),
        )

    def extract_lessons(
        self,
        outcome_eval: Any | None = None,
        completion_decision: Any | None = None,
        recovery_history: Sequence[Any] | None = None,
        operation_results: Sequence[Any] | None = None,
        validations: Sequence[Any] | None = None,
        user_confirmed_preferences: Sequence[Any] | None = None,
        source_run_id: str = "run-default",
        source_goal_id: str = "goal-default",
    ) -> tuple[OperationalLesson, ...]:
        """Extract valid OperationalLesson items adhering to strict safety rules."""
        lessons: list[OperationalLesson] = []

        if recovery_history:
            for rec in recovery_history:
                attempts = getattr(rec, "attempts", getattr(rec, "attempt_count", 1))
                recovered = getattr(rec, "recovered", getattr(rec, "success", False))
                err_msg = str(getattr(rec, "error_message", "error"))
                strat = getattr(
                    rec, "strategy", getattr(rec, "recovery_strategy", "retry")
                )
                strat_name = getattr(strat, "value", str(strat))
                rec_id = getattr(
                    rec, "rec_id", getattr(rec, "recovery_context_id", None)
                )

                if any(
                    p.search(err_msg) or p.search(strat_name)
                    for p in _INSECURE_WORKAROUND_PATTERNS
                ):
                    continue

                if recovered:
                    lesson = self._build_lesson(
                        lesson_id_prefix="les-rec",
                        statement=f"Recovery strategy '{strat_name}' successfully resolved error: {err_msg[:80]}",
                        kind=OperationalLessonKind.RECOVERY_PATTERN,
                        evidence_id=rec_id,
                        scope={"strategy": strat_name, "error_category": err_msg[:30]},
                        confidence=0.9,
                        source_run_id=source_run_id,
                        source_goal_id=source_goal_id,
                    )
                    if lesson:
                        lessons.append(lesson)
                elif attempts > 1:
                    lesson = self._build_lesson(
                        lesson_id_prefix="les-fail",
                        statement=f"Strategy '{strat_name}' failed repeatedly on error: {err_msg[:80]}",
                        kind=OperationalLessonKind.FAILURE_PATTERN,
                        evidence_id=rec_id,
                        scope={"strategy": strat_name, "error_category": err_msg[:30]},
                        confidence=0.85,
                        source_run_id=source_run_id,
                        source_goal_id=source_goal_id,
                    )
                    if lesson:
                        lessons.append(lesson)

                env_constraint = getattr(rec, "environment_constraint", None)
                if env_constraint:
                    lesson = self._build_lesson(
                        lesson_id_prefix="les-env",
                        statement=f"Environment constraint observed: {env_constraint}",
                        kind=OperationalLessonKind.ENVIRONMENT_CONSTRAINT,
                        evidence_id=rec_id,
                        scope={"constraint": str(env_constraint)},
                        confidence=0.8,
                        source_run_id=source_run_id,
                        source_goal_id=source_goal_id,
                        expiration_seconds=86_400,
                    )
                    if lesson:
                        lessons.append(lesson)

                tool_limitation = getattr(rec, "tool_limitation", None)
                if tool_limitation:
                    lesson = self._build_lesson(
                        lesson_id_prefix="les-tool",
                        statement=f"Tool limitation identified: {tool_limitation}",
                        kind=OperationalLessonKind.TOOL_LIMITATION,
                        evidence_id=rec_id,
                        scope={"limitation": str(tool_limitation)},
                        confidence=0.82,
                        source_run_id=source_run_id,
                        source_goal_id=source_goal_id,
                        expiration_seconds=86_400,
                    )
                    if lesson:
                        lessons.append(lesson)

                validation_requirement = getattr(rec, "validation_requirement", None)
                if validation_requirement:
                    lesson = self._build_lesson(
                        lesson_id_prefix="les-val",
                        statement=f"Validation requirement captured: {validation_requirement}",
                        kind=OperationalLessonKind.VALIDATION_REQUIREMENT,
                        evidence_id=rec_id,
                        scope={"requirement": str(validation_requirement)},
                        confidence=0.86,
                        source_run_id=source_run_id,
                        source_goal_id=source_goal_id,
                    )
                    if lesson:
                        lessons.append(lesson)

                dependency_behavior = getattr(rec, "dependency_behavior", None)
                if dependency_behavior:
                    lesson = self._build_lesson(
                        lesson_id_prefix="les-dep",
                        statement=f"Dependency behavior observed: {dependency_behavior}",
                        kind=OperationalLessonKind.DEPENDENCY_BEHAVIOR,
                        evidence_id=rec_id,
                        scope={"behavior": str(dependency_behavior)},
                        confidence=0.84,
                        source_run_id=source_run_id,
                        source_goal_id=source_goal_id,
                    )
                    if lesson:
                        lessons.append(lesson)

                workflow_optimization = getattr(rec, "workflow_optimization", None)
                optimization_evidence_id = getattr(
                    rec, "optimization_evidence_id", rec_id
                )
                if workflow_optimization:
                    lesson = self._build_lesson(
                        lesson_id_prefix="les-opt",
                        statement=f"Workflow optimization validated: {workflow_optimization}",
                        kind=OperationalLessonKind.WORKFLOW_OPTIMIZATION,
                        evidence_id=optimization_evidence_id,
                        scope={"optimization": str(workflow_optimization)},
                        confidence=0.87,
                        source_run_id=source_run_id,
                        source_goal_id=source_goal_id,
                        expiration_seconds=604_800,
                    )
                    if lesson:
                        lessons.append(lesson)

        if validations:
            for val in validations:
                passed = bool(
                    getattr(
                        val,
                        "passed",
                        getattr(val, "is_success", getattr(val, "success", False)),
                    )
                )
                requirement = getattr(val, "requirement", None)
                val_id = getattr(val, "result_id", getattr(val, "validation_id", None))
                if requirement and not passed:
                    lesson = self._build_lesson(
                        lesson_id_prefix="les-valreq",
                        statement=f"Validation requirement identified: {requirement}",
                        kind=OperationalLessonKind.VALIDATION_REQUIREMENT,
                        evidence_id=val_id,
                        scope={"requirement": str(requirement)},
                        confidence=0.83,
                        source_run_id=source_run_id,
                        source_goal_id=source_goal_id,
                    )
                    if lesson:
                        lessons.append(lesson)

        if operation_results:
            for op in operation_results:
                op_id = getattr(op, "execution_id", getattr(op, "operation_id", None))
                dependency_behavior = getattr(op, "dependency_behavior", None)
                if dependency_behavior:
                    lesson = self._build_lesson(
                        lesson_id_prefix="les-opdep",
                        statement=f"Dependency behavior observed in operation: {dependency_behavior}",
                        kind=OperationalLessonKind.DEPENDENCY_BEHAVIOR,
                        evidence_id=op_id,
                        scope={"behavior": str(dependency_behavior)},
                        confidence=0.81,
                        source_run_id=source_run_id,
                        source_goal_id=source_goal_id,
                    )
                    if lesson:
                        lessons.append(lesson)

        if completion_decision is not None and getattr(
            completion_decision, "decision_kind", None
        ) in ("complete", "complete_partially"):
            dec_id = getattr(completion_decision, "decision_id", None)
            reasons = list(getattr(completion_decision, "reasons", ()))
            statement = f"Goal '{source_goal_id}' completed successfully."
            if reasons:
                statement += f" Key factors: {', '.join(reasons[:2])}"
            lesson = self._build_lesson(
                lesson_id_prefix="les-succ",
                statement=statement,
                kind=OperationalLessonKind.SUCCESS_PATTERN,
                evidence_id=dec_id,
                scope={"goal_id": source_goal_id},
                confidence=getattr(completion_decision, "confidence", 0.95),
                source_run_id=source_run_id,
                source_goal_id=source_goal_id,
            )
            if lesson:
                lessons.append(lesson)

        if user_confirmed_preferences:
            for pref in user_confirmed_preferences:
                pref_id = getattr(pref, "pref_id", None)
                key = getattr(pref, "key", str(pref))
                val = getattr(pref, "value", True)
                lesson = self._build_lesson(
                    lesson_id_prefix="les-user",
                    statement=f"Confirmed user preference '{key}': {val}",
                    kind=OperationalLessonKind.USER_PREFERENCE,
                    evidence_id=pref_id,
                    scope={"preference_key": key},
                    confidence=1.0,
                    source_run_id=source_run_id,
                    source_goal_id=source_goal_id,
                )
                if lesson:
                    lessons.append(lesson)

        return tuple(lessons)
