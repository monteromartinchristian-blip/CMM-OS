"""Phase 9.22 – Agent Runtime CLI Tests.

Covers contracts/result/errors, parsing, formatting, context/config/env,
root/help/version, goal/run/approval/budget/trace/event/dead-letter
commands, health/stats, exit codes, batch, security invariants, and
integration/regression against the pre-existing `cmm` CLI.
"""

from __future__ import annotations

import dataclasses
import io
import json
from pathlib import Path
from types import MappingProxyType

import pytest

from cmm.agent_runtime.agent_runtime_api_service import AgentRuntimeApiService
from cmm.agent_runtime.agent_runtime_cli_app import AgentRuntimeCliRunner, main, run
from cmm.agent_runtime.agent_runtime_cli_context import (
    ENV_ACTOR_ID,
    ENV_NO_COLOR,
    ENV_OUTPUT,
    ENV_PERMISSIONS,
    MUTATING_OPERATIONS,
    AgentRuntimeCliContextBuilder,
)
from cmm.agent_runtime.agent_runtime_cli_errors import (
    AgentRuntimeCliConfigError,
    AgentRuntimeCliError,
    AgentRuntimeCliParsingError,
    AgentRuntimeCliSecurityError,
    AgentRuntimeCliUsageError,
    AgentRuntimeCliValidationError,
)
from cmm.agent_runtime.agent_runtime_cli_formatters import (
    HumanFormatter,
    JsonFormatter,
    JsonLinesFormatter,
    QuietFormatter,
    to_serializable,
)
from cmm.agent_runtime.agent_runtime_cli_parsers import (
    parse_cursor,
    parse_decimal,
    parse_enum,
    parse_identifier,
    parse_iso_datetime,
    parse_json_file,
    parse_json_inline,
    parse_limit,
    parse_metadata,
    parse_output_format,
    parse_permissions,
)
from cmm.agent_runtime.agent_runtime_cli_result import (
    EXIT_APPROVAL_REQUIRED,
    EXIT_BUDGET_EXCEEDED,
    EXIT_CONFLICT,
    EXIT_INTERNAL_ERROR,
    EXIT_INTERRUPTED,
    EXIT_INVALID_STATE,
    EXIT_NOT_FOUND,
    EXIT_PERMISSION_DENIED,
    EXIT_POLICY_DENIED,
    EXIT_SUCCESS,
    EXIT_UNAVAILABLE,
    EXIT_USAGE_ERROR,
    AgentRuntimeCliResult,
    map_api_error_to_exit_code,
)

# ═════════════════════════════════════════════════════════════════════════
# Fixtures and helpers
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def api_service() -> AgentRuntimeApiService:
    return AgentRuntimeApiService()


@pytest.fixture()
def cli(api_service: AgentRuntimeApiService) -> AgentRuntimeCliRunner:
    return AgentRuntimeCliRunner(api_service)


ACTOR = ["--actor-id", "a1"]


def perm(*names: str) -> list[str]:
    out: list[str] = []
    for name in names:
        out += ["--permission", name]
    return out


def as_json(result: AgentRuntimeCliResult) -> dict:
    return json.loads(result.stdout)


class _FakeStdin:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


# ═════════════════════════════════════════════════════════════════════════
# Contracts / Result / Errors  (target: 20)
# ═════════════════════════════════════════════════════════════════════════


class TestResultContract:
    def test_valid_result_constructs(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="ok",
            stderr="",
            request_id="r1",
            operation="goal.get",
            status="success",
            data={"a": 1},
            error=None,
        )
        assert result.exit_code == 0
        assert result.data["a"] == 1

    def test_rejects_invalid_exit_code(self) -> None:
        with pytest.raises(ValueError):
            AgentRuntimeCliResult(
                exit_code=42,
                stdout="",
                stderr="",
                request_id=None,
                operation=None,
                status="error",
                data=None,
                error=None,
            )

    def test_rejects_non_string_stdout(self) -> None:
        with pytest.raises(TypeError):
            AgentRuntimeCliResult(
                exit_code=0,
                stdout=123,  # type: ignore[arg-type]
                stderr="",
                request_id=None,
                operation=None,
                status="success",
                data=None,
                error=None,
            )

    def test_rejects_non_string_stderr(self) -> None:
        with pytest.raises(TypeError):
            AgentRuntimeCliResult(
                exit_code=0,
                stdout="",
                stderr=123,  # type: ignore[arg-type]
                request_id=None,
                operation=None,
                status="success",
                data=None,
                error=None,
            )

    def test_data_is_frozen_mapping(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation=None,
            status="success",
            data={"nested": {"a": 1}},
            error=None,
        )
        assert isinstance(result.data, MappingProxyType)
        assert isinstance(result.data["nested"], MappingProxyType)

    def test_data_list_is_frozen_tuple(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation=None,
            status="success",
            data=[1, 2, {"x": 1}],
            error=None,
        )
        assert isinstance(result.data, tuple)
        assert isinstance(result.data[2], MappingProxyType)

    def test_result_is_immutable(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation=None,
            status="success",
            data=None,
            error=None,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.exit_code = 1  # type: ignore[misc]

    def test_mutating_original_dict_does_not_affect_result(self) -> None:
        original = {"a": 1}
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation=None,
            status="success",
            data=original,
            error=None,
        )
        original["a"] = 999
        assert result.data["a"] == 1

    def test_valid_exit_codes_accepts_130(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=130,
            stdout="",
            stderr="",
            request_id=None,
            operation=None,
            status="interrupted",
            data=None,
            error=None,
        )
        assert result.exit_code == 130


class TestExitCodeMapping:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("NOT_FOUND", EXIT_NOT_FOUND),
            ("CONFLICT", EXIT_CONFLICT),
            ("IDEMPOTENCY_CONFLICT", EXIT_CONFLICT),
            ("PERMISSION_DENIED", EXIT_PERMISSION_DENIED),
            ("POLICY_DENIED", EXIT_POLICY_DENIED),
            ("APPROVAL_REQUIRED", EXIT_APPROVAL_REQUIRED),
            ("BUDGET_EXCEEDED", EXIT_BUDGET_EXCEEDED),
            ("STATE_ERROR", EXIT_INVALID_STATE),
            ("INTERNAL_ERROR", EXIT_INTERNAL_ERROR),
            ("VALIDATION_ERROR", EXIT_USAGE_ERROR),
            ("UNSUPPORTED_OPERATION", EXIT_USAGE_ERROR),
            ("UNAVAILABLE", EXIT_UNAVAILABLE),
        ],
    )
    def test_maps_known_codes(self, code: str, expected: int) -> None:
        assert map_api_error_to_exit_code(code) == expected

    def test_unknown_code_falls_back_to_internal(self) -> None:
        assert map_api_error_to_exit_code("SOMETHING_NEW") == EXIT_INTERNAL_ERROR

    def test_none_code_falls_back_to_internal(self) -> None:
        assert map_api_error_to_exit_code(None) == EXIT_INTERNAL_ERROR

    def test_empty_string_code_falls_back_to_internal(self) -> None:
        assert map_api_error_to_exit_code("") == EXIT_INTERNAL_ERROR


class TestErrorHierarchy:
    def test_usage_error_exit_code(self) -> None:
        assert AgentRuntimeCliUsageError("x").exit_code == EXIT_USAGE_ERROR

    def test_validation_error_exit_code(self) -> None:
        assert AgentRuntimeCliValidationError("x").exit_code == EXIT_USAGE_ERROR

    def test_config_error_exit_code(self) -> None:
        assert AgentRuntimeCliConfigError("x").exit_code == EXIT_USAGE_ERROR

    def test_parsing_error_exit_code(self) -> None:
        assert AgentRuntimeCliParsingError("x").exit_code == EXIT_USAGE_ERROR

    def test_security_error_exit_code(self) -> None:
        assert AgentRuntimeCliSecurityError("x").exit_code == EXIT_USAGE_ERROR

    def test_all_are_agent_runtime_cli_error(self) -> None:
        for cls in (
            AgentRuntimeCliUsageError,
            AgentRuntimeCliValidationError,
            AgentRuntimeCliConfigError,
            AgentRuntimeCliParsingError,
            AgentRuntimeCliSecurityError,
        ):
            assert issubclass(cls, AgentRuntimeCliError)

    def test_error_message_has_no_traceback(self) -> None:
        exc = AgentRuntimeCliUsageError("simple message")
        assert "Traceback" not in str(exc)
        assert 'File "' not in str(exc)


# ═════════════════════════════════════════════════════════════════════════
# Parsing  (target: 30)
# ═════════════════════════════════════════════════════════════════════════


