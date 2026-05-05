"""Tests for the security layer."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pyservicelab.core.errors import SecurityError
from pyservicelab.security.checks import (
    assert_no_sql_injection,
    assert_no_xss,
    assert_safe_path,
    has_path_traversal,
    has_sql_injection,
    has_xss,
    sanitize_and_check,
)
from pyservicelab.security.safe_paths import (
    has_traversal_attempt,
    is_safe_path,
    normalize_path,
    safe_join,
)
from pyservicelab.security.sanitization import (
    sanitize_filename,
    sanitize_html,
    sanitize_sql_like,
    sanitize_string,
)
from pyservicelab.security.secrets import (
    constant_time_compare,
    generate_api_key,
    generate_otp,
    generate_secret,
    generate_slug_token,
    is_strong_secret,
)


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------


class TestSanitizeString:
    def test_strips_null_bytes(self) -> None:
        assert "\x00" not in sanitize_string("hello\x00world")

    def test_preserves_newlines(self) -> None:
        result = sanitize_string("line1\nline2")
        assert "\n" in result

    def test_truncates_to_max_length(self) -> None:
        long_str = "a" * 5000
        result = sanitize_string(long_str, max_length=100)
        assert len(result) == 100

    def test_preserves_normal_text(self) -> None:
        text = "Hello, World! 123"
        assert sanitize_string(text) == text


class TestSanitizeHtml:
    def test_removes_script_tags(self) -> None:
        result = sanitize_html("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "alert(1)" in result

    def test_removes_anchor_tags(self) -> None:
        result = sanitize_html('<a href="http://example.com">click</a>')
        assert "<a" not in result
        assert "click" in result

    def test_preserves_text(self) -> None:
        result = sanitize_html("Plain text without tags")
        assert result == "Plain text without tags"


class TestSanitizeFilename:
    def test_removes_path_separators(self) -> None:
        result = sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert ".." not in result

    def test_replaces_illegal_chars(self) -> None:
        result = sanitize_filename('file:*?"<>|.txt')
        assert "*" not in result
        assert "?" not in result

    def test_normal_name_unchanged(self) -> None:
        result = sanitize_filename("myfile.txt")
        assert "myfile" in result

    def test_empty_result_becomes_unnamed(self) -> None:
        result = sanitize_filename("...")
        assert result  # not empty


class TestSanitizeSqlLike:
    def test_escapes_percent(self) -> None:
        result = sanitize_sql_like("100%")
        assert "\\%" in result

    def test_escapes_underscore(self) -> None:
        result = sanitize_sql_like("user_name")
        assert "\\_" in result

    def test_preserves_normal_text(self) -> None:
        result = sanitize_sql_like("hello")
        assert result == "hello"


# ---------------------------------------------------------------------------
# Safe paths
# ---------------------------------------------------------------------------


class TestSafePaths:
    def test_safe_path_within_base(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            base_path = Path(base)
            target = base_path / "subdir" / "file.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            assert is_safe_path(base_path, target) is True

    def test_path_traversal_detected(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            base_path = Path(base)
            evil = base_path / ".." / "etc" / "passwd"
            assert is_safe_path(base_path, evil) is False

    def test_safe_join_valid(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            result = safe_join(base, "subdir", "file.txt")
            assert str(result).startswith(base)

    def test_safe_join_traversal_raises(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            with pytest.raises(ValueError, match="traversal"):
                safe_join(base, "../../etc/passwd")

    def test_has_traversal_attempt(self) -> None:
        assert has_traversal_attempt("../secret") is True
        assert has_traversal_attempt("normal/path") is False

    def test_normalize_path_raises_on_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            with pytest.raises(ValueError):
                normalize_path("../escape", base)


# ---------------------------------------------------------------------------
# Security checks
# ---------------------------------------------------------------------------


class TestSecurityChecks:
    def test_sql_injection_detected(self) -> None:
        assert has_sql_injection("'; DROP TABLE users; --") is True

    def test_sql_injection_union_select(self) -> None:
        assert has_sql_injection("' UNION SELECT * FROM users --") is True

    def test_normal_text_no_sql_injection(self) -> None:
        assert has_sql_injection("Hello, world!") is False

    def test_xss_script_tag(self) -> None:
        assert has_xss("<script>alert('xss')</script>") is True

    def test_xss_javascript_protocol(self) -> None:
        assert has_xss("javascript:alert(1)") is True

    def test_normal_text_no_xss(self) -> None:
        assert has_xss("Hello, world!") is False

    def test_path_traversal_dotdot(self) -> None:
        assert has_path_traversal("../../etc/passwd") is True

    def test_path_traversal_normal(self) -> None:
        assert has_path_traversal("/home/user/file.txt") is False

    def test_assert_no_sql_injection_passes(self) -> None:
        assert_no_sql_injection("Safe input text")

    def test_assert_no_sql_injection_raises(self) -> None:
        with pytest.raises(SecurityError):
            assert_no_sql_injection("'; DROP TABLE users; --")

    def test_assert_no_xss_raises(self) -> None:
        with pytest.raises(SecurityError):
            assert_no_xss("<script>evil()</script>")

    def test_assert_safe_path_raises(self) -> None:
        with pytest.raises(SecurityError):
            assert_safe_path("../../etc/passwd")

    def test_sanitize_and_check_clean_passes(self) -> None:
        result = sanitize_and_check("Normal user input")
        assert result == "Normal user input"

    def test_sanitize_and_check_sql_raises(self) -> None:
        with pytest.raises(SecurityError):
            sanitize_and_check("'; DROP TABLE users; --")


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------


class TestSecrets:
    def test_generate_secret_length(self) -> None:
        secret = generate_secret(16)
        assert len(secret) == 32  # hex → 2 chars per byte

    def test_generate_secret_unique(self) -> None:
        s1 = generate_secret()
        s2 = generate_secret()
        assert s1 != s2

    def test_generate_api_key_prefix(self) -> None:
        key = generate_api_key("myapp")
        assert key.startswith("myapp_")

    def test_generate_api_key_length(self) -> None:
        key = generate_api_key()
        # prefix "psl_" + 64 hex chars
        assert len(key) > 60

    def test_generate_otp_length(self) -> None:
        otp = generate_otp(6)
        assert len(otp) == 6
        assert otp.isdigit()

    def test_generate_slug_token(self) -> None:
        token = generate_slug_token(12)
        assert len(token) == 12
        assert token.isalnum()

    def test_constant_time_compare_equal(self) -> None:
        assert constant_time_compare("abc", "abc") is True

    def test_constant_time_compare_unequal(self) -> None:
        assert constant_time_compare("abc", "xyz") is False

    def test_is_strong_secret_passes(self) -> None:
        assert is_strong_secret("ABCabc123" + "x" * 25) is True

    def test_is_strong_secret_too_short(self) -> None:
        assert is_strong_secret("ABCabc123") is False

    def test_is_strong_secret_no_uppercase(self) -> None:
        assert is_strong_secret("abcabc123" + "x" * 25) is False
