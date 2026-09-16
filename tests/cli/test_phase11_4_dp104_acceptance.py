"""Phase 11.4 — connected acceptance test ``AT-DP-104``.

Requirement: ``F11-018`` — Canonical Operational CLI
Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

This is a **connected** acceptance test, not a mock-only command test.  It
composes the real local application runtime (the official in-memory canonical
graph of ``cmm.application.local_runtime``), adapts its one
``ApplicationGateway`` with the real ``CliApplicationAdapter``, aggregates
through the real read-only ``CliDoctor``, and drives everything through the real
public root entry point ``cmm.__main__.main`` with injected dependencies and
injected streams:

* ``cmm.__main__`` / ``cmm.cli`` — the one public front door and its console
  script wrapper;
* ``cmm.application`` — the real ``ApplicationGateway``, its official services,
  the official in-memory idempotency repository and the canonical local
  composition helper;
* ``cmm.orchestration`` — the real ``Orchestrator``, its canonical decision
  repository and its recording event sink;
* ``cmm.domains`` / ``cmm.agent_runtime`` / ``cmm.runtime`` — the canonical
  owners the composed graph wires;
* the grandfathered specialized CLIs (``cmm.validation.cli`` and
  ``cmm.domains.sdk.cli`` through the root parser, ``cmm.agent_runtime``
  through its own independent parser) for the inherited-command scenarios.

Nothing here mocks ``ApplicationGateway`` or ``Orchestrator``.  Where a scenario
needs a defect, the defect is injected into a **collaborator** of the real
boundary (an orchestrator that raises, canonical evidence that is refused) so the
real boundary is the object under test, and the acceptance asserts the safe
outcome rather than the stub's.

Scenarios A–L are covered here:

* **A** entrypoint identity — one console script, the wrapper delegating to the
  root tree, and ``python -m cmm`` sharing the root parser semantics;
* **B** the inherited ``run`` / ``develop`` / ``validation`` / ``domain`` /
  ``agent`` routes still parse and dispatch;
* **C** ``status`` projected from real gateway health and capability reads;
* **D** ``ask`` reaching the real orchestrator exactly once over the CLI channel,
  recorded by the canonical decision repository;
* **E** ``plugins list`` failing closed as an unavailable capability, with no
  plugin owner created;
* **F** ``backup create`` failing closed with no file, session or orchestration
  mutation;
* **G** ``doctor`` read-only, deterministic and policy-correct;
* **H** output safety — stdout/stderr separation, parseable JSON and YAML, no
  ANSI and no traceback;
* **I** the frozen exit codes for success, usage, invalid request, not found,
  unavailable and internal failure;
* **J** no parallel CLI authority on the live dependency graph;
* **K** capability truth — every ``AVAILABLE`` descriptor has a real handler and
  every ``UNAVAILABLE`` descriptor terminates before any canonical owner;
* **L** platform compatibility — the documented automation commands in a real
  process, with pipes instead of a terminal and no platform-specific command.

Scenario D asserts the honest canonical outcome.  The public message shape
carries no structured intent, so the canonical deterministic intent resolver
answers ``NEEDS_CLARIFICATION`` before domain or agent routing; that result is
asserted instead of a fabricated model answer.

See the design and plan under ``docs/superpowers`` and the reference in
``docs/reference/phase-11-cli.md``.
"""

from __future__ import annotations

import ast
import io
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import tomllib
import yaml

import cmm.__main__ as cli_main
import cmm.cli as cli_wrapper
from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.agent_registry_service import AgentRegistryService
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.application import (
    APPLICATION_API_VERSION,
    ApplicationGateway,
    ApplicationOperation,
    ApplicationQuery,
)
from cmm.application.local_runtime import (
    LocalApplicationRuntime,
    build_local_application_runtime,
)
from cmm.cli_application import CliApplicationAdapter
from cmm.cli_commands import (
    CAPABILITY_UNAVAILABLE_CODE,
    PHASE11_4_COMMANDS,
    phase11_4_descriptor,
)
from cmm.cli_contracts import CliAvailability, CliError, CliExitCode, CliResult
from cmm.cli_doctor import DOCTOR_CHECKS, CliDoctor, DoctorCheckStatus
from cmm.domains.registry import DomainRegistry
from cmm.execution.executor_registry import ExecutorRegistry
from cmm.orchestration.agent_router import CanonicalAgentRouter
from cmm.orchestration.contracts import OrchestrationChannel
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.domain_router import CanonicalDomainRouter
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.orchestrator import Orchestrator
from cmm.platform.container import ApplicationContainer
from cmm.platform.service_registry import IntegrationServiceRegistry
from cmm.runtime.sessions import InMemorySessionStore
from cmm.workflows.engine import WorkflowEngine
from cmm.workflows.registry import InMemoryWorkflowRegistry
from kernel.llm.provider_registry import ProviderRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
CLI_COMMANDS_PATH = REPO_ROOT / "cmm" / "cli_commands.py"

#: The interpreter that runs the documented automation commands in a real
#: process, and the repository root they run from.
PYTHON_EXECUTABLE = ".venv/bin/python"
COMMAND_TIMEOUT_SECONDS = 300

ANSI_ESCAPE = "\x1b"

