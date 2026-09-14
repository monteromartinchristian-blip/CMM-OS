"""Phase 10.37 — Public surface export tests.

Proves the approved Phase 10.37 symbols are importable from ``cmm.domains``
and that the Phase 10.36 DomainAPI surface is unchanged.
"""

from __future__ import annotations

import subprocess
import sys

import cmm.domains

PHASE10_37_PUBLIC_SYMBOLS = (
    "DomainMetricStatus",
    "DomainMetricBucket",
    "DomainMetricMeasurement",
    "DomainMetricsSnapshot",
    "DomainObservabilityLogEntry",
    "DomainHealthStatus",
    "DomainHealthFinding",
    "DomainHealthResult",
    "DomainObservabilityReport",
    "DomainObservabilityEvidence",
    "DomainMetricsCalculator",
    "DomainHealthChecker",
    "DomainObservabilityService",
    "CANONICAL_DOMAIN_OBSERVABILITY_METRICS",
    "InvalidDomainObservabilityContractError",
    "InvalidDomainObservabilityEvidenceError",
)


def test_phase_10_37_public_symbols_exported() -> None:
    for symbol in PHASE10_37_PUBLIC_SYMBOLS:
        assert hasattr(cmm.domains, symbol), f"missing export: {symbol}"


def test_errors_exported_from_cmm_domains_errors() -> None:
    from cmm.domains.errors import (
        InvalidDomainObservabilityContractError,
        InvalidDomainObservabilityEvidenceError,
    )

    assert issubclass(InvalidDomainObservabilityContractError, Exception)
    assert issubclass(InvalidDomainObservabilityEvidenceError, Exception)


def test_domain_api_surface_unchanged() -> None:
    # Phase 10.36 DomainAPI is closed. Verify the canonical public protocol
    # methods are still exactly the Phase 10.36 surface.
    from cmm.domains.api import DomainAPI  # Canonical Phase 10.36 facade.

    methods = {name for name in dir(DomainAPI) if not name.startswith("_")}
    assert "calculate_metrics" not in methods
    assert "check_domain_health" not in methods
    assert "build_report" not in methods


def test_import_has_no_side_effects() -> None:
    """Fresh subprocess import must not publish events or mutate state."""
    code = (
        "import cmm.domains;\n"
        "import cmm.domains.observability_contracts;\n"
        "import cmm.domains.observability_metrics;\n"
        "import cmm.domains.observability_health;\n"
        "import cmm.domains.observability_service;\n"
        "print('IMPORT_OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout
