"""Phase 10.22 — B7: Academic Integrity Mode C (permissive by default, grounded).

The audit found the previous implementation only preserved a stated mode string
and never reasoned about assistance restrictions.  Integrity Mode C must be
permissive by default: assistance is allowed when no applicable restriction is
grounded.  A caller cannot fabricate a prohibition by setting a bare boolean
without grounding.  A remembered prohibition is not automatically equivalent to
a current official one.  When an explicit, sufficiently grounded restriction
exists, the domain respects its concrete scope and preserves source and
temporal validity.
"""

from __future__ import annotations

from cmm.domains.university.rules import evaluate_academic_integrity


def test_mode_c_permissive_by_default_when_no_restriction():
    """No applicable restriction grounded -> assistance allowed by default."""
    result = evaluate_academic_integrity(mode="mode_c")
    assert result["mode"] == "mode_c"
    assert result["assistance_permitted"] is True
    assert result["restriction"] is None
    assert result["restriction_grounded"] is False


def test_mode_c_defaults_to_permissive_when_mode_omitted():
    result = evaluate_academic_integrity()
    assert result["mode"] == "mode_c"
    assert result["assistance_permitted"] is True


def test_ai_forbidden_without_grounding_cannot_fabricate_prohibition():
    """A caller setting ``ai_forbidden=True`` with no grounding cannot create a
    prohibition; Mode C remains permissive."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        caller_restriction={"ai_forbidden": True},
    )
    assert result["assistance_permitted"] is True
    assert result["restriction_grounded"] is False
    assert result["caller_forbidden_ignored"] is True


def test_grounded_restriction_respected_within_scope():
    """An explicit, sufficiently grounded restriction is respected; assistance
    remains permitted within the allowed scope."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        grounded_restriction={
            "status": "prohibited",
            "grounded": True,
            "scope": ("final_exam_essay",),
            "source_class": "official_regulation",
            "temporal": "current",
        },
    )
    assert result["assistance_permitted"] is False
    assert result["restriction_grounded"] is True
    assert result["restriction_scope"] == ("final_exam_essay",)


def test_remembered_restriction_not_current_official():
    """A remembered prohibition is not automatically equivalent to a current
    official one; it does not restrict assistance."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        grounded_restriction={
            "status": "prohibited",
            "grounded": True,
            "source_class": "remembered",
            "temporal": "past",
        },
        remembered_restriction=True,
    )
    assert result["assistance_permitted"] is True
    assert result["restriction_grounded"] is False
    assert result["remembered_not_official"] is True


def test_ungrounded_restriction_does_not_restrict():
    """A restriction with no grounding does not restrict assistance."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        grounded_restriction={
            "status": "prohibited",
            "grounded": False,
        },
    )
    assert result["assistance_permitted"] is True
    assert result["restriction_grounded"] is False


def test_unknown_mode_not_permissive():
    """An unknown integrity mode is rejected, not silently treated as Mode C."""
    result = evaluate_academic_integrity(mode="mode_x")
    assert result["mode_valid"] is False
    assert result["assistance_permitted"] is False