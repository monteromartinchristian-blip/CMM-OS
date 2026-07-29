"""Phase 9.17 – Outcome State Comparator.

Compares expected state, previous state, and actual state across resource versions,
checkpoint states, transaction boundaries, and operation results to detect
expected changes, unexpected changes, missing changes, regressions, and state inconsistencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cmm.agent_runtime.errors import OutcomeStateComparisonError
from cmm.agent_runtime.outcome_evaluation_contracts import OutcomeStateSnapshot


@dataclass(frozen=True)
class StateComparisonDiff:
    """Structured diff representation resulting from OutcomeStateComparator analysis."""

    expected_changes: dict[str, Any] = field(default_factory=dict)
    actual_changes: dict[str, Any] = field(default_factory=dict)
    missing_changes: dict[str, Any] = field(default_factory=dict)
    unexpected_changes: dict[str, Any] = field(default_factory=dict)
    version_mismatches: dict[str, tuple[str, str]] = field(default_factory=dict)
    divergences: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    inconsistencies: tuple[str, ...] = field(default_factory=tuple)
    is_noop: bool = False
    data_missing: bool = False
    residual_state: dict[str, Any] = field(default_factory=dict)


class OutcomeStateComparator:
    """Deep structural and version comparator for runtime states."""

    def compare_states(
        self,
        expected_state: OutcomeStateSnapshot | dict[str, Any],
        actual_state: OutcomeStateSnapshot | dict[str, Any],
        previous_state: OutcomeStateSnapshot | dict[str, Any] | None = None,
        resource_versions: dict[str, str] | None = None,
        mandatory_resources: tuple[str, ...] = (),
    ) -> StateComparisonDiff:
        """Perform deep state comparison and return structured diff."""
        previous_state = previous_state or {}
        resource_versions = resource_versions or {}

        # Extract dict representations
        exp_res = (
            expected_state.resources
            if isinstance(expected_state, OutcomeStateSnapshot)
            else dict(expected_state)
        )
        act_res = (
            actual_state.resources
            if isinstance(actual_state, OutcomeStateSnapshot)
            else dict(actual_state)
        )
        prev_res = (
            previous_state.resources
            if isinstance(previous_state, OutcomeStateSnapshot)
            else dict(previous_state)
        )

        exp_ver = (
            expected_state.versions
            if isinstance(expected_state, OutcomeStateSnapshot)
            else {}
        )
        act_ver = (
            actual_state.versions
            if isinstance(actual_state, OutcomeStateSnapshot)
            else resource_versions
        )

        # Check mandatory resources presence
        for res_key in mandatory_resources:
            if res_key not in act_res:
                raise OutcomeStateComparisonError(
                    f"Mandatory resource {res_key!r} missing from actual state"
                )

        expected_changes: dict[str, Any] = {}
        actual_changes: dict[str, Any] = {}
        missing_changes: dict[str, Any] = {}
        unexpected_changes: dict[str, Any] = {}
        version_mismatches: dict[str, tuple[str, str]] = {}
        divergences: dict[str, tuple[Any, Any]] = {}
        inconsistencies: list[str] = []

        data_missing = not prev_res and not exp_res and not act_res

        # Analyze expected vs previous
        for k, v in exp_res.items():
            if k not in prev_res or prev_res[k] != v:
                expected_changes[k] = v

        # Analyze actual vs previous
        for k, v in act_res.items():
            if k not in prev_res or prev_res[k] != v:
                actual_changes[k] = v

        # Analyze missing changes (expected but not in actual, or actual differs from expected)
        for k, exp_v in exp_res.items():
            if k not in act_res:
                missing_changes[k] = exp_v
            elif act_res[k] != exp_v:
                divergences[k] = (exp_v, act_res[k])
                missing_changes[k] = exp_v

        # Analyze unexpected changes (in actual, but not in expected and not in previous)
        for k, act_v in act_res.items():
            if k not in exp_res and (k not in prev_res or prev_res[k] != act_v):
                unexpected_changes[k] = act_v

        # Analyze version mismatches
        for res_name, exp_v_str in exp_ver.items():
            if res_name in act_ver and act_ver[res_name] != exp_v_str:
                version_mismatches[res_name] = (exp_v_str, act_ver[res_name])
                inconsistencies.append(
                    f"Version mismatch for {res_name}: expected {exp_v_str!r}, actual {act_ver[res_name]!r}"
                )

        # Determine NO_CHANGE
        # Rules: No change is True ONLY if previous == actual AND no actual changes occurred, and data is NOT missing.
        is_noop = (
            not data_missing
            and not actual_changes
            and not unexpected_changes
            and not version_mismatches
        )

        residual_state = dict(act_res)

        return StateComparisonDiff(
            expected_changes=expected_changes,
            actual_changes=actual_changes,
            missing_changes=missing_changes,
            unexpected_changes=unexpected_changes,
            version_mismatches=version_mismatches,
            divergences=divergences,
            inconsistencies=tuple(inconsistencies),
            is_noop=is_noop,
            data_missing=data_missing,
            residual_state=residual_state,
        )
