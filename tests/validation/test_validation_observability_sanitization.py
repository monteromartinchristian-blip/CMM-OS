"""Unit tests for Phase 7.11 — sanitize_validation_data.

Covers:
- Sensitive keys (token, api_key, password, authorization, cookie, etc.)
- Nested mappings
- Lists and tuples
- URL-embedded credentials
- Original objects not mutated
- Non-sensitive keys preserved
- stdout/stderr containing secrets
"""

from __future__ import annotations

from cmm.validation.observability.sanitization import (
    REDACTED,
    sanitize_validation_data,
)

# ---------------------------------------------------------------------------
# Simple key redaction
# ---------------------------------------------------------------------------


def test_token_is_redacted() -> None:
    d = {"token": "abc123"}
    result = sanitize_validation_data(d)
    assert result["token"] == REDACTED


def test_api_key_is_redacted() -> None:
    d = {"api_key": "sk-secret"}
    result = sanitize_validation_data(d)
    assert result["api_key"] == REDACTED


def test_apikey_is_redacted() -> None:
    d = {"apiKey": "sk-secret"}
    result = sanitize_validation_data(d)
    assert result["apiKey"] == REDACTED


def test_password_is_redacted() -> None:
    d = {"password": "hunter2"}
    result = sanitize_validation_data(d)
    assert result["password"] == REDACTED


def test_passwd_is_redacted() -> None:
    d = {"passwd": "secret123"}
    result = sanitize_validation_data(d)
    assert result["passwd"] == REDACTED


def test_secret_is_redacted() -> None:
    d = {"secret": "top-secret-value"}
    result = sanitize_validation_data(d)
    assert result["secret"] == REDACTED


def test_authorization_is_redacted() -> None:
    d = {"authorization": "Bearer secret-token"}
    result = sanitize_validation_data(d)
    assert result["authorization"] == REDACTED


def test_cookie_is_redacted() -> None:
    d = {"cookie": "session=abc; token=xyz"}
    result = sanitize_validation_data(d)
    assert result["cookie"] == REDACTED


def test_credential_is_redacted() -> None:
    d = {"credential": "some-cred"}
    result = sanitize_validation_data(d)
    assert result["credential"] == REDACTED


def test_private_key_is_redacted() -> None:
    d = {"private_key": "-----BEGIN RSA PRIVATE KEY-----"}
    result = sanitize_validation_data(d)
    assert result["private_key"] == REDACTED


def test_access_key_is_redacted() -> None:
    d = {"access_key": "AKIAIOSFODNN7EXAMPLE"}
    result = sanitize_validation_data(d)
    assert result["access_key"] == REDACTED


def test_refresh_token_is_redacted() -> None:
    d = {"refresh_token": "refresh-abc"}
    result = sanitize_validation_data(d)
    assert result["refresh_token"] == REDACTED


# ---------------------------------------------------------------------------
# Case-insensitive matching
# ---------------------------------------------------------------------------


def test_case_insensitive_PASSWORD() -> None:
    d = {"PASSWORD": "secret"}
    result = sanitize_validation_data(d)
    assert result["PASSWORD"] == REDACTED


def test_case_insensitive_ApiKey() -> None:
    d = {"ApiKey": "val"}
    result = sanitize_validation_data(d)
    assert result["ApiKey"] == REDACTED


def test_partial_key_match() -> None:
    d = {"db_password_hash": "should-be-redacted"}
    result = sanitize_validation_data(d)
    assert result["db_password_hash"] == REDACTED


# ---------------------------------------------------------------------------
# Non-sensitive keys preserved
# ---------------------------------------------------------------------------


def test_non_sensitive_key_preserved() -> None:
    d = {"name": "Alice", "age": 30, "active": True}
    result = sanitize_validation_data(d)
    assert result["name"] == "Alice"
    assert result["age"] == 30
    assert result["active"] is True


def test_mixed_dict_partial_redaction() -> None:
    d = {
        "user": "christian",
        "token": "abc123",
        "retries": 3,
    }
    result = sanitize_validation_data(d)
    assert result["user"] == "christian"
    assert result["token"] == REDACTED
    assert result["retries"] == 3