class TestParseJsonInline:
    def test_parses_valid_object(self) -> None:
        assert parse_json_inline('{"a": 1}') == {"a": 1}

    def test_rejects_invalid_json(self) -> None:
        with pytest.raises(AgentRuntimeCliParsingError):
            parse_json_inline("{not json")

    def test_rejects_non_object_top_level(self) -> None:
        with pytest.raises(AgentRuntimeCliParsingError):
            parse_json_inline("[1, 2, 3]")

    def test_rejects_oversized_payload(self) -> None:
        huge = json.dumps({"a": "x" * (70 * 1024)})
        with pytest.raises(AgentRuntimeCliParsingError):
            parse_json_inline(huge)

    def test_rejects_forbidden_key(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_inline('{"password": "x"}')

    def test_rejects_forbidden_string_content(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_inline('{"note": "my api_key=abc123"}')

    def test_rejects_dangerous_code_marker(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_inline('{"cmd": "eval(something)"}')

    def test_rejects_nested_forbidden_key(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_inline('{"outer": {"inner": {"secret": "x"}}}')


class TestParseJsonFile:
    def test_parses_valid_file(self, tmp_path: Path) -> None:
        path = tmp_path / "payload.json"
        path.write_text('{"a": 1}')
        assert parse_json_file(str(path)) == {"a": 1}

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AgentRuntimeCliParsingError):
            parse_json_file(str(tmp_path / "missing.json"))

    def test_directory_instead_of_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AgentRuntimeCliParsingError):
            parse_json_file(str(tmp_path))

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{broken")
        with pytest.raises(AgentRuntimeCliParsingError):
            parse_json_file(str(path))

    def test_oversized_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "big.json"
        path.write_text(json.dumps({"a": "x" * 100}))
        with pytest.raises(AgentRuntimeCliParsingError):
            parse_json_file(str(path), max_bytes=10)

    def test_non_object_top_level_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "list.json"
        path.write_text("[1,2]")
        with pytest.raises(AgentRuntimeCliParsingError):
            parse_json_file(str(path))

    def test_rejects_forbidden_key_in_file(self, tmp_path: Path) -> None:
        path = tmp_path / "secret.json"
        path.write_text('{"token": "abc"}')
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_file(str(path))

    def test_empty_path_raises(self) -> None:
        with pytest.raises(AgentRuntimeCliParsingError):
            parse_json_file("")


class TestParseMetadata:
    def test_parses_pairs(self) -> None:
        assert parse_metadata(["a=1", "b=2"]) == {"a": "1", "b": "2"}

    def test_none_returns_empty(self) -> None:
        assert parse_metadata(None) == {}

    def test_missing_equals_raises(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_metadata(["noequals"])

    def test_empty_key_raises(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_metadata(["=value"])

    def test_sensitive_key_raises(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_metadata(["password=x"])

    def test_conflicting_duplicate_raises(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_metadata(["team=alpha", "team=beta"])

    def test_identical_duplicate_is_allowed(self) -> None:
        assert parse_metadata(["team=alpha", "team=alpha"]) == {"team": "alpha"}

    def test_oversized_value_raises(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_metadata([f"k={'x' * 5000}"])


class TestParsePermissions:
    def test_parses_valid_permissions(self) -> None:
        assert parse_permissions(["goal:write", "run:read"]) == {
            "goal:write",
            "run:read",
        }

    def test_none_returns_empty_frozenset(self) -> None:
        assert parse_permissions(None) == frozenset()

    def test_rejects_missing_colon(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_permissions(["goalwrite"])

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_permissions([""])


class TestParseIsoDatetime:
    def test_parses_aware_timestamp(self) -> None:
        result = parse_iso_datetime("2026-01-01T00:00:00+00:00")
        assert result.startswith("2026-01-01T00:00:00")

    def test_normalizes_naive_to_utc(self) -> None:
        result = parse_iso_datetime("2026-01-01T00:00:00")
        assert "+00:00" in result

    def test_accepts_z_suffix(self) -> None:
        result = parse_iso_datetime("2026-01-01T00:00:00Z")
        assert "+00:00" in result

    def test_rejects_empty(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_iso_datetime("")

    def test_rejects_garbage(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_iso_datetime("not-a-date")


class TestParseDecimal:
    def test_parses_valid_decimal(self) -> None:
        from decimal import Decimal

        assert parse_decimal("10.5") == Decimal("10.5")

    def test_exact_precision_preserved(self) -> None:
        from decimal import Decimal

        assert parse_decimal("0.1") == Decimal("0.1")

    def test_rejects_empty(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_decimal("")

    def test_rejects_non_numeric(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_decimal("notanumber")

    def test_rejects_nan(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_decimal("NaN")

    def test_rejects_infinity(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_decimal("Infinity")

    def test_positive_flag_rejects_zero(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_decimal("0", positive=True)

    def test_positive_flag_rejects_negative(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_decimal("-5", positive=True)


class TestParseIdentifier:
    def test_parses_valid_identifier(self) -> None:
        assert parse_identifier("goal-1") == "goal-1"

    def test_rejects_empty(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_identifier("")

    def test_rejects_slash(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_identifier("a/b")

    def test_rejects_dotdot(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_identifier("../etc")

    def test_rejects_backslash(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_identifier("a\\b")

    def test_rejects_null_byte(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_identifier("a\x00b")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_identifier("x" * 300)


class TestParseEnumAndOutputAndLimitAndCursor:
    def test_parse_enum_accepts_valid(self) -> None:
        assert parse_enum("a", frozenset({"a", "b"})) == "a"

    def test_parse_enum_rejects_invalid(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_enum("c", frozenset({"a", "b"}))

    def test_parse_output_format_accepts_all_four(self) -> None:
        for fmt in ("human", "json", "jsonl", "quiet"):
            assert parse_output_format(fmt) == fmt

    def test_parse_output_format_rejects_invalid(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_output_format("xml")

    def test_parse_limit_valid(self) -> None:
        assert parse_limit("10") == 10

    def test_parse_limit_rejects_out_of_range(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_limit("0")

    def test_parse_limit_rejects_non_integer(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_limit("abc")

    def test_parse_cursor_valid(self) -> None:
        assert parse_cursor("abc123") == "abc123"

    def test_parse_cursor_rejects_empty(self) -> None:
        with pytest.raises(AgentRuntimeCliValidationError):
            parse_cursor("")


# ═════════════════════════════════════════════════════════════════════════
# Formatting  (target: 25)
# ═════════════════════════════════════════════════════════════════════════


class TestToSerializable:
    def test_float_becomes_decimal_string(self) -> None:
        assert to_serializable(0.1) == "0.1"

    def test_enum_becomes_value(self) -> None:
        from cmm.agent_runtime.agent_runtime_api_enums import AgentRuntimeApiStatus

        assert to_serializable(AgentRuntimeApiStatus.SUCCESS) == "success"

    def test_dataclass_becomes_dict(self) -> None:
        from cmm.agent_runtime.agent_runtime_api_contracts import GoalResponse

        response = GoalResponse(
            goal_id="g1",
            title="t",
            objective="o",
            status="active",
            goal_kind="GENERAL",
            priority=5,
        )
        result = to_serializable(response)
        assert result["goal_id"] == "g1"

    def test_sensitive_key_redacted(self) -> None:
        result = to_serializable({"password": "hunter2", "ok": "value"})
        assert result["password"] == "**REDACTED**"
        assert result["ok"] == "value"

    def test_nested_sensitive_key_redacted(self) -> None:
        result = to_serializable({"outer": {"api_key": "abc"}})
        assert result["outer"]["api_key"] == "**REDACTED**"

    def test_list_of_dicts_redacted(self) -> None:
        result = to_serializable([{"token": "x"}, {"ok": "y"}])
        assert result[0]["token"] == "**REDACTED**"
        assert result[1]["ok"] == "y"

    def test_unknown_object_becomes_placeholder(self) -> None:
        class Weird:
            pass

        assert to_serializable(Weird()) == "**UNSERIALIZABLE**"

    def test_none_passes_through(self) -> None:
        assert to_serializable(None) is None

    def test_bool_passes_through(self) -> None:
        assert to_serializable(True) is True

    def test_datetime_becomes_isoformat(self) -> None:
        from datetime import datetime, timezone

        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert to_serializable(dt) == dt.isoformat()


class TestJsonFormatter:
    def test_output_is_valid_json(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id="r1",
            operation="goal.get",
            status="success",
            data={"goal_id": "g1"},
            error=None,
        )
        text = JsonFormatter().format(result)
        parsed = json.loads(text)
        assert parsed["data"]["goal_id"] == "g1"

    def test_sort_keys_deterministic(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id="r1",
            operation="op",
            status="success",
            data={"z": 1, "a": 2},
            error=None,
        )
        text = JsonFormatter().format(result)
        assert text.index('"a"') < text.index('"z"')

    def test_error_result_is_valid_json(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=3,
            stdout="",
            stderr="",
            request_id="r1",
            operation="goal.get",
            status="error",
            data=None,
            error={"code": "NOT_FOUND", "message": "not found", "details": None},
        )
        parsed = json.loads(JsonFormatter().format(result))
        assert parsed["error"]["code"] == "NOT_FOUND"

    def test_output_is_single_line(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation=None,
            status="success",
            data={"a": 1},
            error=None,
        )
        text = JsonFormatter().format(result)
        assert "\n" not in text


class TestJsonLinesFormatter:
    def test_output_is_valid_json(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation="op",
            status="success",
            data={"a": 1},
            error=None,
        )
        parsed = json.loads(JsonLinesFormatter().format(result))
        assert parsed["data"]["a"] == 1

    def test_output_is_compact(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation=None,
            status="success",
            data={"a": 1},
            error=None,
        )
        text = JsonLinesFormatter().format(result)
        assert ", " not in text
        assert ": " not in text


class TestHumanFormatter:
    def test_success_shows_status_and_operation(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id="r1",
            operation="goal.get",
            status="success",
            data={"goal_id": "g1"},
            error=None,
        )
        text = HumanFormatter().format(result)
        assert "goal.get" in text
        assert "goal_id: g1" in text

    def test_error_shows_code_and_message(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=3,
            stdout="",
            stderr="",
            request_id="r1",
            operation="goal.get",
            status="error",
            data=None,
            error={"code": "NOT_FOUND", "message": "Goal not found", "details": None},
        )
        text = HumanFormatter().format(result)
        assert "NOT_FOUND" in text
        assert "Goal not found" in text

    def test_no_stack_trace_leaked(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=1,
            stdout="",
            stderr="",
            request_id=None,
            operation=None,
            status="error",
            data=None,
            error={
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": None,
            },
        )
        text = HumanFormatter().format(result)
        assert "Traceback" not in text

    def test_deterministic_key_order(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation=None,
            status="success",
            data={"zebra": 1, "alpha": 2},
            error=None,
        )
        text = HumanFormatter().format(result)
        assert text.index("alpha") < text.index("zebra")


class TestQuietFormatter:
    def test_returns_primary_id(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation="goal.create",
            status="success",
            data={"goal_id": "g1", "title": "x"},
            error=None,
        )
        assert QuietFormatter().format(result) == "g1"

    def test_returns_total_when_no_id(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=None,
            operation="goal.list",
            status="success",
            data={"items": [], "total": 5},
            error=None,
        )
        assert QuietFormatter().format(result) == "5"

    def test_does_not_hide_errors(self) -> None:
        result = AgentRuntimeCliResult(
            exit_code=3,
            stdout="",
            stderr="",
            request_id=None,
            operation="goal.get",
            status="error",
            data=None,
            error={"code": "NOT_FOUND", "message": "missing", "details": None},
        )
        text = QuietFormatter().format(result)
        assert "NOT_FOUND" in text
        assert "missing" in text


# ═════════════════════════════════════════════════════════════════════════
# Context / Config / Env  (target: 25)
# ═════════════════════════════════════════════════════════════════════════


class TestContextBuilderPrecedence:
    def test_cli_actor_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_ACTOR_ID, "env-actor")
        builder = AgentRuntimeCliContextBuilder()
        ctx = builder.build(
            operation="goal.get", actor_id="cli-actor", permissions=None, config={}
        )
        assert ctx.actor == "cli-actor"

    def test_env_actor_wins_over_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_ACTOR_ID, "env-actor")
        builder = AgentRuntimeCliContextBuilder()
        ctx = builder.build(
            operation="goal.get",
            actor_id=None,
            permissions=None,
            config={"actor_id": "config-actor"},
        )
        assert ctx.actor == "env-actor"

    def test_config_actor_used_when_no_cli_or_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ENV_ACTOR_ID, raising=False)
        builder = AgentRuntimeCliContextBuilder()
        ctx = builder.build(
            operation="goal.get",
            actor_id=None,
            permissions=None,
            config={"actor_id": "config-actor"},
        )
        assert ctx.actor == "config-actor"

    def test_default_readonly_actor_for_read_operation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ENV_ACTOR_ID, raising=False)
        builder = AgentRuntimeCliContextBuilder()
        ctx = builder.build(
            operation="goal.get", actor_id=None, permissions=None, config={}
        )
        assert ctx.actor

    def test_mutating_operation_without_actor_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ENV_ACTOR_ID, raising=False)
        builder = AgentRuntimeCliContextBuilder()
        with pytest.raises(AgentRuntimeCliUsageError):
            builder.build(
                operation="goal.create", actor_id=None, permissions=None, config={}
            )

    def test_all_documented_mutating_operations_require_actor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ENV_ACTOR_ID, raising=False)
        builder = AgentRuntimeCliContextBuilder()
        for op in MUTATING_OPERATIONS:
            with pytest.raises(AgentRuntimeCliUsageError):
                builder.build(operation=op, actor_id=None, permissions=None, config={})

    def test_cli_permissions_win_over_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_PERMISSIONS, "run:read")
        builder = AgentRuntimeCliContextBuilder()
        ctx = builder.build(
            operation="goal.get",
            actor_id="a1",
            permissions=frozenset({"goal:read"}),
            config={},
        )
        assert ctx.permissions == frozenset({"goal:read"})

    def test_env_permissions_parsed_from_csv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_PERMISSIONS, "goal:read,run:read")
        builder = AgentRuntimeCliContextBuilder()
        ctx = builder.build(
            operation="goal.get", actor_id="a1", permissions=None, config={}
        )
        assert ctx.permissions == frozenset({"goal:read", "run:read"})

    def test_no_implicit_permissions_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ENV_PERMISSIONS, raising=False)
        builder = AgentRuntimeCliContextBuilder()
        ctx = builder.build(
            operation="goal.get", actor_id="a1", permissions=None, config={}
        )
        assert ctx.permissions == frozenset()

    def test_only_allowlisted_env_vars_are_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CMM_AGENT_NOT_A_REAL_VAR", "value")
        builder = AgentRuntimeCliContextBuilder()
        assert builder._env_get("CMM_AGENT_NOT_A_REAL_VAR") is None


class TestOutputAndNoColorResolution:
    def test_cli_output_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_OUTPUT, "json")
        builder = AgentRuntimeCliContextBuilder()
        assert builder.resolve_output_format(cli_output="human", config={}) == "human"

    def test_env_output_used_when_no_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_OUTPUT, "json")
        builder = AgentRuntimeCliContextBuilder()
        assert builder.resolve_output_format(cli_output=None, config={}) == "json"

    def test_config_output_used_last(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_OUTPUT, raising=False)
        builder = AgentRuntimeCliContextBuilder()
        assert (
            builder.resolve_output_format(cli_output=None, config={"output": "quiet"})
            == "quiet"
        )

    def test_no_color_env_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_NO_COLOR, "true")
        builder = AgentRuntimeCliContextBuilder()
        assert builder.resolve_no_color(cli_no_color=False, config={}) is True

    def test_no_color_default_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_NO_COLOR, raising=False)
        builder = AgentRuntimeCliContextBuilder()
        assert builder.resolve_no_color(cli_no_color=False, config={}) is False


class TestConfigFile:
    def test_loads_valid_config(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text(
            json.dumps({"actor_id": "cfg-actor", "permissions": ["goal:read"]})
        )
        builder = AgentRuntimeCliContextBuilder()
        config = builder.load_config(str(path))
        assert config["actor_id"] == "cfg-actor"
        assert config["permissions"] == ["goal:read"]

    def test_missing_config_raises(self, tmp_path: Path) -> None:
        builder = AgentRuntimeCliContextBuilder()
        with pytest.raises(AgentRuntimeCliConfigError):
            builder.load_config(str(tmp_path / "missing.json"))

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not json")
        builder = AgentRuntimeCliContextBuilder()
        with pytest.raises(AgentRuntimeCliConfigError):
            builder.load_config(str(path))

    def test_oversized_config_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "big.json"
        path.write_text(json.dumps({"actor_id": "x" * (128 * 1024)}))
        builder = AgentRuntimeCliContextBuilder()
        with pytest.raises(AgentRuntimeCliConfigError):
            builder.load_config(str(path))

    def test_invalid_permissions_type_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"permissions": "not-a-list"}))
        builder = AgentRuntimeCliContextBuilder()
        with pytest.raises(AgentRuntimeCliConfigError):
            builder.load_config(str(path))

    def test_invalid_actor_id_type_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"actor_id": 123}))
        builder = AgentRuntimeCliContextBuilder()
        with pytest.raises(AgentRuntimeCliConfigError):
            builder.load_config(str(path))

    def test_unknown_extra_keys_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"actor_id": "cfg", "totally_unknown_field": "x"}))
        builder = AgentRuntimeCliContextBuilder()
        config = builder.load_config(str(path))
        assert "totally_unknown_field" not in config

    def test_no_config_path_returns_empty(self) -> None:
        builder = AgentRuntimeCliContextBuilder()
        assert builder.load_config(None) == {}

    def test_config_via_symlink_loads(self, tmp_path: Path) -> None:
        real = tmp_path / "real.json"
        real.write_text(json.dumps({"actor_id": "linked"}))
        link = tmp_path / "link.json"
        link.symlink_to(real)
        builder = AgentRuntimeCliContextBuilder()
        config = builder.load_config(str(link))
        assert config["actor_id"] == "linked"

    def test_broken_symlink_raises(self, tmp_path: Path) -> None:
        link = tmp_path / "broken.json"
        link.symlink_to(tmp_path / "does-not-exist.json")
        builder = AgentRuntimeCliContextBuilder()
        with pytest.raises(AgentRuntimeCliConfigError):
            builder.load_config(str(link))


# ═════════════════════════════════════════════════════════════════════════
# Root / Help / Version  (target: 15)
# ═════════════════════════════════════════════════════════════════════════


class TestRootHelpVersion:
    def test_help_exits_zero(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["--help"])
        assert result.exit_code == 0

    def test_help_shows_usage(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["--help"])
        assert "usage" in result.stdout.lower()

    def test_help_lists_all_resources(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["--help"])
        for resource in (
            "goal",
            "run",
            "approval",
            "budget",
            "trace",
            "event",
            "batch",
        ):
            assert resource in result.stdout

    def test_version_exits_zero(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["--version"])
        assert result.exit_code == 0

    def test_version_is_stable_across_calls(self, cli: AgentRuntimeCliRunner) -> None:
        first = cli.run(["--version"]).stdout
        second = cli.run(["--version"]).stdout
        assert first == second

    def test_version_contains_semver_like_string(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["--version"])
        assert "9.22" in result.stdout

    def test_subcommand_help_works(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["goal", "--help"])
        assert result.exit_code == 0
        assert "create" in result.stdout

    def test_help_does_not_touch_api_service(self) -> None:
        runner = AgentRuntimeCliRunner(api_service=None)
        result = runner.run(["--help"])
        assert result.exit_code == 0
        assert runner._api_service is None

    def test_no_resource_is_usage_error(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run([])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_unknown_resource_is_usage_error(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["not-a-real-resource"])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_no_resource_error_is_valid_json_when_requested(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["--output", "json"])
        parsed = json.loads(result.stderr)
        assert parsed["status"] == "error"

    def test_json_and_output_json_are_equivalent(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        a = cli.run(["health", "--json", *perm("system:read")])
        b = cli.run(["health", "--output", "json", *perm("system:read")])
        data_a = dict(json.loads(a.stdout)["data"])
        data_b = dict(json.loads(b.stdout)["data"])
        data_a.pop("timestamp", None)
        data_b.pop("timestamp", None)
        assert data_a == data_b

    def test_quiet_and_output_quiet_are_equivalent(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        a = cli.run(["health", "--quiet", *perm("system:read")])
        b = cli.run(["health", "--output", "quiet", *perm("system:read")])
        assert a.stdout == b.stdout

    def test_json_quiet_conflict_is_usage_error(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["health", "--json", "--quiet"])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_output_json_conflicts_with_quiet_flag(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["health", "--output", "json", "--quiet"])
        assert result.exit_code == EXIT_USAGE_ERROR


# ═════════════════════════════════════════════════════════════════════════
# Goals  (target: 20)
# ═════════════════════════════════════════════════════════════════════════


class TestGoalCommands:
    def test_create_requires_actor(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["goal", "create", "--title", "t", "--objective", "o"])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_create_requires_permission(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["goal", "create", "--title", "t", "--objective", "o", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_create_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["title"] == "t"

    def test_create_with_metadata(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                "--metadata",
                "team=alpha",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        assert result.data["context"]["team"] == "alpha"

    def test_create_with_priority(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                "--priority",
                "10",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        assert result.data["priority"] == 10

    def test_get_not_found(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["goal", "get", "no-such-goal", *ACTOR, *perm("goal:read")])
        assert result.exit_code == EXIT_NOT_FOUND

    def test_get_after_create(self, cli: AgentRuntimeCliRunner) -> None:
        created = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        goal_id = created.data["goal_id"]
        result = cli.run(["goal", "get", goal_id, *ACTOR, *perm("goal:read")])
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["goal_id"] == goal_id

    def test_list_returns_created_goals(self, cli: AgentRuntimeCliRunner) -> None:
        cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        result = cli.run(["goal", "list", *ACTOR, *perm("goal:read")])
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["total"] >= 1

    def test_list_accepts_filters_without_error(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "goal",
                "list",
                "--status",
                "active",
                "--limit",
                "10",
                *ACTOR,
                *perm("goal:read"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS

    def test_update_requires_a_change(self, cli: AgentRuntimeCliRunner) -> None:
        created = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        goal_id = created.data["goal_id"]
        result = cli.run(["goal", "update", goal_id, *ACTOR, *perm("goal:write")])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_update_title_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        created = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        goal_id = created.data["goal_id"]
        result = cli.run(
            [
                "goal",
                "update",
                goal_id,
                "--title",
                "new title",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["title"] == "new title"

    def test_prioritize_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        created = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        goal_id = created.data["goal_id"]
        result = cli.run(
            ["goal", "prioritize", goal_id, "20", *ACTOR, *perm("goal:write")]
        )
        assert result.data["priority"] == 20

    def test_prioritize_rejects_non_integer(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["goal", "prioritize", "g1", "abc", *ACTOR, *perm("goal:write")]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_pause_then_resume(self, cli: AgentRuntimeCliRunner) -> None:
        created = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        goal_id = created.data["goal_id"]
        paused = cli.run(
            ["goal", "pause", goal_id, "--reason", "test", *ACTOR, *perm("goal:write")]
        )
        assert paused.data["status"] == "paused"
        resumed = cli.run(["goal", "resume", goal_id, *ACTOR, *perm("goal:write")])
        assert resumed.data["status"] == "active"

    def test_cancel_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        created = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        goal_id = created.data["goal_id"]
        result = cli.run(["goal", "cancel", goal_id, *ACTOR, *perm("goal:write")])
        assert result.data["status"] == "cancelled"

    def test_cancel_completed_goal_is_state_error(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        created = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        goal_id = created.data["goal_id"]
        cli.run(["goal", "cancel", goal_id, *ACTOR, *perm("goal:write")])
        result = cli.run(["goal", "cancel", goal_id, *ACTOR, *perm("goal:write")])
        assert result.exit_code == EXIT_INVALID_STATE

    def test_does_not_fake_success_on_missing_goal(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            ["goal", "pause", "does-not-exist", *ACTOR, *perm("goal:write")]
        )
        assert result.exit_code == EXIT_NOT_FOUND
        assert result.status != "success"

    def test_create_empty_title_is_validation_error(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "goal",
                "create",
                "--title",
                "",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_request_id_is_propagated(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            [
                "goal",
                "get",
                "no-such-goal",
                "--request-id",
                "custom-req-1",
                *ACTOR,
                *perm("goal:read"),
            ]
        )
        assert result.request_id == "custom-req-1"


# ═════════════════════════════════════════════════════════════════════════
# Runs  (target: 18)
# ═════════════════════════════════════════════════════════════════════════


class TestRunCommands:
    def _make_goal(self, cli: AgentRuntimeCliRunner) -> str:
        result = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        return result.data["goal_id"]

    def test_start_requires_actor(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["run", "start", "goal-1"])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_start_missing_goal_is_not_found(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["run", "start", "no-such-goal", *ACTOR, *perm("run:write")])
        assert result.exit_code == EXIT_NOT_FOUND

    def test_start_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        goal_id = self._make_goal(cli)
        result = cli.run(["run", "start", goal_id, *ACTOR, *perm("run:write")])
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["goal_id"] == goal_id

    def test_start_on_paused_goal_is_state_error(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        goal_id = self._make_goal(cli)
        cli.run(["goal", "pause", goal_id, *ACTOR, *perm("goal:write")])
        result = cli.run(["run", "start", goal_id, *ACTOR, *perm("run:write")])
        assert result.exit_code == EXIT_INVALID_STATE

    def test_start_with_autonomy_level(self, cli: AgentRuntimeCliRunner) -> None:
        goal_id = self._make_goal(cli)
        result = cli.run(
            [
                "run",
                "start",
                goal_id,
                "--autonomy-level",
                "2",
                *ACTOR,
                *perm("run:write"),
            ]
        )
        assert result.data["autonomy_level"] == 2

    def test_get_not_found(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["run", "get", "no-such-run", *ACTOR, *perm("run:read")])
        assert result.exit_code == EXIT_NOT_FOUND

    def test_get_after_start(self, cli: AgentRuntimeCliRunner) -> None:
        goal_id = self._make_goal(cli)
        started = cli.run(["run", "start", goal_id, *ACTOR, *perm("run:write")])
        run_id = started.data["run_id"]
        result = cli.run(["run", "get", run_id, *ACTOR, *perm("run:read")])
        assert result.data["run_id"] == run_id

    def test_list_returns_started_runs(self, cli: AgentRuntimeCliRunner) -> None:
        goal_id = self._make_goal(cli)
        cli.run(["run", "start", goal_id, *ACTOR, *perm("run:write")])
        result = cli.run(["run", "list", *ACTOR, *perm("run:read")])
        assert result.data["total"] >= 1

    def test_pause_then_resume(self, cli: AgentRuntimeCliRunner) -> None:
        goal_id = self._make_goal(cli)
        started = cli.run(["run", "start", goal_id, *ACTOR, *perm("run:write")])
        run_id = started.data["run_id"]
        paused = cli.run(["run", "pause", run_id, *ACTOR, *perm("run:write")])
        assert paused.data["status"] == "paused"
        resumed = cli.run(["run", "resume", run_id, *ACTOR, *perm("run:write")])
        assert resumed.data["status"] == "running"

    def test_cancel_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        goal_id = self._make_goal(cli)
        started = cli.run(["run", "start", goal_id, *ACTOR, *perm("run:write")])
        run_id = started.data["run_id"]
        result = cli.run(["run", "cancel", run_id, *ACTOR, *perm("run:write")])
        assert result.data["status"] == "cancelled"

    def test_cancel_terminal_run_is_state_error(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        goal_id = self._make_goal(cli)
        started = cli.run(["run", "start", goal_id, *ACTOR, *perm("run:write")])
        run_id = started.data["run_id"]
        cli.run(["run", "cancel", run_id, *ACTOR, *perm("run:write")])
        result = cli.run(["run", "cancel", run_id, *ACTOR, *perm("run:write")])
        assert result.exit_code == EXIT_INVALID_STATE

    def test_pause_missing_run_is_not_found(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["run", "pause", "no-such-run", *ACTOR, *perm("run:write")])
        assert result.exit_code == EXIT_NOT_FOUND

    def test_run_without_permission_is_denied(self, cli: AgentRuntimeCliRunner) -> None:
        goal_id = self._make_goal(cli)
        result = cli.run(["run", "start", goal_id, *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_list_read_permission_required(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["run", "list", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED


# ═════════════════════════════════════════════════════════════════════════
# Approvals  (target: 12)
# ═════════════════════════════════════════════════════════════════════════


class TestApprovalCommands:
    def test_get_not_found(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["approval", "get", "no-such-approval", *ACTOR, *perm("approval:read")]
        )
        assert result.exit_code == EXIT_NOT_FOUND

    def test_list_shows_pending(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        api_service.approval_adapter.request_approval(assigned_to="a1")
        result = cli.run(["approval", "list", *ACTOR, *perm("approval:read")])
        assert result.data["total"] >= 1

    def test_approve_requires_actor(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        response = api_service.approval_adapter.request_approval(assigned_to="a1")
        result = cli.run(["approval", "approve", response.approval_id])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_approve_succeeds(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        response = api_service.approval_adapter.request_approval(assigned_to="a1")
        result = cli.run(
            [
                "approval",
                "approve",
                response.approval_id,
                "--comment",
                "lgtm",
                *ACTOR,
                *perm("approval:write"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["status"] == "approved"
        assert result.data["comment"] == "lgtm"

    def test_reject_succeeds(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        response = api_service.approval_adapter.request_approval(assigned_to="a1")
        result = cli.run(
            [
                "approval",
                "reject",
                response.approval_id,
                "--reason",
                "no",
                *ACTOR,
                *perm("approval:write"),
            ]
        )
        assert result.data["status"] == "rejected"
        assert result.data["comment"] == "no"

    def test_no_double_decision(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        response = api_service.approval_adapter.request_approval(assigned_to="a1")
        cli.run(
            [
                "approval",
                "approve",
                response.approval_id,
                *ACTOR,
                *perm("approval:write"),
            ]
        )
        result = cli.run(
            [
                "approval",
                "approve",
                response.approval_id,
                *ACTOR,
                *perm("approval:write"),
            ]
        )
        assert result.exit_code == EXIT_CONFLICT

    def test_wrong_actor_is_permission_denied(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        response = api_service.approval_adapter.request_approval(
            assigned_to="someone-else"
        )
        result = cli.run(
            [
                "approval",
                "approve",
                response.approval_id,
                *ACTOR,
                *perm("approval:write"),
            ]
        )
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_expired_approval_is_invalid_state(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        response = api_service.approval_adapter.request_approval(
            assigned_to="a1", expires_at="2000-01-01T00:00:00+00:00"
        )
        result = cli.run(
            [
                "approval",
                "approve",
                response.approval_id,
                *ACTOR,
                *perm("approval:write"),
            ]
        )
        assert result.exit_code == EXIT_INVALID_STATE

    def test_expiration_visible_in_output(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        response = api_service.approval_adapter.request_approval(
            assigned_to="a1", expires_at="2099-01-01T00:00:00+00:00"
        )
        result = cli.run(
            ["approval", "get", response.approval_id, *ACTOR, *perm("approval:read")]
        )
        assert result.data["expires_at"] == "2099-01-01T00:00:00+00:00"

    def test_list_requires_permission(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["approval", "list", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_reject_missing_is_not_found(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["approval", "reject", "no-such", *ACTOR, *perm("approval:write")]
        )
        assert result.exit_code == EXIT_NOT_FOUND


# ═════════════════════════════════════════════════════════════════════════
# Budgets  (target: 14)
# ═════════════════════════════════════════════════════════════════════════


class TestBudgetCommands:
    def test_get_auto_creates_budget(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["budget", "get", "b1", *ACTOR, *perm("budget:read")])
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["limit"] == "100.0"

    def test_reserve_requires_actor(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["budget", "reserve", "b1", "10"])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_reserve_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            [
                "budget",
                "reserve",
                "b1",
                "10",
                "--unit",
                "iteration",
                *ACTOR,
                *perm("budget:write"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["reservation"]["amount"] == "10.0"

    def test_reserve_with_tokens_unit_hits_known_api_validation_gap(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        """Documents a real Phase 9.21 ValidationMiddleware quirk: it scans
        str(payload) for the substring "token" and false-positives on the
        word "tokens" itself. The CLI must not paper over this - it passes
        the user's explicit unit through honestly and reports the real
        (sanitized) VALIDATION_ERROR the API returns."""
        result = cli.run(
            [
                "budget",
                "reserve",
                "b1",
                "10",
                "--unit",
                "tokens",
                *ACTOR,
                *perm("budget:write"),
            ]
        )
        assert result.exit_code == EXIT_USAGE_ERROR
        assert result.error["code"] == "VALIDATION_ERROR"

    def test_reserve_exact_decimal_amount(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["budget", "reserve", "b1", "0.1", *ACTOR, *perm("budget:write")]
        )
        assert result.data["reservation"]["amount"] == "0.1"

    def test_reserve_rejects_non_decimal_amount(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            ["budget", "reserve", "b1", "abc", *ACTOR, *perm("budget:write")]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_reserve_rejects_zero_amount(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["budget", "reserve", "b1", "0", *ACTOR, *perm("budget:write")]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_reserve_exceeding_limit_is_budget_exceeded(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            ["budget", "reserve", "b1", "1000", *ACTOR, *perm("budget:write")]
        )
        assert result.exit_code == EXIT_BUDGET_EXCEEDED

    def test_reservation_id_is_traceable(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            [
                "budget",
                "reserve",
                "b1",
                "10",
                "--reservation-id",
                "res-42",
                *ACTOR,
                *perm("budget:write"),
            ]
        )
        assert result.data["reservation"]["reservation_id"] == "res-42"

    def test_release_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        cli.run(
            [
                "budget",
                "reserve",
                "b1",
                "10",
                "--reservation-id",
                "res-1",
                *ACTOR,
                *perm("budget:write"),
            ]
        )
        result = cli.run(
            ["budget", "release", "b1", "res-1", "10", *ACTOR, *perm("budget:write")]
        )
        assert result.exit_code == EXIT_SUCCESS

    def test_release_unknown_reservation_is_not_found(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "budget",
                "release",
                "b1",
                "no-such-reservation",
                "10",
                *ACTOR,
                *perm("budget:write"),
            ]
        )
        assert result.exit_code == EXIT_NOT_FOUND

    def test_release_more_than_reserved_is_validation_error(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        cli.run(
            [
                "budget",
                "reserve",
                "b1",
                "10",
                "--reservation-id",
                "res-2",
                *ACTOR,
                *perm("budget:write"),
            ]
        )
        result = cli.run(
            ["budget", "release", "b1", "res-2", "1000", *ACTOR, *perm("budget:write")]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_release_rejects_negative_amount(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["budget", "release", "b1", "res-1", "-5", *ACTOR, *perm("budget:write")]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_reserve_no_permission_denied(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["budget", "reserve", "b1", "10", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_get_no_permission_denied(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["budget", "get", "b1", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED


# ═════════════════════════════════════════════════════════════════════════
# Traces  (target: 18)
# ═════════════════════════════════════════════════════════════════════════


class TestTraceCommands:
    def _seed_trace(
        self, api_service: AgentRuntimeApiService, owner: str = "a1"
    ) -> str:
        response = api_service.trace_adapter.create_trace(owner=owner)
        return response.trace_id

    def test_get_missing_is_not_found(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["trace", "get", "no-such-trace", *ACTOR, *perm("trace:read")])
        assert result.exit_code == EXIT_NOT_FOUND

    def test_get_succeeds(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        trace_id = self._seed_trace(api_service)
        result = cli.run(["trace", "get", trace_id, *ACTOR, *perm("trace:read")])
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["trace_id"] == trace_id

    def test_get_wrong_owner_is_permission_denied(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        trace_id = self._seed_trace(api_service, owner="someone-else")
        result = cli.run(["trace", "get", trace_id, *ACTOR, *perm("trace:read")])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_list_requires_permission(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["trace", "list", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_verify_empty_trace(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        trace_id = self._seed_trace(api_service)
        result = cli.run(["trace", "verify", trace_id, *ACTOR, *perm("trace:read")])
        assert result.data["integrity_status"] == "empty"

    def test_verify_valid_chain(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        trace_id = self._seed_trace(api_service)
        api_service.trace_adapter.append_record(trace_id, {"step": 1})
        result = cli.run(["trace", "verify", trace_id, *ACTOR, *perm("trace:read")])
        assert result.data["integrity_status"] == "verified"

    def test_verify_does_not_invent_valid_status_for_tampered_chain(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        trace_id = self._seed_trace(api_service)
        api_service.trace_adapter.append_record(trace_id, {"step": 1})
        api_service.trace_adapter._traces[trace_id]["records"][0]["hash"] = (
            "tampered-hash"
        )
        result = cli.run(["trace", "verify", trace_id, *ACTOR, *perm("trace:read")])
        assert result.data["integrity_status"] == "tampered"

    def test_export_without_output_file_writes_default(
        self,
        api_service: AgentRuntimeApiService,
        cli: AgentRuntimeCliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        trace_id = self._seed_trace(api_service)
        result = cli.run(
            ["trace", "export", trace_id, *ACTOR, *perm("trace:read", "trace:export")]
        )
        assert result.exit_code == EXIT_SUCCESS
        assert (tmp_path / f"{trace_id}.json").exists()

    def test_export_with_output_file(
        self,
        api_service: AgentRuntimeApiService,
        cli: AgentRuntimeCliRunner,
        tmp_path: Path,
    ) -> None:
        trace_id = self._seed_trace(api_service)
        out = tmp_path / "custom.json"
        result = cli.run(
            [
                "trace",
                "export",
                trace_id,
                "--output-file",
                str(out),
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS
        assert out.exists()

    def test_export_refuses_overwrite_without_force(
        self,
        api_service: AgentRuntimeApiService,
        cli: AgentRuntimeCliRunner,
        tmp_path: Path,
    ) -> None:
        trace_id = self._seed_trace(api_service)
        out = tmp_path / "custom.json"
        cli.run(
            [
                "trace",
                "export",
                trace_id,
                "--output-file",
                str(out),
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        result = cli.run(
            [
                "trace",
                "export",
                trace_id,
                "--output-file",
                str(out),
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_export_overwrites_with_force(
        self,
        api_service: AgentRuntimeApiService,
        cli: AgentRuntimeCliRunner,
        tmp_path: Path,
    ) -> None:
        trace_id = self._seed_trace(api_service)
        out = tmp_path / "custom.json"
        cli.run(
            [
                "trace",
                "export",
                trace_id,
                "--output-file",
                str(out),
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        result = cli.run(
            [
                "trace",
                "export",
                trace_id,
                "--output-file",
                str(out),
                "--force",
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS

    def test_export_atomic_write_no_temp_file_left_behind(
        self,
        api_service: AgentRuntimeApiService,
        cli: AgentRuntimeCliRunner,
        tmp_path: Path,
    ) -> None:
        trace_id = self._seed_trace(api_service)
        out = tmp_path / "atomic.json"
        cli.run(
            [
                "trace",
                "export",
                trace_id,
                "--output-file",
                str(out),
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        leftovers = [
            p for p in tmp_path.iterdir() if p.name.startswith(".cmm-agent-tmp-")
        ]
        assert leftovers == []

    def test_export_path_traversal_in_trace_id_rejected(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "trace",
                "export",
                "../../etc/passwd",
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_export_never_leaks_chain_of_thought(
        self,
        api_service: AgentRuntimeApiService,
        cli: AgentRuntimeCliRunner,
        tmp_path: Path,
    ) -> None:
        trace_id = self._seed_trace(api_service)
        api_service.trace_adapter.append_record(
            trace_id, {"chain_of_thought": "secret reasoning"}
        )
        out = tmp_path / "export.json"
        cli.run(
            [
                "trace",
                "export",
                trace_id,
                "--output-file",
                str(out),
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        content = out.read_text()
        assert "secret reasoning" not in content

    def test_export_requires_export_permission(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        trace_id = self._seed_trace(api_service)
        result = cli.run(["trace", "export", trace_id, *ACTOR, *perm("trace:read")])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_export_format_choice_validated(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            [
                "trace",
                "export",
                "t1",
                "--format",
                "xml",
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_list_shows_own_traces_only(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        self._seed_trace(api_service, owner="a1")
        self._seed_trace(api_service, owner="other")
        result = cli.run(["trace", "list", *ACTOR, *perm("trace:read")])
        assert result.data["total"] == 1


# ═════════════════════════════════════════════════════════════════════════
# Events  (target: 20)
# ═════════════════════════════════════════════════════════════════════════


class TestEventCommands:
    def test_publish_requires_permission(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["event", "publish", "goal.created", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_publish_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["event", "publish", "goal.created", *ACTOR, *perm("event:write")]
        )
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["event_type"] == "goal.created"

    def test_publish_unknown_event_type_is_validation_error(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            ["event", "publish", "not.a.real.event", *ACTOR, *perm("event:write")]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_publish_never_reports_fake_delivered(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            ["event", "publish", "goal.created", *ACTOR, *perm("event:write")]
        )
        assert result.data["delivery"]["status"] != "delivered"
        assert result.data["delivery"]["status"] == "recorded"

    def test_publish_with_inline_payload(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            [
                "event",
                "publish",
                "goal.created",
                "--payload",
                '{"note": "hello"}',
                *ACTOR,
                *perm("event:write"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS

    def test_publish_with_payload_file(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = tmp_path / "payload.json"
        path.write_text('{"note": "hello"}')
        result = cli.run(
            [
                "event",
                "publish",
                "goal.created",
                "--payload-file",
                str(path),
                *ACTOR,
                *perm("event:write"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS

    def test_publish_rejects_both_payload_and_payload_file(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "event",
                "publish",
                "goal.created",
                "--payload",
                "{}",
                "--payload-file",
                "x.json",
                *ACTOR,
                *perm("event:write"),
            ]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_publish_rejects_sensitive_inline_payload(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "event",
                "publish",
                "goal.created",
                "--payload",
                '{"password": "x"}',
                *ACTOR,
                *perm("event:write"),
            ]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_publish_rejects_sensitive_metadata(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "event",
                "publish",
                "goal.created",
                "--metadata",
                "secret=x",
                *ACTOR,
                *perm("event:write"),
            ]
        )
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_publish_with_correlation_and_run_id(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "event",
                "publish",
                "goal.created",
                "--run-id",
                "run-1",
                "--correlation-id",
                "c1",
                *ACTOR,
                *perm("event:write"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS

    def test_list_requires_permission(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["event", "list", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_list_shows_published_events(self, cli: AgentRuntimeCliRunner) -> None:
        cli.run(["event", "publish", "goal.created", *ACTOR, *perm("event:write")])
        result = cli.run(["event", "list", *ACTOR, *perm("event:read")])
        assert result.data["total"] >= 1

    def test_replay_requires_selector_or_limit(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["event", "replay", *ACTOR, *perm("event:write")])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_replay_with_limit_is_accepted(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["event", "replay", "--limit", "5", *ACTOR, *perm("event:write")]
        )
        assert result.exit_code == EXIT_SUCCESS

    def test_replay_with_event_type_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        cli.run(["event", "publish", "goal.created", *ACTOR, *perm("event:write")])
        result = cli.run(
            [
                "event",
                "replay",
                "--event-type",
                "goal.created",
                *ACTOR,
                *perm("event:write"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["replayed"] >= 1

    def test_replay_dry_run_never_calls_mutating_replay(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        cli.run(["event", "publish", "goal.created", *ACTOR, *perm("event:write")])
        before = cli.run(["event", "list", *ACTOR, *perm("event:read")]).data["total"]
        cli.run(
            [
                "event",
                "replay",
                "--event-type",
                "goal.created",
                "--dry-run",
                *ACTOR,
                *perm("event:read"),
            ]
        )
        after = cli.run(["event", "list", *ACTOR, *perm("event:read")]).data["total"]
        assert before == after

    def test_replay_dry_run_reports_would_replay_count(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        cli.run(["event", "publish", "goal.created", *ACTOR, *perm("event:write")])
        result = cli.run(
            [
                "event",
                "replay",
                "--event-type",
                "goal.created",
                "--dry-run",
                *ACTOR,
                *perm("event:read"),
            ]
        )
        assert result.data["dry_run"] is True
        assert result.data["would_replay"] >= 1

    def test_replay_does_not_fake_replay_for_unknown_type(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "event",
                "replay",
                "--event-type",
                "goal.updated",
                *ACTOR,
                *perm("event:write"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["replayed"] == 0

    def test_publish_from_to_time_filters_accepted_on_list(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "event",
                "list",
                "--from",
                "2020-01-01T00:00:00Z",
                "--to",
                "2030-01-01T00:00:00Z",
                *ACTOR,
                *perm("event:read"),
            ]
        )
        assert result.exit_code == EXIT_SUCCESS

    def test_publish_rejects_invalid_timestamp_filter(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            ["event", "list", "--from", "not-a-date", *ACTOR, *perm("event:read")]
        )
        assert result.exit_code == EXIT_USAGE_ERROR


# ═════════════════════════════════════════════════════════════════════════
# Dead Letters  (target: 8)
# ═════════════════════════════════════════════════════════════════════════


class TestDeadLetterCommands:
    def _seed_dead_letter(self, api_service: AgentRuntimeApiService) -> str:
        api_service.event_adapter.publish_internal(
            "goal.created", {"resource_id": "g1"}
        )
        event_id = api_service.event_adapter._events[0]["event_id"]
        entry = api_service.event_adapter.route_to_dead_letter(
            event_id, "handler failed"
        )
        return entry.dead_letter_id

    def test_list_requires_permission(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["dead-letter", "list", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_list_shows_dead_letters(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        self._seed_dead_letter(api_service)
        result = cli.run(["dead-letter", "list", *ACTOR, *perm("event:read")])
        assert result.data["total"] >= 1

    def test_replay_missing_is_not_found(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["dead-letter", "replay", "no-such-dl", *ACTOR, *perm("event:write")]
        )
        assert result.exit_code == EXIT_NOT_FOUND

    def test_replay_succeeds(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        dl_id = self._seed_dead_letter(api_service)
        result = cli.run(["dead-letter", "replay", dl_id, *ACTOR, *perm("event:write")])
        assert result.exit_code == EXIT_SUCCESS
        assert result.data["replayed"] is True

    def test_replay_requires_actor(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        dl_id = self._seed_dead_letter(api_service)
        result = cli.run(["dead-letter", "replay", dl_id])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_replay_dry_run_does_not_mutate(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        dl_id = self._seed_dead_letter(api_service)
        cli.run(
            ["dead-letter", "replay", dl_id, "--dry-run", *ACTOR, *perm("event:read")]
        )
        listing = cli.run(["dead-letter", "list", *ACTOR, *perm("event:read")])
        assert listing.data["dead_letters"][0]["replayed"] is False

    def test_replay_dry_run_reports_found(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        dl_id = self._seed_dead_letter(api_service)
        result = cli.run(
            ["dead-letter", "replay", dl_id, "--dry-run", *ACTOR, *perm("event:read")]
        )
        assert result.data["would_replay"] is True

    def test_replay_dry_run_missing_reports_not_found(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            [
                "dead-letter",
                "replay",
                "no-such-dl",
                "--dry-run",
                *ACTOR,
                *perm("event:read"),
            ]
        )
        assert result.data["would_replay"] is False


# ═════════════════════════════════════════════════════════════════════════
# Health / Stats  (target: 10)
# ═════════════════════════════════════════════════════════════════════════


class TestHealthStats:
    def test_health_requires_permission(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["health", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_health_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["health", *ACTOR, *perm("system:read")])
        assert result.exit_code == EXIT_SUCCESS

    def test_health_shows_degraded_honestly(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["health", *ACTOR, *perm("system:read")])
        assert result.data["status"] == "degraded"

    def test_health_lists_unavailable_components(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["health", *ACTOR, *perm("system:read")])
        assert result.data["managers"]["goal"] == "unavailable"

    def test_health_never_invents_a_healthy_status(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["health", *ACTOR, *perm("system:read")])
        assert result.data["status"] in {"healthy", "degraded"}

    def test_health_quiet_reports_status(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["health", "--quiet", *ACTOR, *perm("system:read")])
        assert result.stdout.strip() == "degraded"

    def test_stats_requires_permission(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["stats", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_stats_succeeds(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["stats", *ACTOR, *perm("system:read")])
        assert result.exit_code == EXIT_SUCCESS

    def test_stats_reflects_operations_executed(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        cli.run(["health", *ACTOR, *perm("system:read")])
        result = cli.run(["stats", *ACTOR, *perm("system:read")])
        assert result.data["operations_executed"] >= 1

    def test_stats_does_not_invent_managers(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["health", *ACTOR, *perm("system:read")])
        assert result.data["managers"]["goal"] == "unavailable"
        assert result.data["repositories"]["goal"] == "unavailable"


# ═════════════════════════════════════════════════════════════════════════
# Batch  (target: 20)
# ═════════════════════════════════════════════════════════════════════════


class TestBatchCommand:
    def _write_batch(self, tmp_path: Path, lines: list[str]) -> Path:
        path = tmp_path / "batch.jsonl"
        path.write_text("\n".join(lines) + "\n")
        return path

    def test_single_line_success(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                json.dumps(
                    {
                        "operation": "runtime.health",
                        "actor_id": "a1",
                        "permissions": ["system:read"],
                    }
                )
            ],
        )
        result = cli.run(["batch", "--file", str(path)])
        assert result.exit_code == EXIT_SUCCESS
        record = json.loads(result.stdout.strip())
        assert record["status"] == "success"

    def test_mixed_success_and_error(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                json.dumps(
                    {
                        "operation": "runtime.health",
                        "actor_id": "a1",
                        "permissions": ["system:read"],
                    }
                ),
                json.dumps(
                    {
                        "operation": "goal.get",
                        "payload": {"goal_id": "no-such"},
                        "actor_id": "a1",
                        "permissions": ["goal:read"],
                    }
                ),
            ],
        )
        result = cli.run(["batch", "--file", str(path)])
        assert result.exit_code == 1
        lines = [json.loads(x) for x in result.stdout.strip().splitlines()]
        assert lines[0]["status"] == "success"
        assert lines[1]["status"] == "error"

    def test_preserves_order(self, cli: AgentRuntimeCliRunner, tmp_path: Path) -> None:
        path = self._write_batch(
            tmp_path,
            [
                json.dumps(
                    {
                        "operation": "goal.create",
                        "payload": {"title": "first", "objective": "o"},
                        "actor_id": "a1",
                        "permissions": ["goal:write"],
                    }
                ),
                json.dumps(
                    {
                        "operation": "goal.create",
                        "payload": {"title": "second", "objective": "o"},
                        "actor_id": "a1",
                        "permissions": ["goal:write"],
                    }
                ),
            ],
        )
        result = cli.run(["batch", "--file", str(path)])
        lines = [json.loads(x) for x in result.stdout.strip().splitlines()]
        assert lines[0]["data"]["title"] == "first"
        assert lines[1]["data"]["title"] == "second"

    def test_invalid_json_line_identified_by_number(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(tmp_path, ["not valid json"])
        result = cli.run(["batch", "--file", str(path)])
        record = json.loads(result.stdout.strip())
        assert record["line"] == 1
        assert record["status"] == "error"

    def test_one_failure_does_not_stop_the_rest(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                "not valid json",
                json.dumps(
                    {
                        "operation": "runtime.health",
                        "actor_id": "a1",
                        "permissions": ["system:read"],
                    }
                ),
            ],
        )
        result = cli.run(["batch", "--file", str(path)])
        lines = [json.loads(x) for x in result.stdout.strip().splitlines()]
        assert len(lines) == 2
        assert lines[1]["status"] == "success"

    def test_fail_fast_stops_after_first_error(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                "not valid json",
                json.dumps(
                    {
                        "operation": "runtime.health",
                        "actor_id": "a1",
                        "permissions": ["system:read"],
                    }
                ),
            ],
        )
        result = cli.run(["batch", "--file", str(path), "--fail-fast"])
        lines = [json.loads(x) for x in result.stdout.strip().splitlines()]
        assert len(lines) == 1

    def test_summary_appended_when_requested(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                json.dumps(
                    {
                        "operation": "runtime.health",
                        "actor_id": "a1",
                        "permissions": ["system:read"],
                    }
                )
            ],
        )
        result = cli.run(["batch", "--file", str(path), "--summary"])
        lines = [json.loads(x) for x in result.stdout.strip().splitlines()]
        assert lines[-1]["summary"]["total"] == 1
        assert lines[-1]["summary"]["succeeded"] == 1

    def test_no_summary_by_default(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                json.dumps(
                    {
                        "operation": "runtime.health",
                        "actor_id": "a1",
                        "permissions": ["system:read"],
                    }
                )
            ],
        )
        result = cli.run(["batch", "--file", str(path)])
        lines = [json.loads(x) for x in result.stdout.strip().splitlines()]
        assert all("summary" not in x for x in lines)

    def test_max_lines_enforced(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [json.dumps({"operation": "runtime.health"}) for _ in range(5)],
        )
        result = cli.run(["batch", "--file", str(path), "--max-lines", "2"])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_max_bytes_enforced(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [json.dumps({"operation": "runtime.health", "payload": {"x": "y" * 1000}})],
        )
        result = cli.run(["batch", "--file", str(path), "--max-bytes", "10"])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_missing_batch_file_is_usage_error(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        result = cli.run(["batch", "--file", str(tmp_path / "missing.jsonl")])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_request_id_preserved_per_line(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                json.dumps(
                    {
                        "operation": "runtime.health",
                        "request_id": "line-req-1",
                        "actor_id": "a1",
                        "permissions": ["system:read"],
                    }
                )
            ],
        )
        result = cli.run(["batch", "--file", str(path)])
        record = json.loads(result.stdout.strip())
        assert record["request_id"] == "line-req-1"

    def test_idempotency_key_per_record(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                json.dumps(
                    {
                        "operation": "goal.create",
                        "payload": {"title": "t", "objective": "o"},
                        "idempotency_key": "idem-1",
                        "actor_id": "a1",
                        "permissions": ["goal:write"],
                    }
                ),
                json.dumps(
                    {
                        "operation": "goal.create",
                        "payload": {"title": "t", "objective": "o"},
                        "idempotency_key": "idem-1",
                        "actor_id": "a1",
                        "permissions": ["goal:write"],
                    }
                ),
            ],
        )
        result = cli.run(["batch", "--file", str(path)])
        lines = [json.loads(x) for x in result.stdout.strip().splitlines()]
        assert lines[0]["data"]["goal_id"] == lines[1]["data"]["goal_id"]

    def test_unknown_operation_reported_per_line(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path, [json.dumps({"operation": "not.a.real.operation"})]
        )
        result = cli.run(["batch", "--file", str(path)])
        record = json.loads(result.stdout.strip())
        assert record["status"] == "error"
        assert record["error"]["code"] == "UNSUPPORTED_OPERATION"

    def test_missing_operation_field_reported_per_line(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(tmp_path, [json.dumps({"payload": {}})])
        result = cli.run(["batch", "--file", str(path)])
        record = json.loads(result.stdout.strip())
        assert record["status"] == "error"

    def test_blank_lines_are_skipped(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = tmp_path / "batch.jsonl"
        path.write_text(
            json.dumps(
                {
                    "operation": "runtime.health",
                    "actor_id": "a1",
                    "permissions": ["system:read"],
                }
            )
            + "\n\n\n"
        )
        result = cli.run(["batch", "--file", str(path)])
        lines = [x for x in result.stdout.strip().splitlines() if x]
        assert len(lines) == 1

    def test_line_level_actor_used_when_present(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                json.dumps(
                    {
                        "operation": "goal.create",
                        "payload": {"title": "t", "objective": "o"},
                        "actor_id": "line-actor",
                        "permissions": ["goal:write"],
                    }
                )
            ],
        )
        result = cli.run(["batch", "--file", str(path)])
        record = json.loads(result.stdout.strip())
        assert record["data"]["creator"] == "line-actor"

    def test_global_actor_used_as_fallback(
        self, cli: AgentRuntimeCliRunner, tmp_path: Path
    ) -> None:
        path = self._write_batch(
            tmp_path,
            [
                json.dumps(
                    {
                        "operation": "goal.create",
                        "payload": {"title": "t", "objective": "o"},
                        "permissions": ["goal:write"],
                    }
                )
            ],
        )
        result = cli.run(["batch", "--file", str(path), "--actor-id", "global-actor"])
        record = json.loads(result.stdout.strip())
        assert record["data"]["creator"] == "global-actor"

    def test_reads_from_stdin_when_no_file(
        self, cli: AgentRuntimeCliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        line = json.dumps(
            {
                "operation": "runtime.health",
                "actor_id": "a1",
                "permissions": ["system:read"],
            }
        )
        monkeypatch.setattr("sys.stdin", _FakeStdin((line + "\n").encode("utf-8")))
        result = cli.run(["batch"])
        record = json.loads(result.stdout.strip())
        assert record["status"] == "success"


# ═════════════════════════════════════════════════════════════════════════
# Security  (target: 25)
# ═════════════════════════════════════════════════════════════════════════


def _ast_module(module) -> object:
    import ast

    return ast.parse(Path(module.__file__).read_text())


class TestSecurity:
    def test_no_eval_or_exec_calls_in_source(self) -> None:
        import ast

        import cmm.agent_runtime.agent_runtime_cli_commands as mod
        import cmm.agent_runtime.agent_runtime_cli_parsers as parsers_mod

        for module in (mod, parsers_mod):
            tree = _ast_module(module)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert node.func.id not in {"eval", "exec"}

    def test_no_pickle_subprocess_or_os_system_imports(self) -> None:
        import ast

        import cmm.agent_runtime.agent_runtime_cli_app as app_mod
        import cmm.agent_runtime.agent_runtime_cli_commands as cmd_mod
        import cmm.agent_runtime.agent_runtime_cli_parsers as parsers_mod

        banned = {"pickle", "subprocess"}
        for module in (app_mod, cmd_mod, parsers_mod):
            tree = _ast_module(module)
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            assert imported.isdisjoint(banned)

    def test_no_literal_eval_call_used(self) -> None:
        import ast

        import cmm.agent_runtime.agent_runtime_cli_parsers as parsers_mod

        tree = _ast_module(parsers_mod)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr != "literal_eval"

    def test_payload_rejects_chain_of_thought(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_inline('{"chain_of_thought": "secret"}')

    def test_payload_rejects_internal_reasoning(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_inline('{"internal_reasoning": "secret"}')

    def test_payload_rejects_private_prompt(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_inline('{"private_prompt": "secret"}')

    def test_payload_rejects_bearer_token_content(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_inline('{"header": "bearer abc123"}')

    def test_payload_rejects_private_key(self) -> None:
        with pytest.raises(AgentRuntimeCliSecurityError):
            parse_json_inline('{"key": "-----BEGIN private_key-----"}')

    def test_response_redacts_secret_field(self) -> None:
        assert to_serializable({"secret": "x"})["secret"] == "**REDACTED**"

    def test_response_redacts_credential_field(self) -> None:
        assert to_serializable({"credential": "x"})["credential"] == "**REDACTED**"

    def test_internal_error_never_leaks_original_message(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        from cmm.agent_runtime.agent_runtime_api_enums import AgentRuntimeApiOperation

        def _boom(request, context):
            raise RuntimeError("leaked secret token=abc123")

        api_service.router.unregister(AgentRuntimeApiOperation.GOAL_GET)
        api_service.router.register(AgentRuntimeApiOperation.GOAL_GET, _boom)
        result = cli.run(["goal", "get", "g1", *ACTOR, *perm("goal:read")])
        assert "abc123" not in result.stderr
        assert "token=" not in result.stderr
        assert result.exit_code == EXIT_INTERNAL_ERROR

    def test_keyboard_interrupt_returns_130(
        self,
        api_service: AgentRuntimeApiService,
        monkeypatch: pytest.MonkeyPatch,
        cli: AgentRuntimeCliRunner,
    ) -> None:
        def _interrupt(*args, **kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr(api_service, "execute", _interrupt)
        result = cli.run(["health", *ACTOR, *perm("system:read")])
        assert result.exit_code == EXIT_INTERRUPTED
        assert result.stderr == ""
        assert "Traceback" not in result.stdout

    def test_quiet_mode_does_not_hide_errors(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["goal", "get", "no-such", "--quiet", *ACTOR, *perm("goal:read")]
        )
        assert result.exit_code == EXIT_NOT_FOUND
        assert result.stderr != ""

    def test_json_output_always_valid_on_success(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["health", "--output", "json", *ACTOR, *perm("system:read")])
        json.loads(result.stdout)

    def test_json_output_always_valid_on_error(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            ["goal", "get", "no-such", "--output", "json", *ACTOR, *perm("goal:read")]
        )
        json.loads(result.stderr)

    def test_json_output_valid_on_usage_error(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(
            ["goal", "create", "--title", "t", "--objective", "o", "--output", "json"]
        )
        json.loads(result.stderr)

    def test_no_actor_implicit_for_mutation(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["goal", "create", "--title", "t", "--objective", "o"])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_no_permission_implicit_by_actor(self, cli: AgentRuntimeCliRunner) -> None:
        result = cli.run(["goal", "create", "--title", "t", "--objective", "o", *ACTOR])
        assert result.exit_code == EXIT_PERMISSION_DENIED

    def test_path_traversal_in_positional_id_rejected(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["goal", "get", "../../secret", *ACTOR, *perm("goal:read")])
        assert result.exit_code == EXIT_USAGE_ERROR

    def test_dead_letter_replay_missing_is_not_fake_success(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(
            ["dead-letter", "replay", "no-such-dl", *ACTOR, *perm("event:write")]
        )
        assert result.exit_code == EXIT_NOT_FOUND
        assert result.status != "success"

    def test_trace_verify_never_returns_fake_valid_string(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        trace_id = api_service.trace_adapter.create_trace(owner="a1").trace_id
        result = cli.run(["trace", "verify", trace_id, *ACTOR, *perm("trace:read")])
        assert result.data["integrity_status"] in {"empty", "verified", "tampered"}

    def test_no_stack_trace_on_result_stdout_or_stderr(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        result = cli.run(["goal", "get", "no-such", *ACTOR, *perm("goal:read")])
        assert "Traceback" not in result.stdout
        assert "Traceback" not in result.stderr

    def test_no_subprocess_import_in_cli_modules(self) -> None:
        import cmm.agent_runtime.agent_runtime_cli_app as app_mod
        import cmm.agent_runtime.agent_runtime_cli_commands as cmd_mod

        for module in (app_mod, cmd_mod):
            src = Path(module.__file__).read_text()
            assert "import subprocess" not in src

    def test_help_never_touches_real_stdin(self) -> None:
        runner = AgentRuntimeCliRunner()
        result = runner.run(["--help"])
        assert result.exit_code == 0

    def test_export_file_outside_destination_still_requires_force(
        self,
        api_service: AgentRuntimeApiService,
        cli: AgentRuntimeCliRunner,
        tmp_path: Path,
    ) -> None:
        trace_id = api_service.trace_adapter.create_trace(owner="a1").trace_id
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        out = nested / "trace.json"
        cli.run(
            [
                "trace",
                "export",
                trace_id,
                "--output-file",
                str(out),
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        result = cli.run(
            [
                "trace",
                "export",
                trace_id,
                "--output-file",
                str(out),
                *ACTOR,
                *perm("trace:read", "trace:export"),
            ]
        )
        assert result.exit_code == EXIT_USAGE_ERROR


# ═════════════════════════════════════════════════════════════════════════
# Integration / Regression  (target: 15)
# ═════════════════════════════════════════════════════════════════════════


class TestIntegrationRegression:
    def test_module_level_run_function(self) -> None:
        result = run(["--version"])
        assert result.exit_code == 0

    def test_module_level_run_with_injected_service(
        self, api_service: AgentRuntimeApiService
    ) -> None:
        result = run(["health", *ACTOR, *perm("system:read")], api_service=api_service)
        assert result.exit_code == 0

    def test_main_returns_int_exit_code(self, capsys: pytest.CaptureFixture) -> None:
        code = main(["--version"])
        assert code == 0
        captured = capsys.readouterr()
        assert "9.22" in captured.out

    def test_main_writes_errors_to_stderr(self, capsys: pytest.CaptureFixture) -> None:
        code = main(["goal", "create", "--title", "t", "--objective", "o"])
        assert code == EXIT_USAGE_ERROR
        captured = capsys.readouterr()
        assert captured.err != ""

    def test_cmm_main_still_routes_validation(self) -> None:
        from cmm.__main__ import build_parser

        parser = build_parser()
        args = parser.parse_args(["validation", "run"])
        assert args.command == "validation"

    def test_cmm_main_still_routes_develop(self) -> None:
        from cmm.__main__ import build_parser

        parser = build_parser()
        args = parser.parse_args(["develop", "some goal"])
        assert args.command == "develop"

    def test_cmm_main_still_routes_run(self) -> None:
        from cmm.__main__ import build_parser

        parser = build_parser()
        args = parser.parse_args(["run", "some goal"])
        assert args.command == "run"

    def test_cmm_agent_subcommand_registered_for_help(self) -> None:
        from cmm.__main__ import build_parser

        parser = build_parser()
        help_text = parser.format_help()
        assert "agent" in help_text

    def test_cmm_main_dispatches_agent_before_parser(self) -> None:
        from cmm.__main__ import main as cmm_main

        code = cmm_main(["agent", "--version"])
        assert code == 0

    def test_cmm_main_agent_help_does_not_error(self) -> None:
        from cmm.__main__ import main as cmm_main

        code = cmm_main(["agent", "--help"])
        assert code == 0

    def test_public_facade_exports(self) -> None:
        from cmm.agent_runtime.agent_runtime_cli import (
            AgentRuntimeCliContextBuilder as _Ctx,
        )
        from cmm.agent_runtime.agent_runtime_cli import (
            AgentRuntimeCliResult as _Result,
        )
        from cmm.agent_runtime.agent_runtime_cli import (
            AgentRuntimeCliRunner as _Runner,
        )

        assert _Ctx is not None
        assert _Result is not None
        assert _Runner is not None

    def test_package_exports_run_and_main(self) -> None:
        import cmm.agent_runtime as ar

        assert callable(ar.run)
        assert callable(ar.main)

    def test_two_independent_runners_do_not_share_state(self) -> None:
        service_a = AgentRuntimeApiService()
        service_b = AgentRuntimeApiService()
        runner_a = AgentRuntimeCliRunner(service_a)
        runner_b = AgentRuntimeCliRunner(service_b)
        runner_a.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        result_b = runner_b.run(["goal", "list", *ACTOR, *perm("goal:read")])
        assert result_b.data["total"] == 0

    def test_same_runner_reuses_state_across_calls(
        self, cli: AgentRuntimeCliRunner
    ) -> None:
        created = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        goal_id = created.data["goal_id"]
        fetched = cli.run(["goal", "get", goal_id, *ACTOR, *perm("goal:read")])
        assert fetched.data["goal_id"] == goal_id

    def test_full_lifecycle_goal_run_budget_trace_event(
        self, api_service: AgentRuntimeApiService, cli: AgentRuntimeCliRunner
    ) -> None:
        goal = cli.run(
            [
                "goal",
                "create",
                "--title",
                "t",
                "--objective",
                "o",
                *ACTOR,
                *perm("goal:write"),
            ]
        )
        goal_id = goal.data["goal_id"]
        run_result = cli.run(["run", "start", goal_id, *ACTOR, *perm("run:write")])
        assert run_result.exit_code == EXIT_SUCCESS
        budget = cli.run(
            ["budget", "reserve", "b1", "5", *ACTOR, *perm("budget:write")]
        )
        assert budget.exit_code == EXIT_SUCCESS
        event = cli.run(
            [
                "event",
                "publish",
                "agent_run.started",
                "--run-id",
                run_result.data["run_id"],
                *ACTOR,
                *perm("event:write"),
            ]
        )
        assert event.exit_code == EXIT_SUCCESS
