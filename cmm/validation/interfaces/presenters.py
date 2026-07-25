"""Human and JSON presenters for CMM OS Validation (Phase 7.12)."""

from __future__ import annotations

import json
from typing import Any

from ..observability.sanitization import sanitize_validation_data
from .contracts import (
    ValidationArtifactResponse,
    ValidationGateResponse,
    ValidationResultResponse,
    ValidationStatusResponse,
)


def format_json_response(
    command: str,
    success: bool,
    exit_code: int,
    validation_id: str | None,
    result: dict[str, Any] | None,
    error: dict[str, Any] | None,
) -> str:
    """Format structured CLI/API response as clean JSON.

    No non-JSON diagnostic messages are included in stdout.
    """
    payload = {
        "schema_version": 1,
        "command": command,
        "success": success,
        "exit_code": exit_code,
        "validation_id": validation_id,
        "result": sanitize_validation_data(result) if result is not None else None,
        "error": sanitize_validation_data(error) if error is not None else None,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def format_human_run(
    response: ValidationResultResponse,
    verbose: bool = False,
    quiet: bool = False,
) -> str:
    """Format validation run result for human consumption."""
    if quiet:
        return f"Validation {response.validation_id}: status={response.status}"

    lines = [
        f"Validation {response.validation_id}",
        f"Policy: {response.policy}",
        f"Status: {response.status}",
        f"Duration: {response.duration_ms}ms",
    ]

    steps_summary = f"{len(response.steps)} step(s)"
    if response.steps:
        passed = sum(1 for s in response.steps if s.get("status") == "passed")
        steps_summary += f" ({passed} passed)"
    lines.append(f"Steps: {steps_summary}")

    findings_count = len(response.blocking_findings) + len(response.warnings)
    lines.append(
        f"Findings: {findings_count} ({len(response.blocking_findings)} blocking, {len(response.warnings)} warnings)"
    )
    lines.append(f"Gate: {'allowed' if response.can_commit else 'rejected'}")
    lines.append(f"Artifacts: {len(response.artifacts)}")

    is_persisted = response.metadata.get("persisted", True)
    lines.append(f"Persisted: {'yes' if is_persisted else 'no'}")

    if verbose and response.steps:
        lines.append("")
        lines.append("Step details:")
        for step in response.steps:
            name = step.get("name", "unknown")
            st = step.get("status", "unknown")
            dur = step.get("duration_ms", 0)
            lines.append(f"  - {name}: {st} ({dur}ms)")
            if verbose and step.get("stderr"):
                lines.append(f"    stderr: {step['stderr'].strip()}")

    if verbose and response.blocking_findings:
        lines.append("")
        lines.append("Blocking findings:")
        for finding in response.blocking_findings:
            lines.append(f"  - [{finding.get('code')}] {finding.get('message')}")

    return "\n".join(lines)


def format_human_inspect(
    record_data: dict[str, Any] | ValidationStatusResponse,
    verbose: bool = False,
    quiet: bool = False,
) -> str:
    """Format execution record for human inspection."""
    if isinstance(record_data, ValidationStatusResponse):
        rec = record_data.serialize()
    else:
        rec = dict(record_data)

    vid = rec.get("id") or rec.get("validation_id")
    st = rec.get("status")

    if quiet:
        return f"Validation {vid}: status={st}"

    lines = [
        f"Validation {vid}",
        f"Status: {st}",
        f"Policy: {rec.get('policy', 'none')}",
        f"Actor: {rec.get('actor', 'none')}",
        f"Execution Mode: {rec.get('execution_mode', 'local')}",
        f"Branch: {rec.get('branch', 'none')}",
        f"Started: {rec.get('started_at', 'none')}",
        f"Completed: {rec.get('completed_at', 'none')}",
    ]

    steps = rec.get("step_results") or rec.get("steps") or ()
    lines.append(f"Steps: {len(steps)}")

    findings = rec.get("findings") or ()
    lines.append(f"Findings: {len(findings)}")

    gate_result = rec.get("gate_result")
    gate_allowed = (
        gate_result.get("allowed")
        if isinstance(gate_result, dict)
        else rec.get("gate_allowed")
    )
    lines.append(
        f"Gate: {'allowed' if gate_allowed else ('rejected' if gate_allowed is False else 'not evaluated')}"
    )

    lines.append(f"Commit Hash: {rec.get('commit_hash', 'none')}")

    if verbose and steps:
        lines.append("")
        lines.append("Steps details:")
        for s in steps:
            if isinstance(s, dict):
                lines.append(
                    f"  - {s.get('name')}: {s.get('status')} ({s.get('duration_ms', 0)}ms)"
                )

    return "\n".join(lines)


def format_human_artifacts(
    artifacts: list[ValidationArtifactResponse],
    selected_artifact: ValidationArtifactResponse | None = None,
    quiet: bool = False,
) -> str:
    """Format artifacts listing or single artifact view for human consumption."""
    if selected_artifact is not None:
        if quiet:
            return f"Artifact {selected_artifact.id}: kind={selected_artifact.kind}"
        lines = [
            f"Artifact {selected_artifact.id}",
            f"Kind: {selected_artifact.kind}",
            f"Source: {selected_artifact.source}",
            f"Path: {selected_artifact.path or 'none'}",
            f"Size: {selected_artifact.size_bytes} bytes",
            f"Findings: {len(selected_artifact.findings)}",
            f"Created: {selected_artifact.created_at.isoformat() if selected_artifact.created_at else 'none'}",
        ]
        return "\n".join(lines)

    if quiet:
        return f"Artifacts: {len(artifacts)}"

    lines = [f"Artifacts ({len(artifacts)}):"]
    if not artifacts:
        lines.append("  (none)")
    else:
        for art in artifacts:
            lines.append(
                f"  - {art.id}: kind={art.kind}, source={art.source}, size={art.size_bytes}B"
            )
    return "\n".join(lines)


def format_human_gate(
    gate: ValidationGateResponse,
    quiet: bool = False,
) -> str:
    """Format commit gate evaluation result for human consumption."""
    if quiet:
        return f"Gate: {'allowed' if gate.allowed else 'rejected'}"

    lines = [
        f"Validation Gate: {'allowed' if gate.allowed else 'rejected'}",
        f"Validation Result ID: {gate.validation_result_id}",
        f"Blocking Findings: {len(gate.blocking_findings)}",
        f"Commit Created: {'yes' if gate.commit_created else 'no'}",
        f"Commit Hash: {gate.commit_hash or 'none'}",
    ]
    if gate.reasons:
        lines.append("Reasons:")
        for r in gate.reasons:
            code = r.get("code") or r.get("reason_code") or "reason"
            msg = r.get("message") or str(r)
            lines.append(f"  - [{code}] {msg}")
    return "\n".join(lines)


__all__ = [
    "format_human_artifacts",
    "format_human_gate",
    "format_human_inspect",
    "format_human_run",
    "format_json_response",
]