#: The canonical orchestration service ids this acceptance reads its evidence
#: from.  Both are bound by the official orchestration composition module.
DECISION_REPOSITORY_SERVICE_ID = "orchestration.decision_repository"
EVENT_SINK_SERVICE_ID = "orchestration.event_sink"
CONTEXT_RESOLVER_SERVICE_ID = "orchestration.context_resolver"
APPLICATION_SERVICE_ID = "application.gateway"

#: The first canonical event the orchestrator emits for an accepted request: the
#: faithful invocation count of the real pipeline.
REQUEST_RECEIVED_EVENT = "orchestration.request_received"

#: Raw internal defect text that must never reach a public CLI answer.
RAW_DEFECT_TEXT = (
    "Traceback (most recent call last): internal defect at "
    "/private/tmp/cmm-internal-detail with secret AKIA-EXAMPLE-SECRET-KEY"
)

#: Command families that existed before Phase 11.4 and must stay dispatchable.
INHERITED_FAMILIES = ("agent", "develop", "domain", "run", "validation")

#: Commands that are core to the operational CLI and must never be wired to a
#: macOS-only tool.
PLATFORM_SPECIFIC_COMMANDS = (
    "brew",
    "launchctl",
    "osascript",
    "plutil",
    "security find",
)

#: The command identities this build backs, and the ones it reserves.
AVAILABLE_COMMAND_IDS = tuple(
    descriptor.command_id
    for descriptor in PHASE11_4_COMMANDS
    if descriptor.availability is CliAvailability.AVAILABLE
)
RESERVED_COMMAND_IDS = tuple(
    descriptor.command_id
    for descriptor in PHASE11_4_COMMANDS
    if descriptor.availability is CliAvailability.UNAVAILABLE
)

#: The identifier/value arguments the roadmap shape declares for each reserved
#: subcommand that names one, so every reserved command can be dispatched exactly
#: as the roadmap names it.
RESERVED_POSITIONAL_ARGUMENTS: Mapping[str, tuple[str, ...]] = {
    "approvals.approve": ("approval-1",),
    "approvals.reject": ("approval-1",),
    "backup.restore": ("backup-1",),
    "config.set": ("key", "value"),
    "goals.create": ("Example goal",),
    "goals.pause": ("goal-1",),
    "goals.resume": ("goal-1",),
    "goals.show": ("goal-1",),
    "knowledge.inspect": ("item-1",),
    "memory.search": ("query",),
    "workflows.cancel": ("workflow-1",),
    "workflows.pause": ("workflow-1",),
    "workflows.resume": ("workflow-1",),
    "workflows.run": ("workflow-1",),
    "workflows.show": ("workflow-1",),
}

#: The one-shot ``ask`` argument shape, with one request text per case.
ONE_AVAILABLE_COMMAND_ARGUMENTS: Mapping[str, tuple[tuple[str, ...], str]] = {
    "status": (("status", "--output", "json"), ""),
    "doctor": (("doctor", "--output", "json"), ""),
    "ask": (("ask", "hello", "--actor", "user-1", "--output", "json"), ""),
    "chat": (("chat", "--actor", "user-1", "--output", "json"), "/exit\n"),
}

#: Canonical owners the CLI presentation layer must never reach: the layers below
#: the application boundary, plus the future-phase owners the roadmap reserves
#: and this build deliberately does not create.
CANONICAL_OWNER_TYPES: tuple[type, ...] = (
    AgentRegistry,
    AgentRegistryService,
    ApplicationContainer,
    CanonicalAgentRouter,
    CanonicalDomainRouter,
    DomainRegistry,
    ExecutorRegistry,
    GoalManager,
    InMemorySessionStore,
    InMemoryWorkflowRegistry,
    IntegrationServiceRegistry,
    Orchestrator,
    ProviderRegistry,
    WorkflowEngine,
)

#: Owner name fragments that must not appear on any object the presentation layer
#: can reach.  This catches an owner of a later phase (plugins, backups,
#: migrations, metrics, approvals, history) that does not exist in this build, so
#: no competing owner can be introduced behind the CLI without failing here.
FORBIDDEN_OWNER_NAME_TOKENS = (
    "agentregistry",
    "approval",
    "backup",
    "domainregistry",
    "goalrepository",
    "goalstore",
    "history",
    "metric",
    "migration",
    "plugin",
    "providerregistry",
    "sessionstore",
    "workflowengine",
)


# ── The connected fixture ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CliRun:
    """One in-process run of the public front door and its two streams."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def document(self) -> dict[str, Any]:
        """Return the structured document the run emitted."""

        return json.loads(self.stdout or self.stderr)

    @property
    def payload_stream(self) -> str:
        """Return the stream that carried the run's document."""

        return "stdout" if self.stdout else "stderr"


