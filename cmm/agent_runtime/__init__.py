"""Phase 9 – Autonomous Agent Runtime Package.

Exports foundational contracts, enums, errors, repository, and GoalManager for Phase 9.1 and Phase 9.2.
"""

from cmm.agent_runtime.contracts import (
    AgentDefinition,
    AgentResult,
    AgentRun,
    RuntimeDecision,
)
from cmm.agent_runtime.enums import (
    AgentResultOutcome,
    AgentRuntimeStatus,
    GoalConstraintKind,
    GoalDependencyType,
    GoalKind,
    GoalStatus,
    RuntimeDecisionType,
    SuccessCriterionKind,
    SuccessCriterionStatus,
)
from cmm.agent_runtime.errors import (
    AgentRuntimeError,
    DuplicateGoalError,
    GoalCompletionError,
    GoalDependencyError,
    GoalError,
    GoalNotFoundError,
    InvalidAgentContractError,
    InvalidAgentIdentifierError,
    InvalidGoalContractError,
    InvalidGoalTransitionError,
)
from cmm.agent_runtime.goal_contracts import (
    Goal,
    GoalConstraint,
    GoalDependency,
    GoalHistoryEntry,
    GoalPriority,
    GoalQuery,
    GoalSearchResult,
    SuccessCriterion,
)
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.goal_repository import GoalRepository, InMemoryGoalRepository

__all__ = [
    "AgentDefinition",
    "AgentResult",
    "AgentResultOutcome",
    "AgentRun",
    "AgentRuntimeError",
    "AgentRuntimeStatus",
    "DuplicateGoalError",
    "Goal",
    "GoalCompletionError",
    "GoalConstraint",
    "GoalConstraintKind",
    "GoalDependency",
    "GoalDependencyError",
    "GoalDependencyType",
    "GoalError",
    "GoalHistoryEntry",
    "GoalKind",
    "GoalManager",
    "GoalNotFoundError",
    "GoalPriority",
    "GoalQuery",
    "GoalRepository",
    "GoalSearchResult",
    "GoalStatus",
    "InMemoryGoalRepository",
    "InvalidAgentContractError",
    "InvalidAgentIdentifierError",
    "InvalidGoalContractError",
    "InvalidGoalTransitionError",
    "RuntimeDecision",
    "RuntimeDecisionType",
    "SuccessCriterion",
    "SuccessCriterionKind",
    "SuccessCriterionStatus",
]
