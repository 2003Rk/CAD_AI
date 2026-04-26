"""Tests for prompt patterns."""

from src.prompts.patterns import get_pattern, get_all_patterns, ALL_PATTERNS


class TestPromptPatterns:
    def test_three_patterns_exist(self):
        assert len(ALL_PATTERNS) == 3

    def test_get_pattern_by_id(self):
        for pid in (1, 2, 3):
            p = get_pattern(pid)
            assert p.id == pid
            assert p.name
            assert p.system_prompt
            assert p.user_prompt_template

    def test_format_user_prompt(self):
        p = get_pattern(1)
        text = p.format_user_prompt("a steel bracket")
        assert "a steel bracket" in text

    def test_all_patterns_returns_list(self):
        patterns = get_all_patterns()
        assert len(patterns) == 3
        assert all(p.id in (1, 2, 3) for p in patterns)
