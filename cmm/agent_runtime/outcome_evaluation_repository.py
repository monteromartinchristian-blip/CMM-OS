"""Phase 9.17 – Outcome Evaluation Repository.

Defines thread-safe in-memory repository for storing and querying
OutcomeEvaluations and GoalCompletionDecisions with fingerprint-based
idempotency verification and immutability invariants.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock

from cmm.agent_runtime.errors import (
    OutcomeEvaluationRepositoryError,
    OutcomeFingerprintError,
)
from cmm.agent_runtime.outcome_evaluation_contracts import (
    GoalCompletionDecision,
    OutcomeEvaluation,
)


class OutcomeEvaluationRepository(ABC):
    """Abstract base repository for storing and querying outcome evaluations and completion decisions."""

    @abstractmethod
    def save_evaluation(
        self, evaluation: OutcomeEvaluation, idempotency_key: str | None = None
    ) -> OutcomeEvaluation:
        """Save an outcome evaluation."""

    @abstractmethod
    def get_evaluation(self, outcome_evaluation_id: str) -> OutcomeEvaluation | None:
        """Get an evaluation by evaluation_id."""

    @abstractmethod
    def save_decision(
        self, decision: GoalCompletionDecision, idempotency_key: str | None = None
    ) -> GoalCompletionDecision:
        """Save a completion decision."""

    @abstractmethod
    def get_decision(
        self, completion_decision_id: str
    ) -> GoalCompletionDecision | None:
        """Get a decision by decision_id."""

    @abstractmethod
    def get_evaluations_by_goal(self, goal_id: str) -> tuple[OutcomeEvaluation, ...]:
        """Get all evaluations for a specific goal."""

    @abstractmethod
    def get_evaluations_by_run(
        self, agent_run_id: str
    ) -> tuple[OutcomeEvaluation, ...]:
        """Get all evaluations for a specific agent run."""

    @abstractmethod
    def get_evaluations_by_workflow(
        self, workflow_id: str
    ) -> tuple[OutcomeEvaluation, ...]:
        """Get all evaluations for a specific workflow."""

    @abstractmethod
    def get_latest_evaluation(self, goal_id: str) -> OutcomeEvaluation | None:
        """Get the latest evaluation for a goal."""

    @abstractmethod
    def get_decisions_by_goal(self, goal_id: str) -> tuple[GoalCompletionDecision, ...]:
        """Get all completion decisions for a goal."""


class InMemoryOutcomeEvaluationRepository(OutcomeEvaluationRepository):
    """Thread-safe in-memory implementation of OutcomeEvaluationRepository."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._evaluations_by_id: dict[str, OutcomeEvaluation] = {}
        self._decisions_by_id: dict[str, GoalCompletionDecision] = {}
        self._evaluations_by_goal: dict[str, list[OutcomeEvaluation]] = {}
        self._decisions_by_goal: dict[str, list[GoalCompletionDecision]] = {}
        self._evaluations_by_run: dict[str, list[OutcomeEvaluation]] = {}
        self._evaluations_by_workflow: dict[str, list[OutcomeEvaluation]] = {}
        self._idempotency_evaluations: dict[str, OutcomeEvaluation] = {}
        self._idempotency_decisions: dict[str, GoalCompletionDecision] = {}

    def save_evaluation(
        self, evaluation: OutcomeEvaluation, idempotency_key: str | None = None
    ) -> OutcomeEvaluation:
        with self._lock:
            # Check idempotency key if provided
            if idempotency_key:
                existing = self._idempotency_evaluations.get(idempotency_key)
                if existing:
                    if existing.fingerprint != evaluation.fingerprint:
                        raise OutcomeFingerprintError(
                            f"Idempotency conflict for key {idempotency_key!r}: "
                            f"fingerprint mismatch ({existing.fingerprint!r} vs {evaluation.fingerprint!r})"
                        )
                    return existing

            # Check if evaluation_id already exists
            existing_eval = self._evaluations_by_id.get(
                evaluation.outcome_evaluation_id
            )
            if existing_eval:
                if existing_eval.fingerprint != evaluation.fingerprint:
                    raise OutcomeEvaluationRepositoryError(
                        f"Cannot overwrite existing evaluation {evaluation.outcome_evaluation_id!r} "
                        "with mismatching fingerprint"
                    )
                return existing_eval

            self._evaluations_by_id[evaluation.outcome_evaluation_id] = evaluation
            self._evaluations_by_goal.setdefault(evaluation.goal_id, []).append(
                evaluation
            )
            self._evaluations_by_run.setdefault(evaluation.agent_run_id, []).append(
                evaluation
            )
            if evaluation.workflow_id:
                self._evaluations_by_workflow.setdefault(
                    evaluation.workflow_id, []
                ).append(evaluation)

            if idempotency_key:
                self._idempotency_evaluations[idempotency_key] = evaluation

            return evaluation

    def get_evaluation(self, outcome_evaluation_id: str) -> OutcomeEvaluation | None:
        with self._lock:
            return self._evaluations_by_id.get(outcome_evaluation_id)

    def save_decision(
        self, decision: GoalCompletionDecision, idempotency_key: str | None = None
    ) -> GoalCompletionDecision:
        with self._lock:
            if idempotency_key:
                existing = self._idempotency_decisions.get(idempotency_key)
                if existing:
                    if existing.fingerprint != decision.fingerprint:
                        raise OutcomeFingerprintError(
                            f"Idempotency conflict for decision key {idempotency_key!r}: "
                            f"fingerprint mismatch ({existing.fingerprint!r} vs {decision.fingerprint!r})"
                        )
                    return existing

            existing_dec = self._decisions_by_id.get(decision.completion_decision_id)
            if existing_dec:
                if existing_dec.fingerprint != decision.fingerprint:
                    raise OutcomeEvaluationRepositoryError(
                        f"Cannot overwrite existing decision {decision.completion_decision_id!r} "
                        "with mismatching fingerprint"
                    )
                return existing_dec

            self._decisions_by_id[decision.completion_decision_id] = decision
            self._decisions_by_goal.setdefault(decision.goal_id, []).append(decision)

            if idempotency_key:
                self._idempotency_decisions[idempotency_key] = decision

            return decision

    def get_decision(
        self, completion_decision_id: str
    ) -> GoalCompletionDecision | None:
        with self._lock:
            return self._decisions_by_id.get(completion_decision_id)

    def get_evaluations_by_goal(self, goal_id: str) -> tuple[OutcomeEvaluation, ...]:
        with self._lock:
            return tuple(self._evaluations_by_goal.get(goal_id, []))

    def get_evaluations_by_run(
        self, agent_run_id: str
    ) -> tuple[OutcomeEvaluation, ...]:
        with self._lock:
            return tuple(self._evaluations_by_run.get(agent_run_id, []))

    def get_evaluations_by_workflow(
        self, workflow_id: str
    ) -> tuple[OutcomeEvaluation, ...]:
        with self._lock:
            return tuple(self._evaluations_by_workflow.get(workflow_id, []))

    def get_latest_evaluation(self, goal_id: str) -> OutcomeEvaluation | None:
        with self._lock:
            evals = self._evaluations_by_goal.get(goal_id, [])
            if not evals:
                return None
            return evals[-1]

    def get_decisions_by_goal(self, goal_id: str) -> tuple[GoalCompletionDecision, ...]:
        with self._lock:
            return tuple(self._decisions_by_goal.get(goal_id, []))