@dataclass(frozen=True, slots=True)
class ComposedCli:
    """The real local canonical runtime behind the real CLI presentation."""

    runtime: LocalApplicationRuntime
    adapter: CliApplicationAdapter
    doctor: CliDoctor

    def run(self, argv: Sequence[str], *, stdin_text: str = "") -> CliRun:
        """Run one command through the real root entry point, in process."""

        stdout, stderr = io.StringIO(), io.StringIO()
        exit_code = cli_main.main(
            list(argv),
            application=self.adapter,
            doctor=self.doctor,
            stdin=io.StringIO(stdin_text),
            stdout=stdout,
            stderr=stderr,
        )
        return CliRun(
            exit_code=exit_code,
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
        )

    def service(self, service_id: str) -> Any:
        """Return one canonical service the composed container publishes."""

        return self.runtime.container.get_service(service_id)

    @property
    def gateway(self) -> Any:
        return self.service(APPLICATION_SERVICE_ID)

    @property
    def decisions(self) -> InMemoryOrchestrationDecisionRepository:
        """Return the canonical decision repository the real orchestrator writes."""

        return self.service(DECISION_REPOSITORY_SERVICE_ID)

    @property
    def events(self) -> RecordingOrchestrationEventSink:
        """Return the canonical event sink the real orchestrator reports to."""

        return self.service(EVENT_SINK_SERVICE_ID)

    @property
    def session_store(self) -> InMemorySessionStore:
        """Return the official session store this graph's context resolver reads.

        The store is read through the canonical resolver that owns it, so the
        acceptance counts sessions in the store the composed graph really uses
        rather than in a copy of its own.
        """

        resolver = self.service(CONTEXT_RESOLVER_SERVICE_ID)
        return vars(resolver)["_session_store"]

    def session_count(self) -> int:
        """Return how many sessions the canonical store has committed."""

        return len(vars(self.session_store)["_backing"])

    def received_request_ids(self) -> list[str]:
        """Return the request identities the real orchestration pipeline accepted."""

        return [
            event.request_id
            for event in self.events.events()
            if event.event_type == REQUEST_RECEIVED_EVENT
        ]


@pytest.fixture
def cli() -> ComposedCli:
    """Compose one fresh, isolated local runtime behind the real CLI."""

    runtime = build_local_application_runtime()
    adapter = CliApplicationAdapter(runtime.gateway)
    return ComposedCli(runtime=runtime, adapter=adapter, doctor=CliDoctor(adapter))


