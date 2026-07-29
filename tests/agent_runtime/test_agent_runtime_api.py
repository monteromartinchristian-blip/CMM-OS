"""Phase 9.21 – Agent Runtime API Tests.

Covers contracts, idempotency, router, middleware, adapters and the
end-to-end service (goal/run/approval/budget/trace/event/system + wiring).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from cmm.agent_runtime.agent_runtime_api_adapters import (
    AgentRunApiAdapter,
    ApprovalApiAdapter,
    BudgetApiAdapter,
    GoalApiAdapter,
    RuntimeEventApiAdapter,
    RuntimeSystemApiAdapter,
    TraceApiAdapter,
)
from cmm.agent_runtime.agent_runtime_api_contracts import (
    AgentRuntimeApiContext,
    AgentRuntimeApiError,
    AgentRuntimeApiHealth,
    AgentRuntimeApiPage,
    AgentRuntimeApiPermissions,
    AgentRuntimeApiQuery,
    AgentRuntimeApiRequest,
    AgentRuntimeApiResponse,
    AgentRuntimeApiSortDirection,
    AgentRuntimeApiStats,
    CreateGoalRequest,
    ExportAgentTraceRequest,
    GetGoalRequest,
    ListApprovalRequestsRequest,
    ListGoalsRequest,
    PrioritizeGoalRequest,
    PublishRuntimeEventRequest,
    ReleaseBudgetRequest,
    ReplayDeadLetterRequest,
    ReplayRuntimeEventsRequest,
    ReserveBudgetRequest,
    StartAgentRunRequest,
    compute_request_fingerprint,
)
from cmm.agent_runtime.agent_runtime_api_enums import (
    AgentRuntimeApiErrorCode,
    AgentRuntimeApiOperation,
    AgentRuntimeApiStatus,
)
from cmm.agent_runtime.agent_runtime_api_errors import (
    AgentRuntimeApiException,
    AgentRuntimeApiNotFoundError,
)
from cmm.agent_runtime.agent_runtime_api_idempotency import (
    InMemoryAgentRuntimeApiIdempotencyStore,
    compute_fingerprint,
)
from cmm.agent_runtime.agent_runtime_api_middleware import (
    AuditMiddleware,
    AuthenticationContextMiddleware,
    ErrorMappingMiddleware,
    MetricsMiddleware,
    PermissionMiddleware,
    RedactionMiddleware,
    RequestIdMiddleware,
    ValidationMiddleware,
    create_default_middleware_chain,
)
from cmm.agent_runtime.agent_runtime_api_router import (
    AgentRuntimeApiMiddleware,
    AgentRuntimeApiRouter,
)
from cmm.agent_runtime.agent_runtime_api_service import AgentRuntimeApiService
from cmm.agent_runtime.runtime_event_types import EventType

# ═════════════════════════════════════════════════════════════════════════
# Block 1: contracts, idempotency, router, middleware
# ═════════════════════════════════════════════════════════════════════════


class TestContracts:
    """Validation and behavior of the immutable API contracts."""

    def test_request_generates_request_id_by_default(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        assert isinstance(req.request_id, str) and req.request_id

    def test_request_rejects_empty_request_id(self) -> None:
        with pytest.raises(ValueError):
            AgentRuntimeApiRequest(
                operation=AgentRuntimeApiOperation.GOAL_GET, request_id=""
            )

    def test_request_rejects_blank_idempotency_key(self) -> None:
        with pytest.raises(ValueError):
            AgentRuntimeApiRequest(
                operation=AgentRuntimeApiOperation.GOAL_GET, idempotency_key="   "
            )

    def test_request_accepts_valid_idempotency_key(self) -> None:
        req = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.GOAL_GET, idempotency_key="key-1"
        )
        assert req.idempotency_key == "key-1"

    def test_context_rejects_empty_actor(self) -> None:
        with pytest.raises(ValueError):
            AgentRuntimeApiContext(actor="")

    def test_context_defaults(self) -> None:
        ctx = AgentRuntimeApiContext(actor="alice")
        assert ctx.actor_kind == "user"
        assert ctx.permissions == frozenset()

    def test_error_sanitizes_sensitive_message(self) -> None:
        err = AgentRuntimeApiError(
            code=AgentRuntimeApiErrorCode.VALIDATION_ERROR, message="token=abc123"
        )
        assert err.message == "An internal error occurred"

    def test_error_keeps_safe_message(self) -> None:
        err = AgentRuntimeApiError(
            code=AgentRuntimeApiErrorCode.NOT_FOUND, message="Goal x not found"
        )
        assert err.message == "Goal x not found"

    def test_response_success_true(self) -> None:
        resp = AgentRuntimeApiResponse(status=AgentRuntimeApiStatus.SUCCESS)
        assert resp.success is True

    def test_response_success_false(self) -> None:
        resp = AgentRuntimeApiResponse(status=AgentRuntimeApiStatus.ERROR)
        assert resp.success is False

    def test_page_rejects_limit_too_low(self) -> None:
        with pytest.raises(ValueError):
            AgentRuntimeApiPage(limit=0)

    def test_page_rejects_limit_too_high(self) -> None:
        with pytest.raises(ValueError):
            AgentRuntimeApiPage(limit=501)

    def test_query_rejects_limit_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            AgentRuntimeApiQuery(limit=0)

    def test_query_default_sort_direction_asc(self) -> None:
        assert AgentRuntimeApiQuery().sort_direction == AgentRuntimeApiSortDirection.ASC

    def test_permissions_allows_true(self) -> None:
        perms = AgentRuntimeApiPermissions(required={"goal:write": True})
        assert perms.allows("goal:write") is True

    def test_permissions_allows_false_when_missing(self) -> None:
        assert AgentRuntimeApiPermissions().allows("goal:write") is False

    def test_health_rejects_sensitive_warning(self) -> None:
        with pytest.raises(ValueError):
            AgentRuntimeApiHealth(
                status="degraded",
                version="1.0",
                managers={},
                repositories={},
                event_bus="unavailable",
                trace_service="unavailable",
                timestamp="now",
                warnings=["contains password leak"],
            )

    def test_health_accepts_safe_warning(self) -> None:
        h = AgentRuntimeApiHealth(
            status="degraded",
            version="1.0",
            managers={},
            repositories={},
            event_bus="unavailable",
            trace_service="unavailable",
            timestamp="now",
            warnings=["disk space low"],
        )
        assert h.warnings == ["disk space low"]

    def test_stats_latency_average_none_when_no_samples(self) -> None:
        assert AgentRuntimeApiStats().latency_average_ms is None

    def test_stats_latency_average_computed(self) -> None:
        stats = AgentRuntimeApiStats(latency_accumulated_ms=100.0, latency_count=4)
        assert stats.latency_average_ms == 25.0

    def test_create_goal_request_rejects_empty_title(self) -> None:
        with pytest.raises(ValueError):
            CreateGoalRequest(title="  ", objective="do it")

    def test_create_goal_request_rejects_empty_objective(self) -> None:
        with pytest.raises(ValueError):
            CreateGoalRequest(title="t", objective=" ")

    def test_create_goal_request_rejects_negative_priority(self) -> None:
        with pytest.raises(ValueError):
            CreateGoalRequest(title="t", objective="o", priority=-1)

    def test_get_goal_request_rejects_empty_id(self) -> None:
        with pytest.raises(ValueError):
            GetGoalRequest(goal_id=" ")

    def test_list_goals_request_defaults_query(self) -> None:
        req = ListGoalsRequest()
        assert isinstance(req.query, AgentRuntimeApiQuery)

    def test_prioritize_goal_request_rejects_negative_priority(self) -> None:
        with pytest.raises(ValueError):
            PrioritizeGoalRequest(goal_id="g1", new_priority=-1)

    def test_start_agent_run_request_rejects_empty_goal_id(self) -> None:
        with pytest.raises(ValueError):
            StartAgentRunRequest(goal_id="")

    def test_list_approval_requests_defaults_to_pending_filter(self) -> None:
        req = ListApprovalRequestsRequest()
        assert req.query.filters == {"status": "pending"}

    def test_reserve_budget_request_rejects_nonpositive_amount(self) -> None:
        with pytest.raises(ValueError):
            ReserveBudgetRequest(budget_id="b1", amount=0)

    def test_release_budget_request_rejects_empty_reservation_id(self) -> None:
        with pytest.raises(ValueError):
            ReleaseBudgetRequest(budget_id="b1", reservation_id=" ", amount=1)

    def test_export_trace_request_rejects_invalid_format(self) -> None:
        with pytest.raises(ValueError):
            ExportAgentTraceRequest(trace_id="t1", format="XML")

    def test_export_trace_request_accepts_known_formats(self) -> None:
        for fmt in ("json", "JSONL", "Summary"):
            assert ExportAgentTraceRequest(trace_id="t1", format=fmt).format == fmt

    def test_replay_events_request_rejects_invalid_mode(self) -> None:
        with pytest.raises(ValueError):
            ReplayRuntimeEventsRequest(replay_mode="bogus")

    def test_replay_dead_letter_request_rejects_empty_id(self) -> None:
        with pytest.raises(ValueError):
            ReplayDeadLetterRequest(dead_letter_id="")

    def test_publish_event_request_rejects_empty_type(self) -> None:
        with pytest.raises(ValueError):
            PublishRuntimeEventRequest(event_type=" ")

    def test_compute_request_fingerprint_ignores_key_order(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_CREATE)
        fp1 = compute_request_fingerprint(req, {"a": 1, "b": 2})
        fp2 = compute_request_fingerprint(req, {"b": 2, "a": 1})
        assert fp1 == fp2


class TestIdempotencyStore:
    """In-memory idempotency store: fingerprint matching, TTL, cleanup."""

    def test_store_and_get_roundtrip(self) -> None:
        store = InMemoryAgentRuntimeApiIdempotencyStore()
        store.store("k1", "fp1", "result")
        entry = store.get("k1")
        assert entry is not None
        assert entry.result == "result"

    def test_get_missing_key_returns_none(self) -> None:
        assert InMemoryAgentRuntimeApiIdempotencyStore().get("missing") is None

    def test_get_expired_entry_returns_none(self) -> None:
        store = InMemoryAgentRuntimeApiIdempotencyStore(default_ttl_seconds=1.0)
        store.store("k1", "fp1", "r")
        store._store["k1"].created_at -= 10.0  # deterministic forced expiry
        assert store.get("k1") is None

    def test_remove_existing_key(self) -> None:
        store = InMemoryAgentRuntimeApiIdempotencyStore()
        store.store("k1", "fp1", "r")
        assert store.remove("k1") is not None
        assert store.get("k1") is None

    def test_remove_missing_key_returns_none(self) -> None:
        assert InMemoryAgentRuntimeApiIdempotencyStore().remove("missing") is None

    def test_clear_removes_only_expired(self) -> None:
        store = InMemoryAgentRuntimeApiIdempotencyStore(default_ttl_seconds=300.0)
        store.store("fresh", "fp", "r")
        store.store("stale", "fp", "r")
        store._store["stale"].created_at -= 10_000
        removed = store.clear()
        assert removed == 1
        assert store.get("fresh") is not None
        assert "stale" not in store._store

    def test_size_property(self) -> None:
        store = InMemoryAgentRuntimeApiIdempotencyStore()
        store.store("k1", "fp1", "r")
        store.store("k2", "fp2", "r")
        assert store.size == 2

    def test_store_rejects_empty_key(self) -> None:
        with pytest.raises(ValueError):
            InMemoryAgentRuntimeApiIdempotencyStore().store("", "fp", "r")

    def test_store_rejects_empty_fingerprint(self) -> None:
        with pytest.raises(ValueError):
            InMemoryAgentRuntimeApiIdempotencyStore().store("k1", "", "r")

    def test_init_rejects_nonpositive_ttl(self) -> None:
        with pytest.raises(ValueError):
            InMemoryAgentRuntimeApiIdempotencyStore(default_ttl_seconds=0)

    def test_compute_fingerprint_ignores_key_order(self) -> None:
        fp1 = compute_fingerprint("goal.create", {"a": 1, "b": 2})
        fp2 = compute_fingerprint("goal.create", {"b": 2, "a": 1})
        assert fp1 == fp2

    def test_compute_fingerprint_rejects_empty_operation(self) -> None:
        with pytest.raises(ValueError):
            compute_fingerprint("", {})


class TestRouter:
    """Registration, resolution and dispatch semantics of the API router."""

    @staticmethod
    def _noop_handler(
        request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
    ) -> AgentRuntimeApiResponse:
        return AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS, request_id=request.request_id
        )

    def test_register_and_resolve(self) -> None:
        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, self._noop_handler)
        assert router.resolve(AgentRuntimeApiOperation.GOAL_GET) is self._noop_handler

    def test_register_duplicate_raises(self) -> None:
        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, self._noop_handler)
        with pytest.raises(AgentRuntimeApiException):
            router.register(AgentRuntimeApiOperation.GOAL_GET, self._noop_handler)

    def test_register_rejects_non_callable_handler(self) -> None:
        router = AgentRuntimeApiRouter()
        with pytest.raises(AgentRuntimeApiException):
            router.register(AgentRuntimeApiOperation.GOAL_GET, "not-callable")

    def test_register_with_aliases_resolves(self) -> None:
        router = AgentRuntimeApiRouter()
        router.register(
            AgentRuntimeApiOperation.GOAL_GET,
            self._noop_handler,
            aliases=["goal.fetch"],
        )
        assert router._resolve_op_key("goal.fetch") is self._noop_handler

    def test_register_alias_conflicts_with_existing_operation(self) -> None:
        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, self._noop_handler)
        with pytest.raises(AgentRuntimeApiException):
            router.register(
                AgentRuntimeApiOperation.GOAL_LIST,
                self._noop_handler,
                aliases=["goal.get"],
            )

    def test_unregister_removes_handler(self) -> None:
        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, self._noop_handler)
        router.unregister(AgentRuntimeApiOperation.GOAL_GET)
        assert not router.has_operation(AgentRuntimeApiOperation.GOAL_GET)

    def test_unregister_missing_raises(self) -> None:
        with pytest.raises(AgentRuntimeApiException):
            AgentRuntimeApiRouter().unregister(AgentRuntimeApiOperation.GOAL_GET)

    def test_resolve_unknown_raises(self) -> None:
        with pytest.raises(AgentRuntimeApiException):
            AgentRuntimeApiRouter().resolve(AgentRuntimeApiOperation.GOAL_GET)

    def test_list_operations(self) -> None:
        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, self._noop_handler)
        assert router.list_operations() == ["goal.get"]

    def test_dispatch_missing_operation_returns_validation_error(self) -> None:
        router = AgentRuntimeApiRouter()
        req = AgentRuntimeApiRequest(operation=None)
        resp = router.dispatch(req, AgentRuntimeApiContext(actor="alice"))
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "VALIDATION_ERROR"

    def test_dispatch_unregistered_operation_returns_error_response(self) -> None:
        router = AgentRuntimeApiRouter()
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        resp = router.dispatch(req, AgentRuntimeApiContext(actor="alice"))
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "UNSUPPORTED_OPERATION"

    def test_dispatch_success_without_middleware(self) -> None:
        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, self._noop_handler)
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        resp = router.dispatch(req, AgentRuntimeApiContext(actor="alice"))
        assert resp.status == AgentRuntimeApiStatus.SUCCESS

    def test_dispatch_converts_unexpected_exception_to_internal_error(self) -> None:
        def boom(
            request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
        ) -> AgentRuntimeApiResponse:
            raise RuntimeError("kaboom")

        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, boom)
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        resp = router.dispatch(req, AgentRuntimeApiContext(actor="alice"))
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "INTERNAL_ERROR"
        assert "kaboom" not in resp.errors[0].message

    def test_dispatch_propagates_application_error_as_response(self) -> None:
        def boom(
            request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
        ) -> AgentRuntimeApiResponse:
            raise AgentRuntimeApiNotFoundError("Goal x not found")

        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, boom)
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        resp = router.dispatch(req, AgentRuntimeApiContext(actor="alice"))
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "NOT_FOUND"

    def test_middleware_runs_in_registration_order(self) -> None:
        order: list[str] = []

        class Track(AgentRuntimeApiMiddleware):
            def __init__(self, name: str) -> None:
                self._name = name

            def forward(self, request, context):
                order.append(f"forward:{self._name}")
                return request, context

            def after(self, request, context, response):
                order.append(f"after:{self._name}")
                return response

        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, self._noop_handler)
        router.add_middleware(Track("a"))
        router.add_middleware(Track("b"))
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        router.dispatch(req, AgentRuntimeApiContext(actor="alice"))
        assert order == ["forward:a", "forward:b", "after:b", "after:a"]

    def test_middleware_on_error_can_recover(self) -> None:
        class Recover(AgentRuntimeApiMiddleware):
            def on_error(self, request, context, error):
                return AgentRuntimeApiResponse(
                    status=AgentRuntimeApiStatus.PARTIAL, request_id=request.request_id
                )

        def boom(
            request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
        ) -> AgentRuntimeApiResponse:
            raise RuntimeError("boom")

        router = AgentRuntimeApiRouter()
        router.register(AgentRuntimeApiOperation.GOAL_GET, boom)
        router.add_middleware(Recover())
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        resp = router.dispatch(req, AgentRuntimeApiContext(actor="alice"))
        assert resp.status == AgentRuntimeApiStatus.PARTIAL


class TestMiddleware:
    """Individual middleware behavior in isolation."""

    def test_request_id_middleware_fills_missing_id(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        object.__setattr__(req, "request_id", "")
        new_req, _ = RequestIdMiddleware().forward(
            req, AgentRuntimeApiContext(actor="a")
        )
        assert new_req.request_id

    def test_authentication_middleware_passes_valid_actor(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        ctx = AgentRuntimeApiContext(actor="alice")
        _, result_ctx = AuthenticationContextMiddleware().forward(req, ctx)
        assert result_ctx.actor == "alice"

    def test_authentication_middleware_rejects_blank_actor(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        ctx = AgentRuntimeApiContext(actor="alice")
        object.__setattr__(ctx, "actor", "   ")
        with pytest.raises(AgentRuntimeApiException):
            AuthenticationContextMiddleware().forward(req, ctx)

    def test_permission_middleware_allows_when_granted(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_CREATE)
        ctx = AgentRuntimeApiContext(
            actor="alice", permissions=frozenset({"goal:write"})
        )
        PermissionMiddleware().forward(req, ctx)

    def test_permission_middleware_denies_when_missing(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_CREATE)
        ctx = AgentRuntimeApiContext(actor="alice")
        with pytest.raises(AgentRuntimeApiException):
            PermissionMiddleware().forward(req, ctx)

    def test_validation_middleware_rejects_sensitive_key(self) -> None:
        req = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.GOAL_CREATE,
            payload={"notes": "contains password=hunter2"},
        )
        ctx = AgentRuntimeApiContext(actor="alice")
        with pytest.raises(AgentRuntimeApiException):
            ValidationMiddleware().forward(req, ctx)

    def test_validation_middleware_rejects_dangerous_code(self) -> None:
        req = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.GOAL_CREATE,
            payload={"title": "eval(malicious)"},
        )
        ctx = AgentRuntimeApiContext(actor="alice")
        with pytest.raises(AgentRuntimeApiException):
            ValidationMiddleware().forward(req, ctx)

    def test_validation_middleware_allows_safe_payload(self) -> None:
        req = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.GOAL_CREATE,
            payload={"title": "Launch", "objective": "Ship it"},
        )
        ValidationMiddleware().forward(req, AgentRuntimeApiContext(actor="alice"))

    def test_redaction_middleware_redacts_sensitive_fields(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        ctx = AgentRuntimeApiContext(actor="alice")
        resp = AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS,
            data={"title": "ok", "password": "hunter2", "nested": {"token": "abc"}},
        )
        result = RedactionMiddleware().after(req, ctx, resp)
        assert result.data["password"] == "**REDACTED**"
        assert result.data["nested"]["token"] == "**REDACTED**"
        assert result.data["title"] == "ok"

    def test_redaction_middleware_passes_through_non_dict_data(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        ctx = AgentRuntimeApiContext(actor="alice")
        resp = AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS, data="plain"
        )
        result = RedactionMiddleware().after(req, ctx, resp)
        assert result.data == "plain"

    def test_redaction_middleware_fails_closed_on_error(self) -> None:
        class ExplodingDict(dict):
            def items(self):
                raise RuntimeError("boom")

        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        ctx = AgentRuntimeApiContext(actor="alice")
        resp = AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS, data=ExplodingDict({"a": 1})
        )
        with pytest.raises(AgentRuntimeApiException) as exc_info:
            RedactionMiddleware().after(req, ctx, resp)
        assert "boom" not in str(exc_info.value)

    def test_audit_middleware_records_entry(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_CREATE)
        ctx = AgentRuntimeApiContext(actor="alice")
        resp = AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS, request_id=req.request_id
        )
        mw = AuditMiddleware()
        mw.after(req, ctx, resp)
        assert len(mw.audit_log) == 1
        assert mw.audit_log[0]["actor"] == "alice"
        assert mw.audit_log[0]["operation"] == "goal.create"

    def test_audit_middleware_clear(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_CREATE)
        ctx = AgentRuntimeApiContext(actor="alice")
        resp = AgentRuntimeApiResponse(status=AgentRuntimeApiStatus.SUCCESS)
        mw = AuditMiddleware()
        mw.after(req, ctx, resp)
        mw.clear()
        assert mw.audit_log == []

    def test_audit_middleware_records_failure_without_raising(self) -> None:
        req = AgentRuntimeApiRequest(operation=None)
        ctx = AgentRuntimeApiContext(actor="alice")
        resp = AgentRuntimeApiResponse(status=AgentRuntimeApiStatus.SUCCESS)
        mw = AuditMiddleware()
        result = mw.after(req, ctx, resp)
        assert result is resp
        assert len(mw.audit_failures) == 1
        assert mw.audit_failures[0]["error_type"] == "AttributeError"

    def test_metrics_middleware_counts_operations(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_CREATE)
        ctx = AgentRuntimeApiContext(actor="alice")
        mw = MetricsMiddleware()
        mw.forward(req, ctx)
        resp = AgentRuntimeApiResponse(
            status=AgentRuntimeApiStatus.SUCCESS, request_id=req.request_id
        )
        mw.after(req, ctx, resp)
        assert mw.operation_count == 1

    def test_metrics_middleware_records_failure_without_raising(self) -> None:
        req = AgentRuntimeApiRequest(operation=None)
        ctx = AgentRuntimeApiContext(actor="alice")
        resp = AgentRuntimeApiResponse(status=AgentRuntimeApiStatus.SUCCESS)
        mw = MetricsMiddleware()
        result = mw.after(req, ctx, resp)
        assert result is resp
        assert len(mw.metrics_failures) == 1

    def test_error_mapping_middleware_maps_application_error(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        ctx = AgentRuntimeApiContext(actor="alice")
        result = ErrorMappingMiddleware().on_error(
            req, ctx, AgentRuntimeApiNotFoundError("Goal x not found")
        )
        assert result.errors[0].code == "NOT_FOUND"

    def test_error_mapping_middleware_maps_generic_error(self) -> None:
        req = AgentRuntimeApiRequest(operation=AgentRuntimeApiOperation.GOAL_GET)
        ctx = AgentRuntimeApiContext(actor="alice")
        result = ErrorMappingMiddleware().on_error(
            req, ctx, RuntimeError("leaky secret")
        )
        assert result.errors[0].code == "INTERNAL_ERROR"
        assert "leaky secret" not in result.errors[0].message

    def test_default_middleware_chain_order(self) -> None:
        names = [type(m).__name__ for m in create_default_middleware_chain()]
        assert names == [
            "RequestIdMiddleware",
            "AuthenticationContextMiddleware",
            "PermissionMiddleware",
            "ValidationMiddleware",
            "MetricsMiddleware",
            "ErrorMappingMiddleware",
            "AuditMiddleware",
            "RedactionMiddleware",
        ]


# ═════════════════════════════════════════════════════════════════════════
# Block 2: adapters and end-to-end service integration
# ═════════════════════════════════════════════════════════════════════════


def _req(
    op: AgentRuntimeApiOperation, payload: dict | None = None
) -> AgentRuntimeApiRequest:
    return AgentRuntimeApiRequest(operation=op, payload=payload or {})


def _ctx(actor: str = "alice", *perms: str) -> AgentRuntimeApiContext:
    return AgentRuntimeApiContext(actor=actor, permissions=frozenset(perms))


class TestGoalApiAdapter:
    """A. Goal API adapter - CRUD, transitions, defensive copying."""

    def test_create(self) -> None:
        a = GoalApiAdapter()
        resp = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.SUCCESS
        assert resp.data.title == "T"
        assert resp.data.creator == "alice"

    def test_get(self) -> None:
        a = GoalApiAdapter()
        created = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            _ctx(),
        )
        resp = a.get(
            _req(AgentRuntimeApiOperation.GOAL_GET, {"goal_id": created.data.goal_id}),
            _ctx(),
        )
        assert resp.data.goal_id == created.data.goal_id

    def test_list(self) -> None:
        a = GoalApiAdapter()
        a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE,
                {"title": "A", "objective": "O", "priority": 2},
            ),
            _ctx(),
        )
        a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE,
                {"title": "B", "objective": "O", "priority": 1},
            ),
            _ctx(),
        )
        resp = a.list(_req(AgentRuntimeApiOperation.GOAL_LIST), _ctx())
        assert resp.data["total"] == 2
        assert resp.data["items"][0].title == "B"

    def test_update(self) -> None:
        a = GoalApiAdapter()
        created = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            _ctx(),
        )
        resp = a.update(
            _req(
                AgentRuntimeApiOperation.GOAL_UPDATE,
                {"goal_id": created.data.goal_id, "title": "T2"},
            ),
            _ctx(),
        )
        assert resp.data.title == "T2"

    def test_prioritize(self) -> None:
        a = GoalApiAdapter()
        created = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            _ctx(),
        )
        resp = a.prioritize(
            _req(
                AgentRuntimeApiOperation.GOAL_PRIORITIZE,
                {"goal_id": created.data.goal_id, "new_priority": 9},
            ),
            _ctx(),
        )
        assert resp.data.priority == 9

    def test_pause(self) -> None:
        a = GoalApiAdapter()
        created = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            _ctx(),
        )
        resp = a.pause(
            _req(
                AgentRuntimeApiOperation.GOAL_PAUSE, {"goal_id": created.data.goal_id}
            ),
            _ctx(),
        )
        assert resp.data.status == "paused"

    def test_resume(self) -> None:
        a = GoalApiAdapter()
        created = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            _ctx(),
        )
        a.pause(
            _req(
                AgentRuntimeApiOperation.GOAL_PAUSE, {"goal_id": created.data.goal_id}
            ),
            _ctx(),
        )
        resp = a.resume(
            _req(
                AgentRuntimeApiOperation.GOAL_RESUME, {"goal_id": created.data.goal_id}
            ),
            _ctx(),
        )
        assert resp.data.status == "active"

    def test_cancel(self) -> None:
        a = GoalApiAdapter()
        created = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            _ctx(),
        )
        resp = a.cancel(
            _req(
                AgentRuntimeApiOperation.GOAL_CANCEL, {"goal_id": created.data.goal_id}
            ),
            _ctx(),
        )
        assert resp.data.status == "cancelled"

    def test_goal_inexistente(self) -> None:
        resp = GoalApiAdapter().get(
            _req(AgentRuntimeApiOperation.GOAL_GET, {"goal_id": "missing"}), _ctx()
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.NOT_FOUND

    def test_title_empty(self) -> None:
        resp = GoalApiAdapter().create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "  ", "objective": "O"}
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.VALIDATION_ERROR

    def test_objective_empty(self) -> None:
        resp = GoalApiAdapter().create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": " "}
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.VALIDATION_ERROR

    def test_transition_invalid(self) -> None:
        a = GoalApiAdapter()
        created = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            _ctx(),
        )
        # goal is active; resume requires paused -> invalid transition
        resp = a.resume(
            _req(
                AgentRuntimeApiOperation.GOAL_RESUME, {"goal_id": created.data.goal_id}
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.STATE_ERROR

    def test_completed_not_cancellable(self) -> None:
        a = GoalApiAdapter()
        created = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            _ctx(),
        )
        a._goals[created.data.goal_id]["status"] = "completed"
        resp = a.cancel(
            _req(
                AgentRuntimeApiOperation.GOAL_CANCEL, {"goal_id": created.data.goal_id}
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.STATE_ERROR

    def test_response_defensively_copied(self) -> None:
        a = GoalApiAdapter()
        created = a.create(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE,
                {"title": "T", "objective": "O", "context": {"k": "v"}},
            ),
            _ctx(),
        )
        created.data.context["k"] = "mutated"
        fetched = a.get(
            _req(AgentRuntimeApiOperation.GOAL_GET, {"goal_id": created.data.goal_id}),
            _ctx(),
        )
        assert fetched.data.context["k"] == "v"


class TestAgentRunApiAdapter:
    """B. Agent Run API adapter - lifecycle + goal cross-validation."""

    def test_start(self) -> None:
        resp = AgentRunApiAdapter().start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        assert resp.status == AgentRuntimeApiStatus.SUCCESS
        assert resp.data.status == "running"

    def test_get(self) -> None:
        a = AgentRunApiAdapter()
        started = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        resp = a.get(
            _req(AgentRuntimeApiOperation.RUN_GET, {"run_id": started.data.run_id}),
            _ctx(),
        )
        assert resp.data.run_id == started.data.run_id

    def test_list(self) -> None:
        a = AgentRunApiAdapter()
        a.start(_req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx())
        a.start(_req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-2"}), _ctx())
        resp = a.list(_req(AgentRuntimeApiOperation.RUN_LIST), _ctx())
        assert resp.data["total"] == 2

    def test_pause(self) -> None:
        a = AgentRunApiAdapter()
        started = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        resp = a.pause(
            _req(AgentRuntimeApiOperation.RUN_PAUSE, {"run_id": started.data.run_id}),
            _ctx(),
        )
        assert resp.data.status == "paused"

    def test_resume(self) -> None:
        a = AgentRunApiAdapter()
        started = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        a.pause(
            _req(AgentRuntimeApiOperation.RUN_PAUSE, {"run_id": started.data.run_id}),
            _ctx(),
        )
        resp = a.resume(
            _req(AgentRuntimeApiOperation.RUN_RESUME, {"run_id": started.data.run_id}),
            _ctx(),
        )
        assert resp.data.status == "running"

    def test_cancel(self) -> None:
        a = AgentRunApiAdapter()
        started = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        resp = a.cancel(
            _req(AgentRuntimeApiOperation.RUN_CANCEL, {"run_id": started.data.run_id}),
            _ctx(),
        )
        assert resp.data.status == "cancelled"

    def test_goal_inexistente(self) -> None:
        a = AgentRunApiAdapter(goal_lookup=lambda gid: None)
        resp = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "missing"}), _ctx()
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.NOT_FOUND

    def test_goal_blocked(self) -> None:
        a = AgentRunApiAdapter(goal_lookup=lambda gid: "paused")
        resp = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.STATE_ERROR

    def test_goal_cancelled(self) -> None:
        a = AgentRunApiAdapter(goal_lookup=lambda gid: "cancelled")
        resp = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.STATE_ERROR

    def test_pause_terminal(self) -> None:
        a = AgentRunApiAdapter()
        started = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        a.cancel(
            _req(AgentRuntimeApiOperation.RUN_CANCEL, {"run_id": started.data.run_id}),
            _ctx(),
        )
        resp = a.pause(
            _req(AgentRuntimeApiOperation.RUN_PAUSE, {"run_id": started.data.run_id}),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.STATE_ERROR

    def test_resume_not_paused(self) -> None:
        a = AgentRunApiAdapter()
        started = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        resp = a.resume(
            _req(AgentRuntimeApiOperation.RUN_RESUME, {"run_id": started.data.run_id}),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.STATE_ERROR

    def test_cancel_terminal(self) -> None:
        a = AgentRunApiAdapter()
        started = a.start(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": "goal-1"}), _ctx()
        )
        a.cancel(
            _req(AgentRuntimeApiOperation.RUN_CANCEL, {"run_id": started.data.run_id}),
            _ctx(),
        )
        resp = a.cancel(
            _req(AgentRuntimeApiOperation.RUN_CANCEL, {"run_id": started.data.run_id}),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.STATE_ERROR

    def test_idempotencia_start(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write", "run:write")
        goal = service.execute(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            ctx,
        )
        payload = {"goal_id": goal.data.goal_id}
        req1 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.RUN_START,
            payload=payload,
            idempotency_key="run-key-1",
        )
        req2 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.RUN_START,
            payload=payload,
            idempotency_key="run-key-1",
        )
        resp1 = service.execute(req1, ctx)
        resp2 = service.execute(req2, ctx)
        assert resp1.data.run_id == resp2.data.run_id
        listing = service.run_adapter.list(_req(AgentRuntimeApiOperation.RUN_LIST), ctx)
        assert listing.data["total"] == 1


class TestApprovalApiAdapter:
    """C. Approval API adapter - decisions, expiry, authorization."""

    def test_list_pending(self) -> None:
        a = ApprovalApiAdapter()
        a.request_approval(requirement={"kind": "x"})
        resp = a.list(_req(AgentRuntimeApiOperation.APPROVAL_LIST), _ctx())
        assert resp.data["total"] == 1

    def test_get(self) -> None:
        a = ApprovalApiAdapter()
        created = a.request_approval(requirement={"kind": "x"})
        resp = a.get(
            _req(
                AgentRuntimeApiOperation.APPROVAL_GET,
                {"approval_id": created.approval_id},
            ),
            _ctx(),
        )
        assert resp.data.approval_id == created.approval_id

    def test_approve(self) -> None:
        a = ApprovalApiAdapter()
        created = a.request_approval(requirement={"kind": "x"})
        resp = a.approve(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": created.approval_id},
            ),
            _ctx(),
        )
        assert resp.data.status == "approved"
        assert resp.data.actor == "alice"

    def test_reject(self) -> None:
        a = ApprovalApiAdapter()
        created = a.request_approval(requirement={"kind": "x"})
        resp = a.reject(
            _req(
                AgentRuntimeApiOperation.APPROVAL_REJECT,
                {"approval_id": created.approval_id, "reason": "no"},
            ),
            _ctx(),
        )
        assert resp.data.status == "rejected"
        assert resp.data.comment == "no"

    def test_request_inexistente(self) -> None:
        resp = ApprovalApiAdapter().get(
            _req(AgentRuntimeApiOperation.APPROVAL_GET, {"approval_id": "missing"}),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.NOT_FOUND

    def test_expirado(self) -> None:
        a = ApprovalApiAdapter()
        created = a.request_approval(
            requirement={"kind": "x"}, expires_at="2000-01-01T00:00:00+00:00"
        )
        resp = a.approve(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": created.approval_id},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.STATE_ERROR

    def test_actor_no_autorizado(self) -> None:
        a = ApprovalApiAdapter()
        created = a.request_approval(requirement={"kind": "x"}, assigned_to="bob")
        resp = a.approve(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": created.approval_id},
            ),
            _ctx("alice"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.PERMISSION_DENIED

    def test_decision_duplicada(self) -> None:
        a = ApprovalApiAdapter()
        created = a.request_approval(requirement={"kind": "x"})
        a.approve(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": created.approval_id},
            ),
            _ctx(),
        )
        resp = a.reject(
            _req(
                AgentRuntimeApiOperation.APPROVAL_REJECT,
                {"approval_id": created.approval_id},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.CONFLICT

    def test_comentario_opcional(self) -> None:
        a = ApprovalApiAdapter()
        created = a.request_approval(requirement={"kind": "x"})
        resp = a.approve(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": created.approval_id},
            ),
            _ctx(),
        )
        assert resp.data.comment is None

    def test_no_fake_approval(self) -> None:
        assert not hasattr(AgentRuntimeApiOperation, "APPROVAL_CREATE")
        assert not hasattr(AgentRuntimeApiOperation, "APPROVAL_REQUEST")
        known = {"approval.list", "approval.get", "approval.approve", "approval.reject"}
        ops = AgentRuntimeApiService().router.list_operations()
        assert all(not op.startswith("approval.") or op in known for op in ops)


class TestBudgetApiAdapter:
    """D. Budget API adapter - reserve/release, unit safety."""

    def test_get(self) -> None:
        resp = BudgetApiAdapter().get(
            _req(AgentRuntimeApiOperation.BUDGET_GET, {"budget_id": "b1"}), _ctx()
        )
        assert resp.data.budget_id == "b1"
        assert resp.data.limit == 100.0

    def test_reserve(self) -> None:
        resp = BudgetApiAdapter().reserve(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 10},
            ),
            _ctx(),
        )
        assert resp.data.reserved == 10.0

    def test_release(self) -> None:
        a = BudgetApiAdapter()
        reserved = a.reserve(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 10},
            ),
            _ctx(),
        )
        rid = reserved.data.reservation["reservation_id"]
        resp = a.release(
            _req(
                AgentRuntimeApiOperation.BUDGET_RELEASE,
                {"budget_id": "b1", "reservation_id": rid, "amount": 10},
            ),
            _ctx(),
        )
        assert resp.data.reserved == 0.0

    def test_cantidad_cero(self) -> None:
        resp = BudgetApiAdapter().reserve(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 0},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.VALIDATION_ERROR

    def test_cantidad_negativa(self) -> None:
        resp = BudgetApiAdapter().reserve(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": -5},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.VALIDATION_ERROR

    def test_exceeded(self) -> None:
        resp = BudgetApiAdapter().reserve(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 1000},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.BUDGET_EXCEEDED

    def test_over_release(self) -> None:
        a = BudgetApiAdapter()
        reserved = a.reserve(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 10},
            ),
            _ctx(),
        )
        rid = reserved.data.reservation["reservation_id"]
        resp = a.release(
            _req(
                AgentRuntimeApiOperation.BUDGET_RELEASE,
                {"budget_id": "b1", "reservation_id": rid, "amount": 20},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.VALIDATION_ERROR

    def test_unidad_incompatible(self) -> None:
        a = BudgetApiAdapter()
        a.reserve(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 5, "unit": "iteration"},
            ),
            _ctx(),
        )
        resp = a.reserve(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 5, "unit": "usd"},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.VALIDATION_ERROR

    def test_reservation_id(self) -> None:
        resp = BudgetApiAdapter().reserve(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 5, "reservation_id": "custom-id"},
            ),
            _ctx(),
        )
        assert resp.data.reservation["reservation_id"] == "custom-id"

    def test_idempotencia(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "budget:write")
        payload = {"budget_id": "b1", "amount": 5}
        req1 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.BUDGET_RESERVE,
            payload=payload,
            idempotency_key="budget-key-1",
        )
        req2 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.BUDGET_RESERVE,
            payload=payload,
            idempotency_key="budget-key-1",
        )
        resp1 = service.execute(req1, ctx)
        resp2 = service.execute(req2, ctx)
        assert resp1.data.reserved == resp2.data.reserved == 5.0


class TestTraceApiAdapter:
    """E. Trace API adapter - hash-chain integrity, export sanitization."""

    def test_get(self) -> None:
        a = TraceApiAdapter()
        created = a.create_trace(run_id="run-1", goal_id="goal-1")
        resp = a.get(
            _req(AgentRuntimeApiOperation.TRACE_GET, {"trace_id": created.trace_id}),
            _ctx(),
        )
        assert resp.data.trace_id == created.trace_id

    def test_list(self) -> None:
        a = TraceApiAdapter()
        a.create_trace()
        a.create_trace()
        resp = a.list(_req(AgentRuntimeApiOperation.TRACE_LIST), _ctx())
        assert resp.data["total"] == 2

    def test_verify(self) -> None:
        a = TraceApiAdapter()
        created = a.create_trace()
        a.append_record(created.trace_id, {"step": 1})
        resp = a.verify(
            _req(AgentRuntimeApiOperation.TRACE_VERIFY, {"trace_id": created.trace_id}),
            _ctx(),
        )
        assert resp.data.integrity_status == "verified"

    def test_export_json(self) -> None:
        a = TraceApiAdapter()
        created = a.create_trace()
        a.append_record(created.trace_id, {"step": 1})
        resp = a.export(
            _req(
                AgentRuntimeApiOperation.TRACE_EXPORT,
                {"trace_id": created.trace_id, "format": "JSON"},
            ),
            _ctx(),
        )
        assert resp.data.export_format == "JSON"
        assert isinstance(resp.data.export_data, str)
        assert '"step": 1' in resp.data.export_data

    def test_export_jsonl(self) -> None:
        a = TraceApiAdapter()
        created = a.create_trace()
        a.append_record(created.trace_id, {"step": 1})
        resp = a.export(
            _req(
                AgentRuntimeApiOperation.TRACE_EXPORT,
                {"trace_id": created.trace_id, "format": "JSONL"},
            ),
            _ctx(),
        )
        assert resp.data.export_format == "JSONL"
        assert '"trace_id"' in resp.data.export_data

    def test_export_summary(self) -> None:
        a = TraceApiAdapter()
        created = a.create_trace()
        a.append_record(created.trace_id, {"step": 1})
        resp = a.export(
            _req(
                AgentRuntimeApiOperation.TRACE_EXPORT,
                {"trace_id": created.trace_id, "format": "SUMMARY"},
            ),
            _ctx(),
        )
        assert resp.data.export_data["summary"] == "1 records"

    def test_not_found(self) -> None:
        resp = TraceApiAdapter().get(
            _req(AgentRuntimeApiOperation.TRACE_GET, {"trace_id": "missing"}), _ctx()
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.NOT_FOUND

    def test_permission_denied(self) -> None:
        a = TraceApiAdapter()
        created = a.create_trace(owner="alice")
        resp = a.get(
            _req(AgentRuntimeApiOperation.TRACE_GET, {"trace_id": created.trace_id}),
            _ctx("bob"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.PERMISSION_DENIED

    def test_no_chain_of_thought(self) -> None:
        a = TraceApiAdapter()
        created = a.create_trace()
        a.append_record(
            created.trace_id, {"chain_of_thought": "secret reasoning", "step": 1}
        )
        resp = a.export(
            _req(
                AgentRuntimeApiOperation.TRACE_EXPORT,
                {"trace_id": created.trace_id, "format": "JSON"},
            ),
            _ctx(),
        )
        assert "secret reasoning" not in resp.data.export_data
        assert "**REDACTED**" in resp.data.export_data

    def test_integrity_no_fake_valid(self) -> None:
        a = TraceApiAdapter()
        created = a.create_trace()
        a.append_record(created.trace_id, {"step": 1})
        a.append_record(created.trace_id, {"step": 2})
        a._traces[created.trace_id]["records"][0]["data"] = {"step": 999}  # tamper
        resp = a.verify(
            _req(AgentRuntimeApiOperation.TRACE_VERIFY, {"trace_id": created.trace_id}),
            _ctx(),
        )
        assert resp.data.integrity_status == "tampered"


class TestRuntimeEventApiAdapter:
    """F. Runtime event API adapter - validation, dedup, dead-letter."""

    def test_publish(self) -> None:
        resp = RuntimeEventApiAdapter().publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.SUCCESS
        assert resp.data.event_type == EventType.GOAL_CREATED
        assert resp.data.category == "goal"

    def test_list(self) -> None:
        a = RuntimeEventApiAdapter()
        a.publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx(),
        )
        resp = a.list(_req(AgentRuntimeApiOperation.EVENT_LIST), _ctx())
        assert resp.data["total"] == 1

    def test_replay(self) -> None:
        a = RuntimeEventApiAdapter()
        published = a.publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx(),
        )
        resp = a.replay(
            _req(
                AgentRuntimeApiOperation.EVENT_REPLAY,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx(),
        )
        assert resp.data["replayed"] == 1
        assert resp.data["events"][0].original_event_id == published.data.event_id

    def test_dead_letter_list(self) -> None:
        a = RuntimeEventApiAdapter()
        published = a.publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx(),
        )
        a.route_to_dead_letter(published.data.event_id, reason="delivery failed")
        resp = a.list_dead_letters(
            _req(AgentRuntimeApiOperation.DEAD_LETTER_LIST), _ctx()
        )
        assert resp.data["total"] == 1

    def test_dead_letter_replay(self) -> None:
        a = RuntimeEventApiAdapter()
        published = a.publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx(),
        )
        dl = a.route_to_dead_letter(published.data.event_id, reason="delivery failed")
        resp = a.replay_dead_letter(
            _req(
                AgentRuntimeApiOperation.DEAD_LETTER_REPLAY,
                {"dead_letter_id": dl.dead_letter_id},
            ),
            _ctx(),
        )
        assert resp.data["replayed"] is True
        assert resp.data["event"].original_event_id == published.data.event_id

    def test_evento_tipo_desconocido(self) -> None:
        resp = RuntimeEventApiAdapter().publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": "not.a.real.type"},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.VALIDATION_ERROR

    def test_evento_duplicado(self) -> None:
        a = RuntimeEventApiAdapter()
        first = a.publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED, "dedup_key": "dk1"},
            ),
            _ctx(),
        )
        second = a.publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED, "dedup_key": "dk1"},
            ),
            _ctx(),
        )
        assert first.data.event_id == second.data.event_id
        assert (
            a.list(_req(AgentRuntimeApiOperation.EVENT_LIST), _ctx()).data["total"] == 1
        )

    def test_payload_inseguro(self) -> None:
        resp = RuntimeEventApiAdapter().publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED, "note": "token=abc123"},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.VALIDATION_ERROR

    def test_replay_conserva_original_event_id(self) -> None:
        a = RuntimeEventApiAdapter()
        published = a.publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx(),
        )
        resp = a.replay(_req(AgentRuntimeApiOperation.EVENT_REPLAY), _ctx())
        assert resp.data["events"][0].original_event_id == published.data.event_id

    def test_no_fake_delivered(self) -> None:
        resp = RuntimeEventApiAdapter().publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx(),
        )
        assert resp.data.delivery["status"] == "recorded"
        assert resp.data.delivery["status"] != "delivered"

    def test_no_silent_drop(self) -> None:
        resp = RuntimeEventApiAdapter().replay_dead_letter(
            _req(
                AgentRuntimeApiOperation.DEAD_LETTER_REPLAY,
                {"dead_letter_id": "missing"},
            ),
            _ctx(),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == AgentRuntimeApiErrorCode.NOT_FOUND

    def test_append_only(self) -> None:
        a = RuntimeEventApiAdapter()
        a.publish(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx(),
        )
        a.replay(_req(AgentRuntimeApiOperation.EVENT_REPLAY), _ctx())
        assert len(a._events) == 2
        first_id = a._events[0]["event_id"]
        a.replay(_req(AgentRuntimeApiOperation.EVENT_REPLAY), _ctx())
        assert len(a._events) == 4
        assert a._events[0]["event_id"] == first_id


class TestRuntimeSystemApiAdapter:
    """G. Runtime system API adapter - honest health/stats."""

    def test_health_available(self) -> None:
        a = RuntimeSystemApiAdapter()
        for name in ("goal_manager", "goal_repository", "event_bus", "trace_service"):
            a.set_component_wired(name, True)
        resp = a.health(_req(AgentRuntimeApiOperation.RUNTIME_HEALTH), _ctx())
        assert resp.data.status == "healthy"
        assert resp.data.event_bus == "available"

    def test_health_unavailable(self) -> None:
        resp = RuntimeSystemApiAdapter().health(
            _req(AgentRuntimeApiOperation.RUNTIME_HEALTH), _ctx()
        )
        assert resp.data.status == "degraded"
        assert resp.data.event_bus == "unavailable"

    def test_stats_basicas(self) -> None:
        a = RuntimeSystemApiAdapter()
        a.record_operation(10.0)
        a.record_operation(30.0)
        a.record_error()
        resp = a.stats(_req(AgentRuntimeApiOperation.RUNTIME_STATS), _ctx())
        assert resp.data.operations_executed == 2
        assert resp.data.api_errors == 1
        assert resp.data.latency_average_ms == 20.0

    def test_componente_ausente(self) -> None:
        a = RuntimeSystemApiAdapter()
        a.set_component_wired("trace_service", True)
        resp = a.stats(_req(AgentRuntimeApiOperation.RUNTIME_STATS), _ctx())
        assert "goal_manager" in resp.data.unavailable
        assert "trace_service" not in resp.data.unavailable

    def test_no_managers_inventados(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "system:read")
        resp = service.execute(_req(AgentRuntimeApiOperation.RUNTIME_HEALTH), ctx)
        assert resp.data.status == "degraded"
        assert resp.data.managers["goal"] == "unavailable"
        assert resp.data.event_bus == "unavailable"
        assert resp.data.trace_service == "unavailable"

    def test_timestamp_timezone_aware(self) -> None:
        resp = RuntimeSystemApiAdapter().health(
            _req(AgentRuntimeApiOperation.RUNTIME_HEALTH), _ctx()
        )
        assert datetime.fromisoformat(resp.data.timestamp).tzinfo is not None


class TestApiIntegration:
    """H. End-to-end service wiring: events, audit, batch, idempotency."""

    def test_goal_create_emits_goal_created(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write", "event:read")
        service.execute(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            ctx,
        )
        events = service.execute(_req(AgentRuntimeApiOperation.EVENT_LIST), ctx)
        assert EventType.GOAL_CREATED in [e.event_type for e in events.data["events"]]

    def test_run_start_emits_agent_run_started(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write", "run:write", "event:read")
        goal = service.execute(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            ctx,
        )
        service.execute(
            _req(AgentRuntimeApiOperation.RUN_START, {"goal_id": goal.data.goal_id}),
            ctx,
        )
        events = service.execute(_req(AgentRuntimeApiOperation.EVENT_LIST), ctx)
        assert EventType.AGENT_RUN_STARTED in [
            e.event_type for e in events.data["events"]
        ]

    def test_approval_approve_emits_approval_approved(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "approval:write", "event:read")
        approval = service.approval_adapter.request_approval(requirement={"kind": "x"})
        service.execute(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": approval.approval_id},
            ),
            ctx,
        )
        events = service.execute(_req(AgentRuntimeApiOperation.EVENT_LIST), ctx)
        assert EventType.APPROVAL_APPROVED in [
            e.event_type for e in events.data["events"]
        ]

    def test_budget_reserve_emits_budget_reserved(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "budget:write", "event:read")
        service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 5},
            ),
            ctx,
        )
        events = service.execute(_req(AgentRuntimeApiOperation.EVENT_LIST), ctx)
        assert EventType.BUDGET_RESERVED in [
            e.event_type for e in events.data["events"]
        ]

    def test_response_contains_request_id(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write")
        req = _req(
            AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
        )
        resp = service.execute(req, ctx)
        assert resp.request_id == req.request_id

    def test_audit_contains_actor_and_operation(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write")
        service.execute(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            ctx,
        )
        audit_mw = next(
            m for m in service.router._middleware if isinstance(m, AuditMiddleware)
        )
        entry = audit_mw.audit_log[-1]
        assert entry["actor"] == "alice"
        assert entry["operation"] == "goal.create"

    def test_audit_no_contiene_secretos(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write")
        service.execute(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE,
                {"title": "Rotate credentials", "objective": "O"},
            ),
            ctx,
        )
        audit_mw = next(
            m for m in service.router._middleware if isinstance(m, AuditMiddleware)
        )
        entry = audit_mw.audit_log[-1]
        assert set(entry.keys()) == {
            "request_id",
            "actor",
            "operation",
            "resource",
            "status",
            "timestamp",
            "error_codes",
        }
        assert "Rotate credentials" not in str(entry.values())

    def test_batch_conserva_orden(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write")
        requests = [
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE,
                {"title": f"T{i}", "objective": "O"},
            )
            for i in range(5)
        ]
        responses = service.execute_many(requests, ctx)
        assert [r.data.title for r in responses] == ["T0", "T1", "T2", "T3", "T4"]

    def test_fallo_aislado_en_batch(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write")
        requests = [
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "ok", "objective": "O"}
            ),
            _req(AgentRuntimeApiOperation.GOAL_CREATE, {"title": "", "objective": "O"}),
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "ok2", "objective": "O"}
            ),
        ]
        responses = service.execute_many(requests, ctx)
        assert responses[0].status == AgentRuntimeApiStatus.SUCCESS
        assert responses[1].status == AgentRuntimeApiStatus.ERROR
        assert responses[2].status == AgentRuntimeApiStatus.SUCCESS

    def test_idempotencia_evita_doble_ejecucion(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write", "goal:read")
        payload = {"title": "T", "objective": "O"}
        req1 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.GOAL_CREATE,
            payload=payload,
            idempotency_key="idem-1",
        )
        req2 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.GOAL_CREATE,
            payload=payload,
            idempotency_key="idem-1",
        )
        resp1 = service.execute(req1, ctx)
        resp2 = service.execute(req2, ctx)
        assert resp1.data.goal_id == resp2.data.goal_id
        listing = service.execute(_req(AgentRuntimeApiOperation.GOAL_LIST), ctx)
        assert listing.data["total"] == 1


# ═════════════════════════════════════════════════════════════════════════
# Block 3: full-service flows (permissions + idempotency + audit + redaction
# actually exercised, not just the bare adapter) and cross-cutting security
# ═════════════════════════════════════════════════════════════════════════


class TestApprovalServiceFlow:
    """Approval scenarios driven through AgentRuntimeApiService."""

    def test_list_pending(self) -> None:
        service = AgentRuntimeApiService()
        service.approval_adapter.request_approval(requirement={"kind": "x"})
        resp = service.execute(
            _req(AgentRuntimeApiOperation.APPROVAL_LIST), _ctx("alice", "approval:read")
        )
        assert resp.data["total"] == 1

    def test_get_existing(self) -> None:
        service = AgentRuntimeApiService()
        created = service.approval_adapter.request_approval(requirement={"kind": "x"})
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.APPROVAL_GET,
                {"approval_id": created.approval_id},
            ),
            _ctx("alice", "approval:read"),
        )
        assert resp.status == AgentRuntimeApiStatus.SUCCESS
        assert resp.data.approval_id == created.approval_id

    def test_get_missing(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(AgentRuntimeApiOperation.APPROVAL_GET, {"approval_id": "missing"}),
            _ctx("alice", "approval:read"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "NOT_FOUND"

    def test_approve_pending(self) -> None:
        service = AgentRuntimeApiService()
        created = service.approval_adapter.request_approval(requirement={"kind": "x"})
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": created.approval_id},
            ),
            _ctx("alice", "approval:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.SUCCESS
        assert resp.data.status == "approved"

    def test_reject_pending(self) -> None:
        service = AgentRuntimeApiService()
        created = service.approval_adapter.request_approval(requirement={"kind": "x"})
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.APPROVAL_REJECT,
                {"approval_id": created.approval_id, "reason": "no"},
            ),
            _ctx("alice", "approval:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.SUCCESS
        assert resp.data.status == "rejected"

    def test_expired_request_rejected(self) -> None:
        service = AgentRuntimeApiService()
        created = service.approval_adapter.request_approval(
            requirement={"kind": "x"}, expires_at="2000-01-01T00:00:00+00:00"
        )
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": created.approval_id},
            ),
            _ctx("alice", "approval:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "STATE_ERROR"

    def test_duplicate_decision_rejected(self) -> None:
        service = AgentRuntimeApiService()
        created = service.approval_adapter.request_approval(requirement={"kind": "x"})
        ctx = _ctx("alice", "approval:write")
        service.execute(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": created.approval_id},
            ),
            ctx,
        )
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.APPROVAL_REJECT,
                {"approval_id": created.approval_id},
            ),
            ctx,
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "CONFLICT"

    def test_unauthorized_actor_rejected(self) -> None:
        # Distinct from PermissionMiddleware's coarse "approval:write" check:
        # alice HAS the API permission, but the approval is assigned to bob,
        # so the adapter's own resource-level authorization must still deny it.
        service = AgentRuntimeApiService()
        created = service.approval_adapter.request_approval(
            requirement={"kind": "x"}, assigned_to="bob"
        )
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.APPROVAL_APPROVE,
                {"approval_id": created.approval_id},
            ),
            _ctx("alice", "approval:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "PERMISSION_DENIED"


class TestBudgetServiceFlow:
    """Budget scenarios driven through AgentRuntimeApiService."""

    def test_get(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(AgentRuntimeApiOperation.BUDGET_GET, {"budget_id": "b1"}),
            _ctx("alice", "budget:read"),
        )
        assert resp.data.budget_id == "b1"

    def test_reserve(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 10},
            ),
            _ctx("alice", "budget:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.SUCCESS
        assert resp.data.reserved == 10.0

    def test_release(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "budget:write")
        reserved = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 10},
            ),
            ctx,
        )
        rid = reserved.data.reservation["reservation_id"]
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RELEASE,
                {"budget_id": "b1", "reservation_id": rid, "amount": 10},
            ),
            ctx,
        )
        assert resp.status == AgentRuntimeApiStatus.SUCCESS
        assert resp.data.reserved == 0.0

    def test_zero_amount_rejected(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 0},
            ),
            _ctx("alice", "budget:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "VALIDATION_ERROR"

    def test_negative_amount_rejected(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": -5},
            ),
            _ctx("alice", "budget:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "VALIDATION_ERROR"

    def test_exceeded_rejected(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 1000},
            ),
            _ctx("alice", "budget:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "BUDGET_EXCEEDED"

    def test_over_release_rejected(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "budget:write")
        reserved = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 10},
            ),
            ctx,
        )
        rid = reserved.data.reservation["reservation_id"]
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RELEASE,
                {"budget_id": "b1", "reservation_id": rid, "amount": 20},
            ),
            ctx,
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "VALIDATION_ERROR"

    def test_reservation_id_traceable(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "budget:write")
        reserved = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 10, "reservation_id": "trace-me"},
            ),
            ctx,
        )
        assert reserved.data.reservation["reservation_id"] == "trace-me"
        released = service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RELEASE,
                {"budget_id": "b1", "reservation_id": "trace-me", "amount": 10},
            ),
            ctx,
        )
        assert released.data.reservation["reservation_id"] == "trace-me"


class TestTraceServiceFlow:
    """Trace scenarios driven through AgentRuntimeApiService."""

    def test_get(self) -> None:
        service = AgentRuntimeApiService()
        created = service.trace_adapter.create_trace(run_id="run-1")
        resp = service.execute(
            _req(AgentRuntimeApiOperation.TRACE_GET, {"trace_id": created.trace_id}),
            _ctx("alice", "trace:read"),
        )
        assert resp.data.trace_id == created.trace_id

    def test_list(self) -> None:
        service = AgentRuntimeApiService()
        service.trace_adapter.create_trace()
        service.trace_adapter.create_trace()
        resp = service.execute(
            _req(AgentRuntimeApiOperation.TRACE_LIST), _ctx("alice", "trace:read")
        )
        assert resp.data["total"] == 2

    def test_verify_valid_chain(self) -> None:
        service = AgentRuntimeApiService()
        created = service.trace_adapter.create_trace()
        service.trace_adapter.append_record(created.trace_id, {"step": 1})
        service.trace_adapter.append_record(created.trace_id, {"step": 2})
        resp = service.execute(
            _req(AgentRuntimeApiOperation.TRACE_VERIFY, {"trace_id": created.trace_id}),
            _ctx("alice", "trace:read"),
        )
        assert resp.data.integrity_status == "verified"

    def test_verify_corrupted_chain(self) -> None:
        service = AgentRuntimeApiService()
        created = service.trace_adapter.create_trace()
        service.trace_adapter.append_record(created.trace_id, {"step": 1})
        service.trace_adapter.append_record(created.trace_id, {"step": 2})
        service.trace_adapter._traces[created.trace_id]["records"][1]["data"] = {
            "step": 999
        }
        resp = service.execute(
            _req(AgentRuntimeApiOperation.TRACE_VERIFY, {"trace_id": created.trace_id}),
            _ctx("alice", "trace:read"),
        )
        assert resp.data.integrity_status == "tampered"

    def test_export_json(self) -> None:
        service = AgentRuntimeApiService()
        created = service.trace_adapter.create_trace()
        service.trace_adapter.append_record(created.trace_id, {"step": 1})
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.TRACE_EXPORT,
                {"trace_id": created.trace_id, "format": "JSON"},
            ),
            _ctx("alice", "trace:read", "trace:export"),
        )
        assert resp.data.export_format == "JSON"
        assert isinstance(resp.data.export_data, str)

    def test_export_jsonl(self) -> None:
        service = AgentRuntimeApiService()
        created = service.trace_adapter.create_trace()
        service.trace_adapter.append_record(created.trace_id, {"step": 1})
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.TRACE_EXPORT,
                {"trace_id": created.trace_id, "format": "JSONL"},
            ),
            _ctx("alice", "trace:read", "trace:export"),
        )
        assert resp.data.export_format == "JSONL"

    def test_export_summary(self) -> None:
        service = AgentRuntimeApiService()
        created = service.trace_adapter.create_trace()
        service.trace_adapter.append_record(created.trace_id, {"step": 1})
        service.trace_adapter.append_record(created.trace_id, {"step": 2})
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.TRACE_EXPORT,
                {"trace_id": created.trace_id, "format": "SUMMARY"},
            ),
            _ctx("alice", "trace:read", "trace:export"),
        )
        assert resp.data.export_data["summary"] == "2 records"

    def test_exported_content_redacts_nested_chain_of_thought(self) -> None:
        service = AgentRuntimeApiService()
        created = service.trace_adapter.create_trace()
        service.trace_adapter.append_record(
            created.trace_id,
            {"details": {"reasoning": {"chain_of_thought": "deep secret reasoning"}}},
        )
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.TRACE_EXPORT,
                {"trace_id": created.trace_id, "format": "JSON"},
            ),
            _ctx("alice", "trace:read", "trace:export"),
        )
        assert "deep secret reasoning" not in resp.data.export_data
        assert "**REDACTED**" in resp.data.export_data


class TestRuntimeEventServiceFlow:
    """Runtime event scenarios driven through AgentRuntimeApiService."""

    def test_publish_registered_event(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_UPDATED},
            ),
            _ctx("alice", "event:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.SUCCESS
        assert resp.data.event_type == EventType.GOAL_UPDATED

    def test_reject_unknown_event(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(AgentRuntimeApiOperation.EVENT_PUBLISH, {"event_type": "bogus.event"}),
            _ctx("alice", "event:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "VALIDATION_ERROR"

    def test_reject_duplicate_event_via_dedup_key(self) -> None:
        # Event ids are always server-assigned (never client-supplied), so
        # they can never collide; the real duplicate-detection mechanism is
        # the client-supplied dedup_key, exercised here end-to-end.
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "event:write", "event:read")
        payload = {"event_type": EventType.GOAL_UPDATED, "dedup_key": "same-op"}
        first = service.execute(
            _req(AgentRuntimeApiOperation.EVENT_PUBLISH, payload), ctx
        )
        second = service.execute(
            _req(AgentRuntimeApiOperation.EVENT_PUBLISH, payload), ctx
        )
        assert first.data.event_id == second.data.event_id
        listed = service.execute(_req(AgentRuntimeApiOperation.EVENT_LIST), ctx)
        assert listed.data["total"] == 1

    def test_reject_unsafe_payload(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_UPDATED, "note": "bearer sometoken"},
            ),
            _ctx("alice", "event:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "VALIDATION_ERROR"

    def test_list_chronological(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "event:write", "event:read")
        service.execute(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            ctx,
        )
        service.execute(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_UPDATED},
            ),
            ctx,
        )
        service.execute(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_PAUSED},
            ),
            ctx,
        )
        resp = service.execute(_req(AgentRuntimeApiOperation.EVENT_LIST), ctx)
        types = [e.event_type for e in resp.data["events"]]
        assert types == [
            EventType.GOAL_CREATED,
            EventType.GOAL_UPDATED,
            EventType.GOAL_PAUSED,
        ]

    def test_replay_preserves_original_event_id(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "event:write", "event:read")
        published = service.execute(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            ctx,
        )
        resp = service.execute(_req(AgentRuntimeApiOperation.EVENT_REPLAY), ctx)
        assert resp.data["events"][0].original_event_id == published.data.event_id

    def test_dead_letter_missing_rejected(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.DEAD_LETTER_REPLAY,
                {"dead_letter_id": "missing"},
            ),
            _ctx("alice", "event:write"),
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "NOT_FOUND"

    def test_no_fake_delivered_status(self) -> None:
        service = AgentRuntimeApiService()
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.EVENT_PUBLISH,
                {"event_type": EventType.GOAL_CREATED},
            ),
            _ctx("alice", "event:write"),
        )
        assert resp.data.delivery["status"] == "recorded"


class TestApiIntegrationSecurity:
    """Cross-cutting integration/security guarantees across resource types."""

    def test_mutable_operation_emits_correct_event(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write", "run:write", "event:read")
        goal_to_cancel = service.execute(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            ctx,
        )
        service.execute(
            _req(
                AgentRuntimeApiOperation.GOAL_CANCEL,
                {"goal_id": goal_to_cancel.data.goal_id},
            ),
            ctx,
        )
        goal_for_run = service.execute(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T2", "objective": "O"}
            ),
            ctx,
        )
        run = service.execute(
            _req(
                AgentRuntimeApiOperation.RUN_START,
                {"goal_id": goal_for_run.data.goal_id},
            ),
            ctx,
        )
        service.execute(
            _req(AgentRuntimeApiOperation.RUN_PAUSE, {"run_id": run.data.run_id}), ctx
        )
        events = service.execute(_req(AgentRuntimeApiOperation.EVENT_LIST), ctx)
        types = [e.event_type for e in events.data["events"]]
        assert EventType.GOAL_CREATED in types
        assert EventType.GOAL_CANCELLED in types
        assert EventType.AGENT_RUN_STARTED in types
        assert EventType.AGENT_RUN_PAUSED in types

    def test_request_id_always_returned(self) -> None:
        service = AgentRuntimeApiService()
        for op, payload, ctx in (
            (
                AgentRuntimeApiOperation.GOAL_CREATE,
                {"title": "T", "objective": "O"},
                _ctx("alice", "goal:write"),
            ),
            (
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 1},
                _ctx("alice", "budget:write"),
            ),
            (AgentRuntimeApiOperation.RUNTIME_HEALTH, {}, _ctx("alice", "system:read")),
        ):
            req = _req(op, payload)
            resp = service.execute(req, ctx)
            assert resp.request_id == req.request_id

    def test_audit_contains_actor_and_operation_for_error_response(self) -> None:
        service = AgentRuntimeApiService()
        service.execute(
            _req(AgentRuntimeApiOperation.GOAL_GET, {"goal_id": "missing"}),
            _ctx("alice", "goal:read"),
        )
        audit_mw = next(
            m for m in service.router._middleware if isinstance(m, AuditMiddleware)
        )
        entry = audit_mw.audit_log[-1]
        assert entry["actor"] == "alice"
        assert entry["operation"] == "goal.get"
        assert entry["status"] == "error"
        assert entry["error_codes"] == ["NOT_FOUND"]

    def test_audit_excludes_secret_fields_across_operations(self) -> None:
        service = AgentRuntimeApiService()
        service.approval_adapter.request_approval(requirement={"kind": "x"})
        ctx = _ctx("alice", "budget:write", "approval:write")
        service.execute(
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "super-secret-budget-name", "amount": 5},
            ),
            ctx,
        )
        audit_mw = next(
            m for m in service.router._middleware if isinstance(m, AuditMiddleware)
        )
        for entry in audit_mw.audit_log:
            assert "super-secret-budget-name" not in str(entry.values())

    def test_idempotency_prevents_double_execution(self) -> None:
        service = AgentRuntimeApiService()
        created = service.approval_adapter.request_approval(requirement={"kind": "x"})
        ctx = _ctx("alice", "approval:write")
        payload = {"approval_id": created.approval_id}
        req1 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.APPROVAL_APPROVE,
            payload=payload,
            idempotency_key="approve-once",
        )
        req2 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.APPROVAL_APPROVE,
            payload=payload,
            idempotency_key="approve-once",
        )
        resp1 = service.execute(req1, ctx)
        resp2 = service.execute(req2, ctx)
        assert resp1.data.status == resp2.data.status == "approved"
        assert resp1.data.resolved_at == resp2.data.resolved_at

    def test_same_key_different_payload_conflicts(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write")
        req1 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.GOAL_CREATE,
            payload={"title": "A", "objective": "O"},
            idempotency_key="dup-key",
        )
        req2 = AgentRuntimeApiRequest(
            operation=AgentRuntimeApiOperation.GOAL_CREATE,
            payload={"title": "B", "objective": "O"},
            idempotency_key="dup-key",
        )
        resp1 = service.execute(req1, ctx)
        resp2 = service.execute(req2, ctx)
        assert resp1.status == AgentRuntimeApiStatus.SUCCESS
        assert resp2.status == AgentRuntimeApiStatus.ERROR
        assert resp2.errors[0].code == "IDEMPOTENCY_CONFLICT"

    def test_internal_exception_text_never_exposed(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write")

        def boom(
            request: AgentRuntimeApiRequest, context: AgentRuntimeApiContext
        ) -> AgentRuntimeApiResponse:
            raise RuntimeError("db password=hunter2 leaked in stack trace")

        service.router.unregister(AgentRuntimeApiOperation.GOAL_CREATE)
        service.router.register(AgentRuntimeApiOperation.GOAL_CREATE, boom)
        resp = service.execute(
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "T", "objective": "O"}
            ),
            ctx,
        )
        assert resp.status == AgentRuntimeApiStatus.ERROR
        assert resp.errors[0].code == "INTERNAL_ERROR"
        assert "hunter2" not in resp.errors[0].message
        assert "password" not in resp.errors[0].message

    def test_execute_many_preserves_order_with_mixed_success_and_error(self) -> None:
        service = AgentRuntimeApiService()
        ctx = _ctx("alice", "goal:write", "budget:write")
        requests = [
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "A", "objective": "O"}
            ),
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": -5},
            ),
            _req(
                AgentRuntimeApiOperation.BUDGET_RESERVE,
                {"budget_id": "b1", "amount": 5},
            ),
            _req(AgentRuntimeApiOperation.GOAL_CREATE, {"title": "", "objective": "O"}),
            _req(
                AgentRuntimeApiOperation.GOAL_CREATE, {"title": "B", "objective": "O"}
            ),
        ]
        responses = service.execute_many(requests, ctx)
        assert [r.status for r in responses] == [
            AgentRuntimeApiStatus.SUCCESS,
            AgentRuntimeApiStatus.ERROR,
            AgentRuntimeApiStatus.SUCCESS,
            AgentRuntimeApiStatus.ERROR,
            AgentRuntimeApiStatus.SUCCESS,
        ]
        assert responses[0].data.title == "A"
        assert responses[4].data.title == "B"
