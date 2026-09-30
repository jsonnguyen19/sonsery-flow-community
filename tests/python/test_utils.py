"""Tests for utility functions in runctx_core.py."""

import pytest

import runctx_core as core


class TestNormalizeOutput:
    def test_short_text_unchanged(self):
        assert core.normalize_output("abc", limit=100) == "abc"

    def test_truncate_keeps_last_n_chars(self):
        text = "a" * 500
        out = core.normalize_output(text, limit=100)
        assert "truncated" in out
        assert out.endswith("a" * 100)

    def test_exact_limit_unchanged(self):
        text = "x" * 100
        assert core.normalize_output(text, limit=100) == text


class TestStripCodeFence:
    def test_plain_text_unchanged(self):
        assert core.strip_code_fence("hello") == "hello"

    def test_json_fence_extracted(self):
        raw = '```json\n{"tool": "shell"}\n```'
        assert core.strip_code_fence(raw) == '{"tool": "shell"}'

    def test_fence_without_lang(self):
        raw = "```\nhello\n```"
        assert core.strip_code_fence(raw) == "hello"

    def test_runctx_result_marker_exits(self):
        with pytest.raises(SystemExit):
            core.strip_code_fence("RUNCTX_RESULT something")


class TestReadFileRange:
    def test_full_range(self, sample_file):
        out = core.read_file_range(sample_file, None, None)
        assert "1: line1" in out
        assert "5: line5" in out

    def test_sub_range(self, sample_file):
        out = core.read_file_range(sample_file, 2, 4)
        assert "2: line2" in out
        assert "4: line4" in out
        assert "1: line1" not in out
        assert "5: line5" not in out

    def test_start_after_end_returns_empty(self, sample_file):
        assert core.read_file_range(sample_file, 4, 2) == ""

    def test_end_beyond_eof_clamped(self, sample_file):
        out = core.read_file_range(sample_file, 3, 999)
        assert "3: line3" in out
        assert "5: line5" in out

    def test_start_negative_clamped_to_one(self, sample_file):
        out = core.read_file_range(sample_file, -5, 2)
        assert "1: line1" in out
        assert "2: line2" in out
