"""
测试工具函数
"""
import pytest
from utils.helpers import (
    clean_text,
    extract_salary,
    parse_date,
    extract_tech_tags,
)


class TestCleanText:
    def test_remove_extra_spaces(self):
        text = "  Hello   World  "
        assert clean_text(text) == "Hello World"

    def test_remove_newlines(self):
        text = "Line1\nLine2\tTab"
        assert clean_text(text) == "Line1 Line2 Tab"

    def test_empty_string(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""


class TestExtractSalary:
    def test_range_with_k(self):
        result = extract_salary("10-20K")
        assert result == (10000.0, 20000.0)

    def test_range_with_wan(self):
        result = extract_salary("1-2万")
        assert result == (10000.0, 20000.0)

    def test_single_value(self):
        result = extract_salary("15k")
        assert result == (15000.0, 15000.0)

    def test_invalid(self):
        assert extract_salary("面议") == (None, None)
        assert extract_salary("") == (None, None)


class TestParseDate:
    def test_relative_time(self):
        from datetime import datetime
        result = parse_date("3天前")
        assert result is not None
        assert isinstance(result, datetime)

    def test_standard_format(self):
        result = parse_date("2024-01-15")
        assert result is not None
        assert result.year == 2024

    def test_invalid(self):
        assert parse_date("") is None


class TestExtractTechTags:
    def test_python_detection(self):
        text = "需要Python和Django开发经验"
        tags = extract_tech_tags(text)
        assert "Python" in tags

    def test_multiple_tags(self):
        text = "Java后端开发，使用Spring和MySQL"
        tags = extract_tech_tags(text)
        assert "Java" in tags
        assert "数据库" in tags

    def test_no_tags(self):
        text = "这是一段没有技术关键词的文本"
        tags = extract_tech_tags(text)
        assert len(tags) == 0
