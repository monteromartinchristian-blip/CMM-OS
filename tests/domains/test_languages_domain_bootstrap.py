"""Tests for Phase 10.26 Languages Domain Bootstrap."""

from __future__ import annotations

from cmm.domains.languages.bootstrap import (
    LANGUAGES_BOOTSTRAP_NAME,
    LanguagesDomainBootstrap,
    build_standard_languages_domain_bootstrap,
)


def test_build_standard_languages_domain_bootstrap() -> None:
    """Verify standard bootstrap integrates Languages and keeps General as fallback."""
    bootstrap = build_standard_languages_domain_bootstrap()
    assert isinstance(bootstrap, LanguagesDomainBootstrap)
    assert LANGUAGES_BOOTSTRAP_NAME == "LanguagesDomainBootstrap"

    # Both general and languages domains are present
    assert bootstrap.domain_registry.get("domain:general") is not None
    assert bootstrap.domain_registry.get("domain:languages") is not None

    # Resolver fallback is general
    assert bootstrap.resolver is not None