def _without_volatile_correlation(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return *document* without the per-request correlation identity.

    Every run of a command answers under a fresh request id, so that one field is
    volatile by design.  Everything else must be identical for two runs of the
    same command, which is what the determinism assertions compare.
    """

    stripped = dict(document)
    metadata = stripped.get("metadata")
    if isinstance(metadata, Mapping):
        stripped["metadata"] = {
            key: value for key, value in metadata.items() if key != "request_id"
        }
    return stripped


# ══════════════════════════════════════════════════════════════════════════
# Scenario A — entrypoint identity
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_a_the_console_script_points_at_the_public_wrapper() -> None:
    declared = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))["project"]

    assert declared["scripts"] == {"cmm": "cmm.cli:main"}


def test_scenario_a_the_wrapper_delegates_to_the_root_entry_point(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``cmm.cli`` is a wrapper: the root ``main`` stays the one implementation."""

    assert cli_wrapper._official_main is cli_main.main

    wrapper_code = cli_wrapper.main(["plugins", "list", "--output", "json"])
    captured = capsys.readouterr()

    root_stdout, root_stderr = io.StringIO(), io.StringIO()
    root_code = cli_main.main(
        ["plugins", "list", "--output", "json"],
        stdout=root_stdout,
        stderr=root_stderr,
    )

    assert wrapper_code == root_code == int(CliExitCode.CAPABILITY_UNAVAILABLE)
    assert json.loads(captured.err) == json.loads(root_stderr.getvalue())
    assert captured.out == root_stdout.getvalue() == ""


def test_scenario_a_python_m_cmm_shares_the_root_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``python -m cmm`` and the root parser report the very same version."""

    with pytest.raises(SystemExit) as in_process:
        cli_main.main(["--version"])
    in_process_output = capsys.readouterr().out

    completed = subprocess.run(
        [PYTHON_EXECUTABLE, "-m", "cmm", "--version"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )

    assert in_process.value.code == completed.returncode == int(CliExitCode.SUCCESS)
    assert completed.stdout == in_process_output
    assert completed.stderr == ""


def test_scenario_a_python_m_cmm_shares_the_root_parser_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real process exposes exactly the command surface the root parser builds."""

    with pytest.raises(SystemExit) as in_process:
        cli_main.main(["--help"])
    in_process_help = capsys.readouterr().out

    completed = subprocess.run(
        [PYTHON_EXECUTABLE, "-m", "cmm", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )

    assert in_process.value.code == completed.returncode == int(CliExitCode.SUCCESS)
    # The rendered width depends on the terminal the help is rendered for, so the
    # invariant asserted here is the command surface itself, not its wrapping.
    assert _listed_commands(completed.stdout) == _listed_commands(in_process_help)
    assert set(_listed_commands(in_process_help)) >= set(INHERITED_FAMILIES)
    assert completed.stderr == ""


def _listed_commands(help_text: str) -> tuple[str, ...]:
    """Return the command names the root usage line lists, in order.

    The usage block wraps at the terminal width, so the names are read out of the
    first ``{...}`` group of the rendered help instead of out of one physical
    line.
    """

    match = re.search(r"\{([a-z,\-]+)\}", help_text)
    return () if match is None else tuple(match.group(1).split(","))


# ══════════════════════════════════════════════════════════════════════════
# Scenario B — inherited commands preserved
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_b_every_inherited_family_still_parses() -> None:
    parser = cli_main.build_parser()

    assert parser.parse_args(["validation", "run"]).command == "validation"
    assert parser.parse_args(["domain", "create", "sample"]).command == "domain"
    assert parser.parse_args(["run", "goal"]).command == "run"
    assert parser.parse_args(["develop", "goal"]).command == "develop"

    # The agent subtree owns its own independent parser and is dispatched before
    # the root parser runs; the root tree still lists it.
    assert "agent" in _listed_commands(parser.format_help())


def test_scenario_b_run_reports_a_missing_project_without_side_effects(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-project"

    code = cli_main.main(["run", "Add a hello method", "--project", str(missing)])
    captured = capsys.readouterr()

    assert code == 1
    assert f"project path does not exist: {missing}" in captured.err
    assert not missing.exists()
    assert sorted(tmp_path.iterdir()) == []


def test_scenario_b_develop_fails_closed_on_a_missing_project(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-project"

    code = cli_main.main(
        ["develop", "Create a class", "--project", str(missing), "--yes"]
    )
    captured = capsys.readouterr()

    assert code == 1
    assert "Result: failure" in captured.out
    assert sorted(tmp_path.iterdir()) == []


def test_scenario_b_validation_subtree_dispatches_through_its_own_handler(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli_main.main(
        ["validation", "inspect", "missing-validation-id", "--output", "json"]
    )
    captured = capsys.readouterr()
    document = json.loads(captured.out)

    assert code == 3
    assert document["command"] == "validation.inspect"
    assert document["success"] is False
    assert document["validation_id"] == "missing-validation-id"
    assert "validation_not_found" in document["error"]["code"]


def test_scenario_b_domain_subtree_dispatches_through_its_own_handler(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-domain-pack"

    code = cli_main.main(["domain", "validate", str(missing)])
    captured = capsys.readouterr()

    assert code == 1
    assert "does not exist or is not a directory" in captured.err
    assert sorted(tmp_path.iterdir()) == []


def test_scenario_b_agent_subtree_keeps_its_independent_parser(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``cmm agent`` is dispatched before the root parser ever sees its arguments."""

    code = cli_main.main(["agent", "--help"])
    captured = capsys.readouterr()

    assert code == 0
    assert "Agent Runtime CLI (Phase 9.22)" in captured.out
    for subcommand in ("goal", "run", "approval", "budget", "trace"):
        assert subcommand in captured.out, subcommand


# ══════════════════════════════════════════════════════════════════════════
# Scenario C — status through the real gateway
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_c_status_reports_the_canonical_health_and_capabilities(
    cli: ComposedCli,
) -> None:
    run = cli.run(["status", "--output", "json"])
    document = run.document

    assert run.exit_code == int(CliExitCode.SUCCESS)
    assert run.stderr == ""
    assert run.payload_stream == "stdout"
    assert document["command"] == "status"
    assert document["ok"] is True
    assert document["schema_version"] == "v1"

    health = cli.gateway.handle(
        ApplicationQuery(
            request_id="acceptance-health",
            api_version=APPLICATION_API_VERSION,
            operation=ApplicationOperation.HEALTH_GET,
        )
    )
    capabilities = cli.gateway.handle(
        ApplicationQuery(
            request_id="acceptance-capabilities",
            api_version=APPLICATION_API_VERSION,
            operation=ApplicationOperation.CAPABILITIES_LIST,
        )
    )

    data = document["data"]

    assert data["platform_state"] == health.data["status"]
    assert data["platform_ready"] is health.data["platform_ready"] is True
    assert data["application_api_version"] == health.data["api_version"]
    assert data["services"] == sorted(health.data["services"])
    assert [entry["capability_id"] for entry in data["capabilities"]] == sorted(
        entry["capability_id"] for entry in capabilities.data["capabilities"]
    )


def test_scenario_c_status_metadata_is_safe_and_the_result_is_deterministic(
    cli: ComposedCli,
) -> None:
    first = cli.run(["status", "--output", "json"]).document
    second = cli.run(["status", "--output", "json"]).document

    # The metadata carries the correlation identity, the public API version and
    # the handler-declared primary scalar -- no platform state of its own and no
    # internal identity of any canonical owner.
    assert set(first["metadata"]) == {"request_id", "api_version", "quiet_value"}
    assert first["metadata"]["api_version"] == APPLICATION_API_VERSION
    assert first["metadata"]["quiet_value"] == first["data"]["platform_state"]
    assert _without_volatile_correlation(first) == _without_volatile_correlation(second)


def test_scenario_c_status_owns_no_platform_state_of_its_own(cli: ComposedCli) -> None:
    """A third gateway — a copy of the composed graph — reports the same platform."""

    other = build_local_application_runtime()

    data = cli.run(["status", "--output", "json"]).document["data"]
    other_health = other.gateway.handle(
        ApplicationQuery(
            request_id="acceptance-health-other",
            api_version=APPLICATION_API_VERSION,
            operation=ApplicationOperation.HEALTH_GET,
        )
    )

    assert data["platform_state"] == other_health.data["status"]
    assert cli.gateway is not other.gateway


# ══════════════════════════════════════════════════════════════════════════
# Scenario D — ask reaches the real orchestrator over the CLI channel
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_d_ask_submits_exactly_one_canonical_request(cli: ComposedCli) -> None:
    run = cli.run(["ask", "hello", "--actor", "user-1", "--output", "json"])
    document = run.document

    assert run.exit_code == int(CliExitCode.SUCCESS)
    assert run.stderr == ""
    assert cli.received_request_ids() == [document["data"]["request_id"]]
    assert len(cli.decisions.list_for_session(document["data"]["session_id"])) == 1

    record = cli.decisions.get_by_request_id(document["data"]["request_id"])

    assert record is not None
    # The canonical pipeline saw the command line as its origin, not HTTP.
    assert record.channel is OrchestrationChannel.CLI
    assert record.session_id == document["data"]["session_id"]


def test_scenario_d_ask_reports_the_honest_canonical_outcome(cli: ComposedCli) -> None:
    """The public message shape carries no intent, so the pipeline asks for one.

    No fabricated model answer is asserted: the canonical deterministic intent
    resolver answers ``NEEDS_CLARIFICATION`` before domain or agent routing, and
    that is exactly what the public CLI document reports.
    """

    data = cli.run(["ask", "hello", "--actor", "user-1", "--output", "json"]).document[
        "data"
    ]

    assert data["status"] == "needs_clarification"
    assert data["intent"] == "unknown"
    assert data["route"] == "none"
    assert data["primary_domain"] is None
    assert data["agent_id"] is None
    assert data["workflow_id"] is None
    assert "INTENT_UNKNOWN_NEEDS_CLARIFICATION" in data["reason_codes"]


def test_scenario_d_ask_creates_one_canonical_session(cli: ComposedCli) -> None:
    assert cli.session_count() == 0

    run = cli.run(["ask", "hello", "--actor", "user-1", "--output", "json"])

    assert cli.session_count() == 1
    assert cli.session_store.load(run.document["data"]["session_id"]) is not None


def test_scenario_d_ask_reuses_an_explicit_session(cli: ComposedCli) -> None:
    created = cli.adapter.create_session(session_id="acceptance-session")

    assert created.error is None

    run = cli.run(
        [
            "ask",
            "hello",
            "--actor",
            "user-1",
            "--session",
            "acceptance-session",
            "--output",
            "json",
        ]
    )

    assert run.document["data"]["session_id"] == "acceptance-session"
    assert cli.session_count() == 1


# ══════════════════════════════════════════════════════════════════════════
# Scenario E — plugins are unavailable and no plugin owner is created
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_e_plugins_list_fails_closed_as_unavailable(cli: ComposedCli) -> None:
    before = _service_ids(cli)

    run = cli.run(["plugins", "list", "--output", "json"])
    document = run.document

    assert run.exit_code == int(CliExitCode.CAPABILITY_UNAVAILABLE)
    assert run.stdout == ""
    assert document["command"] == "plugins.list"
    assert document["ok"] is False
    assert document["error"]["code"] == CAPABILITY_UNAVAILABLE_CODE
    assert document["error"]["details"] == {"command": "plugins.list"}
    assert "Traceback" not in run.stderr
    assert _service_ids(cli) == before


def test_scenario_e_plugins_list_is_a_recognized_reserved_command() -> None:
    descriptor = phase11_4_descriptor("plugins.list")

    assert descriptor is not None
    assert descriptor.availability is CliAvailability.UNAVAILABLE


def test_scenario_e_no_plugin_owner_exists_behind_the_cli(cli: ComposedCli) -> None:
    """No plugin registry, store or service is reachable, and none is created."""

    assert _forbidden_owner_names(_reachable_cli_objects(cli)) == []
    assert not _production_defines_class("PluginRegistry")
    assert not [service for service in _service_ids(cli) if "plugin" in service]


# ══════════════════════════════════════════════════════════════════════════
# Scenario F — backups are unavailable and mutate nothing
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_f_backup_create_fails_closed_without_mutating_anything(
    cli: ComposedCli,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    sessions_before = cli.session_count()
    received_before = cli.received_request_ids()
    files_before = sorted(entry.name for entry in tmp_path.iterdir())

    run = cli.run(["backup", "create", "--output", "json"])
    document = run.document

    assert run.exit_code == int(CliExitCode.CAPABILITY_UNAVAILABLE)
    assert document["command"] == "backup.create"
    assert document["error"]["code"] == CAPABILITY_UNAVAILABLE_CODE
    assert sorted(entry.name for entry in tmp_path.iterdir()) == files_before == []
    assert cli.session_count() == sessions_before
    assert cli.received_request_ids() == received_before
    assert cli.events.events() == ()
    assert not _production_defines_class("BackupService")


# ══════════════════════════════════════════════════════════════════════════
# Scenario G — doctor is read-only, deterministic and policy-correct
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_g_doctor_reports_real_and_unavailable_checks(
    cli: ComposedCli,
) -> None:
    run = cli.run(["doctor", "--output", "json"])
    document = run.document
    checks = {check["check_id"]: check for check in document["data"]["checks"]}

    assert run.exit_code == int(CliExitCode.SUCCESS)
    assert run.stderr == ""
    assert document["command"] == "doctor"
    assert document["ok"] is True
    assert set(checks) == {spec.check_id for spec in DOCTOR_CHECKS}

    statuses = {check["status"] for check in checks.values()}
    assert DoctorCheckStatus.PASS.value in statuses
    assert DoctorCheckStatus.UNAVAILABLE.value in statuses

    assert checks["application.health"]["status"] == DoctorCheckStatus.PASS.value
    assert checks["application.health"]["details"]["platform_ready"] is True
    assert checks["kernel"]["status"] == DoctorCheckStatus.PASS.value
    assert checks["configuration"]["status"] == DoctorCheckStatus.UNAVAILABLE.value
    assert checks["plugins"]["status"] == DoctorCheckStatus.UNAVAILABLE.value
    assert document["data"]["failed"] == []


def test_scenario_g_doctor_is_read_only_and_deterministic(
    cli: ComposedCli,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    sessions_before = cli.session_count()
    files_before = sorted(entry.name for entry in tmp_path.iterdir())

    first = cli.run(["doctor", "--output", "json"])
    second = cli.run(["doctor", "--output", "json"])

    assert first.exit_code == second.exit_code == int(CliExitCode.SUCCESS)
    assert first.document["data"] == second.document["data"]
    assert cli.session_count() == sessions_before
    assert cli.events.events() == ()
    assert sorted(entry.name for entry in tmp_path.iterdir()) == files_before == []


def test_scenario_g_doctor_fails_closed_when_canonical_evidence_is_refused(
    cli: ComposedCli,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A core check that can not be certified fails the run, and the exit says so.

    The defect is injected at the doctor's only collaborator — the CLI adapter —
    so the run still executes the real doctor, the real dispatcher and the real
    exit-code policy; the gateway and the orchestrator behind it are untouched.
    """

    refused = CliResult(
        command="status",
        ok=False,
        status="failed",
        error=CliError(
            code="DEPENDENCY_UNHEALTHY",
            message="Canonical application evidence is unavailable",
        ),
    )
    monkeypatch.setattr(cli.adapter, "status", lambda: refused)

    run = cli.run(["doctor", "--output", "json"])
    document = run.document

    assert run.exit_code == int(CliExitCode.DEPENDENCY_UNHEALTHY)
    assert run.stdout == ""
    assert document["command"] == "doctor"
    assert document["ok"] is False
    assert document["status"] == "failed"
    assert document["error"]["code"] == "DEPENDENCY_UNHEALTHY"
    assert set(document["data"]["failed"]) == {
        "application.health",
        "application.capabilities",
        "services",
    }
    assert cli.events.events() == ()


# ══════════════════════════════════════════════════════════════════════════
# Scenario H — output safety
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_h_a_json_success_carries_the_payload_on_stdout(
    cli: ComposedCli,
) -> None:
    run = cli.run(["status", "--output", "json"])

    assert run.exit_code == int(CliExitCode.SUCCESS)
    assert run.stderr == ""
    assert json.loads(run.stdout) == run.document
    assert ANSI_ESCAPE not in run.stdout


def test_scenario_h_a_structured_error_carries_the_document_on_stderr(
    cli: ComposedCli,
) -> None:
    run = cli.run(["plugins", "list", "--output", "json"])

    assert run.exit_code == int(CliExitCode.CAPABILITY_UNAVAILABLE)
    assert run.stdout == ""
    assert json.loads(run.stderr)["error"]["code"] == CAPABILITY_UNAVAILABLE_CODE
    assert "Traceback" not in run.stderr
    assert ANSI_ESCAPE not in run.stderr


def test_scenario_h_yaml_and_json_describe_the_same_document(cli: ComposedCli) -> None:
    """The reserved error document is fully deterministic, so it compares exactly."""

    as_json = cli.run(["plugins", "list", "--output", "json"])
    as_yaml = cli.run(["plugins", "list", "--output", "yaml"])

    assert as_json.exit_code == as_yaml.exit_code == 5
    assert as_json.stdout == as_yaml.stdout == ""
    assert yaml.safe_load(as_yaml.stderr) == json.loads(as_json.stderr)
    assert ANSI_ESCAPE not in as_yaml.stderr


def test_scenario_h_yaml_and_json_describe_the_same_status(cli: ComposedCli) -> None:
    as_json = cli.run(["status", "--output", "json"])
    as_yaml = cli.run(["status", "--output", "yaml"])

    assert as_json.exit_code == as_yaml.exit_code == int(CliExitCode.SUCCESS)
    assert as_json.stderr == as_yaml.stderr == ""
    assert _without_volatile_correlation(
        yaml.safe_load(as_yaml.stdout)
    ) == _without_volatile_correlation(json.loads(as_json.stdout))
    assert ANSI_ESCAPE not in as_yaml.stdout


# ══════════════════════════════════════════════════════════════════════════
# Scenario I — stable exit codes
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_i_success_exits_zero(cli: ComposedCli) -> None:
    assert cli.run(["status", "--output", "json"]).exit_code == 0


def test_scenario_i_a_usage_error_exits_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(["explode"])

    captured = capsys.readouterr()

    assert exit_info.value.code == int(CliExitCode.USAGE)
    assert captured.out == ""
    assert "usage:" in captured.err


def test_scenario_i_an_ambiguous_request_exits_three(cli: ComposedCli) -> None:
    both = cli.run(
        ["ask", "hello", "--actor", "user-1", "--output", "json"], stdin_text="piped\n"
    )
    neither = cli.run(["ask", "", "--actor", "user-1", "--output", "json"])

    for run in (both, neither):
        assert run.exit_code == int(CliExitCode.INVALID_REQUEST)
        assert run.stdout == ""
        assert run.document["error"]["code"] == "INVALID_REQUEST"
        assert cli.received_request_ids() == []


def test_scenario_i_a_missing_resource_exits_four(cli: ComposedCli) -> None:
    run = cli.run(
        [
            "ask",
            "hello",
            "--actor",
            "user-1",
            "--session",
            "missing-session",
            "--output",
            "json",
        ]
    )

    assert run.exit_code == int(CliExitCode.NOT_FOUND)
    assert run.document["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert cli.session_count() == 0
    assert cli.received_request_ids() == []


def test_scenario_i_an_unavailable_capability_exits_five(cli: ComposedCli) -> None:
    assert cli.run(["plugins", "list", "--output", "json"]).exit_code == 5


def test_scenario_i_an_internal_defect_exits_ten_without_leaking_it(
    cli: ComposedCli,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect is injected into the real orchestrator; the real gateway answers.

    Replacing the gateway would test a stub, so the defect is injected into the
    canonical collaborator instead: the real application boundary has to convert
    it into its own safe failure, and the CLI has to exit with the frozen
    internal-failure code without any of the raw defect text.
    """

    def _defective_orchestrate(request: object) -> object:
        raise RuntimeError(RAW_DEFECT_TEXT)

    monkeypatch.setattr(cli.runtime.orchestrator, "orchestrate", _defective_orchestrate)

    run = cli.run(["ask", "hello", "--actor", "user-1", "--output", "json"])

    assert run.exit_code == int(CliExitCode.INTERNAL_FAILURE)
    assert run.stdout == ""
    assert run.document["error"]["code"] == "INTERNAL_FAILURE"
    for leaked in (
        RAW_DEFECT_TEXT,
        "AKIA-EXAMPLE-SECRET-KEY",
        "/private/tmp",
        "Traceback",
    ):
        assert leaked not in run.stderr
    assert cli.received_request_ids() == []


# ══════════════════════════════════════════════════════════════════════════
# Scenario J — no parallel CLI authority
# ══════════════════════════════════════════════════════════════════════════


#: The modules whose objects belong to the CLI presentation layer.  The ownership
#: walk descends into these and stops at every other object: the canonical graph
#: behind the application boundary belongs to the application layer.
CLI_PRESENTATION_MODULES = (
    "cmm.cli_application",
    "cmm.cli_commands",
    "cmm.cli_contracts",
    "cmm.cli_doctor",
    "cmm.cli_output",
)


def _owned_attributes(value: object) -> tuple[object, ...]:
    """Return the values one object owns through its instance surface."""

    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return tuple(attributes.values())
    slots = getattr(type(value), "__slots__", ())
    return tuple(
        getattr(value, name, None)
        for name in (slots if isinstance(slots, tuple) else ())
    )


def _reachable_cli_objects(cli: ComposedCli) -> tuple[object, ...]:
    """Return every object the CLI presentation layer owns or reaches directly."""

    found: list[object] = []
    seen: set[int] = set()
    frontier: list[object] = [cli.adapter, cli.doctor]

    while frontier:
        value = frontier.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        found.append(value)
        if not type(value).__module__.startswith(CLI_PRESENTATION_MODULES):
            # A canonical boundary object: recorded, never descended into.
            continue
        frontier.extend(_owned_attributes(value))

    return tuple(found)


def _forbidden_owner_names(values: Sequence[object]) -> list[str]:
    """Return the type names of *values* that name a forbidden owner."""

    return sorted(
        {
            type(value).__name__
            for value in values
            if any(
                token in type(value).__name__.lower()
                for token in FORBIDDEN_OWNER_NAME_TOKENS
            )
        }
    )


def test_scenario_j_the_cli_reaches_exactly_one_application_gateway(
    cli: ComposedCli,
) -> None:
    reachable = _reachable_cli_objects(cli)
    gateways = [value for value in reachable if isinstance(value, ApplicationGateway)]

    assert gateways == [cli.gateway]
    # A subclass would be a second entrypoint of the same boundary.
    assert type(cli.gateway) is ApplicationGateway
    assert cli.gateway is cli.runtime.gateway


def test_scenario_j_the_cli_owns_no_canonical_owner(cli: ComposedCli) -> None:
    reachable = _reachable_cli_objects(cli)

    for value in reachable:
        assert not isinstance(value, CANONICAL_OWNER_TYPES), (
            f"the CLI presentation layer reaches {type(value).__name__} directly"
        )

    assert _forbidden_owner_names(reachable) == []
    assert all(value is not cli.runtime.orchestrator for value in reachable)
    assert all(value is not cli.runtime.container for value in reachable)
    assert all(value is not cli.session_store for value in reachable)


def test_scenario_j_the_cli_owns_no_second_store_or_engine(cli: ComposedCli) -> None:
    """No competing store, engine or registry is created anywhere in the tree."""

    for name in (
        "PluginRegistry",
        "BackupService",
        "MigrationEngine",
        "MetricsStore",
        "GoalStore",
        "ApprovalStore",
        "CLIStateStore",
        "CLIRepository",
        "CLIHistoryStore",
        "CommandRegistry",
        "CommandRouter",
        "CommandRuntime",
    ):
        assert not _production_defines_class(name), name


# ══════════════════════════════════════════════════════════════════════════
# Scenario K — capability truth
# ══════════════════════════════════════════════════════════════════════════


def _dispatched_command_ids() -> frozenset[str]:
    """Return the command identities the explicit dispatcher branches on."""

    tree = ast.parse(CLI_COMMANDS_PATH.read_text(encoding="utf-8"))
    dispatch = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "dispatch_phase11_4"
    )

    dispatched: set[str] = set()
    for node in ast.walk(dispatch):
        if not isinstance(node, ast.Compare):
            continue
        if not (isinstance(node.left, ast.Name) and node.left.id == "command_id"):
            continue
        for comparator in node.comparators:
            if isinstance(comparator, ast.Constant) and isinstance(
                comparator.value, str
            ):
                dispatched.add(comparator.value)
    return frozenset(dispatched)


def test_scenario_k_every_available_descriptor_has_a_dispatch_branch() -> None:
    assert _dispatched_command_ids() == frozenset(AVAILABLE_COMMAND_IDS)


def test_scenario_k_every_available_command_runs_a_real_handler(
    cli: ComposedCli,
) -> None:
    for command_id in AVAILABLE_COMMAND_IDS:
        argv, stdin_text = ONE_AVAILABLE_COMMAND_ARGUMENTS[command_id]

        run = cli.run(argv, stdin_text=stdin_text)

        assert run.exit_code == int(CliExitCode.SUCCESS), command_id
        assert run.document["command"] == command_id
        assert run.document["ok"] is True


def test_scenario_k_every_available_descriptor_is_named_by_the_argument_table() -> None:
    """The handler table above can not silently stop covering a command."""

    assert set(ONE_AVAILABLE_COMMAND_ARGUMENTS) == set(AVAILABLE_COMMAND_IDS)


@pytest.mark.parametrize("command_id", RESERVED_COMMAND_IDS)
def test_scenario_k_a_reserved_command_terminates_before_any_canonical_owner(
    command_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composed: list[int] = []

    def _forbidden_composition() -> object:
        composed.append(1)
        raise AssertionError("a reserved command must not compose the platform")

    monkeypatch.setattr(cli_main, "build_cli_application", _forbidden_composition)

    stdout, stderr = io.StringIO(), io.StringIO()
    exit_code = cli_main.main(
        _reserved_argv(command_id),
        stdin=io.StringIO(""),
        stdout=stdout,
        stderr=stderr,
    )
    document = json.loads(stderr.getvalue())

    assert exit_code == int(CliExitCode.CAPABILITY_UNAVAILABLE)
    assert composed == []
    assert stdout.getvalue() == ""
    assert document["command"] == command_id
    assert document["error"]["code"] == CAPABILITY_UNAVAILABLE_CODE


def _reserved_argv(command_id: str) -> list[str]:
    """Return the roadmap-shaped command line of one reserved command."""

    family, _, subcommand = command_id.partition(".")
    argv = [family]
    if subcommand:
        argv.append(subcommand)
    argv.extend(RESERVED_POSITIONAL_ARGUMENTS.get(command_id, ()))
    return [*argv, "--output", "json"]


def test_scenario_k_every_reserved_command_is_reachable_from_the_root_parser() -> None:
    parser = cli_main.build_parser()

    for command_id in RESERVED_COMMAND_IDS:
        args = parser.parse_args(_reserved_argv(command_id))
        assert args.command == command_id.split(".", 1)[0], command_id

    assert len(RESERVED_COMMAND_IDS) == 25


# ══════════════════════════════════════════════════════════════════════════
# Scenario L — platform compatibility
# ══════════════════════════════════════════════════════════════════════════


def test_scenario_l_help_runs_in_a_real_process_without_a_terminal() -> None:
    completed = subprocess.run(
        [PYTHON_EXECUTABLE, "-m", "cmm", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode == int(CliExitCode.SUCCESS)
    assert completed.stderr == ""
    for family in (*INHERITED_FAMILIES, "status", "doctor", "ask", "chat", "plugins"):
        assert family in completed.stdout, family


def test_scenario_l_a_reserved_command_is_deterministic_in_a_real_process() -> None:
    def _run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON_EXECUTABLE, "-m", "cmm", "plugins", "list", "--output", "json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )

    first, second = _run(), _run()

    assert (
        first.returncode == second.returncode == int(CliExitCode.CAPABILITY_UNAVAILABLE)
    )
    assert first.stdout == second.stdout == ""
    assert first.stderr == second.stderr
    assert json.loads(first.stderr)["error"]["code"] == CAPABILITY_UNAVAILABLE_CODE
    assert "Traceback" not in first.stderr
    assert ANSI_ESCAPE not in first.stderr


def test_scenario_l_the_automation_commands_are_platform_neutral() -> None:
    """The documented automation entry points are ``python -m cmm`` and nothing else.

    Every command asserted above is the same command on macOS and on Linux: no
    shell, no Apple-specific tool and no systemd-specific tool is involved, and
    the front-door sources never name one.
    """

    for module in (CLI_COMMANDS_PATH, REPO_ROOT / "cmm" / "__main__.py"):
        source = module.read_text(encoding="utf-8")
        for command in PLATFORM_SPECIFIC_COMMANDS:
            assert command not in source, f"{module.name} names {command}"


# ── Production introspection helpers ─────────────────────────────────────────


def _service_ids(cli: ComposedCli) -> tuple[str, ...]:
    """Return the canonical service identities the composed container publishes."""

    return tuple(
        sorted(
            service.service_id for service in cli.runtime.container.snapshot().services
        )
    )


def _production_defines_class(name: str) -> bool:
    """Return whether any production module defines a class called *name*."""

    pattern = re.compile(rf"^class\s+{name}\b", re.MULTILINE)
    for root in (REPO_ROOT / "cmm", REPO_ROOT / "kernel"):
        for path in sorted(root.rglob("*.py")):
            if pattern.search(path.read_text(encoding="utf-8")):
                return True
    return False