# ---------------------------------------------------------------------------
# Nested structures
# ---------------------------------------------------------------------------


def test_nested_mapping_sensitive_key() -> None:
    d = {
        "config": {
            "host": "localhost",
            "password": "secret",
        }
    }
    result = sanitize_validation_data(d)
    assert result["config"]["host"] == "localhost"
    assert result["config"]["password"] == REDACTED


def test_deeply_nested_redaction() -> None:
    d = {"a": {"b": {"c": {"token": "deep-secret"}}}}
    result = sanitize_validation_data(d)
    assert result["a"]["b"]["c"]["token"] == REDACTED


def test_list_values_sanitized() -> None:
    d = {"items": [{"token": "abc"}, {"name": "ok"}]}
    result = sanitize_validation_data(d)
    assert result["items"][0]["token"] == REDACTED
    assert result["items"][1]["name"] == "ok"


def test_tuple_values_sanitized() -> None:
    t = ({"token": "abc"}, {"name": "ok"})
    result = sanitize_validation_data(t)
    assert result[0]["token"] == REDACTED
    assert result[1]["name"] == "ok"
    assert isinstance(result, tuple)


def test_list_of_strings_not_mutated() -> None:
    d = {"tags": ["python", "validation"]}
    result = sanitize_validation_data(d)
    assert result["tags"] == ["python", "validation"]


# ---------------------------------------------------------------------------
# URL-embedded credentials
# ---------------------------------------------------------------------------


def test_url_with_credentials_redacted() -> None:
    d = {"endpoint": "https://user:s3cr3t@example.com/api"}
    result = sanitize_validation_data(d)
    assert "s3cr3t" not in result["endpoint"]
    assert "https://" in result["endpoint"]
    assert REDACTED in result["endpoint"]


def test_url_without_credentials_preserved() -> None:
    d = {"endpoint": "https://example.com/api"}
    result = sanitize_validation_data(d)
    assert result["endpoint"] == "https://example.com/api"


def test_plain_string_without_secret_preserved() -> None:
    result = sanitize_validation_data("hello world")
    assert result == "hello world"


# ---------------------------------------------------------------------------
# stdout / stderr (strings)
# ---------------------------------------------------------------------------


def test_stdout_string_url_creds_redacted() -> None:
    stdout = "Connecting to https://user:hunter2@db.internal/path"
    result = sanitize_validation_data({"stdout": stdout})
    # stdout is not a sensitive key, but URL creds should still be stripped
    assert "hunter2" not in result["stdout"]


def test_stderr_with_sensitive_key_redacted() -> None:
    # When wrapped in a dict with key 'token', value is always redacted
    result = sanitize_validation_data({"token": "error: invalid token=abc"})
    assert result["token"] == REDACTED


# ---------------------------------------------------------------------------
# Original not mutated
# ---------------------------------------------------------------------------


def test_original_dict_not_mutated() -> None:
    original = {"token": "abc", "name": "test"}
    original_copy = dict(original)
    sanitize_validation_data(original)
    assert original == original_copy


def test_original_nested_not_mutated() -> None:
    original = {"a": {"token": "secret", "b": [1, 2, 3]}}
    original_a = dict(original["a"])
    sanitize_validation_data(original)
    assert original["a"] == original_a


# ---------------------------------------------------------------------------
# Scalars and edge cases
# ---------------------------------------------------------------------------


def test_none_passthrough() -> None:
    assert sanitize_validation_data(None) is None


def test_int_passthrough() -> None:
    assert sanitize_validation_data(42) == 42


def test_bool_passthrough() -> None:
    assert sanitize_validation_data(True) is True


def test_empty_dict() -> None:
    assert sanitize_validation_data({}) == {}


def test_empty_list() -> None:
    assert sanitize_validation_data([]) == []


def test_empty_string() -> None:
    assert sanitize_validation_data("") == ""


def test_sensitive_key_with_numeric_value() -> None:
    # Even non-string values associated with sensitive keys are redacted
    result = sanitize_validation_data({"token": 12345})
    assert result["token"] == REDACTED


def test_sensitive_key_with_none_value() -> None:
    result = sanitize_validation_data({"token": None})
    assert result["token"] == REDACTED
