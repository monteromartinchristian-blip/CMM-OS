from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompletionCriteria:
    all_required_nodes_completed: bool = True
    output_schema_valid: bool = True
    no_blocking_failures: bool = True
    required_approvals_granted: bool = True
    required_resources_resolved: bool = True
    minimum_successful_nodes: int | None = None
    specific_node_completed: str | None = None


def evaluate_completion_criteria(criteria: CompletionCriteria, *, completed: Iterable[str], failed: Iterable[str], skipped: Iterable[str], output_schema_valid: bool = True, required_approvals_granted: bool = True, required_resources_resolved: bool = True, required_nodes: Iterable[str] = ()) -> bool:
    completed_set = set(completed)
    failed_set = set(failed)
    required_set = set(required_nodes)
    if criteria.all_required_nodes_completed and not required_set <= completed_set:
        return False
    if criteria.no_blocking_failures and failed_set:
        return False
    if criteria.output_schema_valid and not output_schema_valid:
        return False
    if criteria.required_approvals_granted and not required_approvals_granted:
        return False
    if criteria.required_resources_resolved and not required_resources_resolved:
        return False
    if criteria.minimum_successful_nodes is not None and len(completed_set) < criteria.minimum_successful_nodes:
        return False
    return criteria.specific_node_completed is None or criteria.specific_node_completed in completed_set
