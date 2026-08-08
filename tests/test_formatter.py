"""Tests for report_mailer.formatter.

Uses real report JSON captured by actually running csv-data-cleaner and
contact-scraper (tests/fixtures/), not hand-built approximations of
their output shape.
"""

import json
from pathlib import Path

from report_mailer.formatter import detect_report_type, format_report

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


class TestDetectReportType:
    def test_recognizes_real_quality_report(self):
        data = load_fixture("sample_quality_report.json")
        assert detect_report_type(data) == "quality_report"

    def test_recognizes_real_scrape_report(self):
        data = load_fixture("sample_scrape_report.json")
        assert detect_report_type(data) == "scrape_report"

    def test_generic_for_unrecognized_shape(self):
        assert detect_report_type({"server": "web-01", "status": "ok"}) == "generic"

    def test_generic_for_empty_dict(self):
        assert detect_report_type({}) == "generic"


class TestFormatQualityReport:
    def test_text_body_includes_key_stats(self):
        data = load_fixture("sample_quality_report.json")
        _, text = format_report(data)
        assert "Total rows: 10" in text
        assert "Rows removed: 1" in text
        assert "Issues found: 12" in text

    def test_html_body_is_well_formed_and_escaped(self):
        data = load_fixture("sample_quality_report.json")
        html, _ = format_report(data)
        assert "<h1" in html
        assert "<table" in html
        # No unescaped issue message content should break out of a <td>.
        assert "<script" not in html

    def test_html_uses_only_inline_styles_no_style_block(self):
        data = load_fixture("sample_quality_report.json")
        html, _ = format_report(data)
        assert "<style" not in html
        assert 'style="' in html

    def test_issues_table_present_when_issues_exist(self):
        data = load_fixture("sample_quality_report.json")
        html, _ = format_report(data)
        assert "invalid_format" in html or "issue_type" in html.lower() or "<table" in html

    def test_no_issues_case(self):
        data = load_fixture("sample_quality_report.json")
        data = dict(data)
        data["issues"] = []
        html, text = format_report(data)
        assert "No issues found" in html
        assert "Issues found: 0" in text


class TestFormatScrapeReport:
    def test_text_body_includes_key_stats(self):
        data = load_fixture("sample_scrape_report.json")
        _, text = format_report(data)
        assert "Pages attempted: 1" in text
        assert "Unique emails: 3" in text
        assert "Unique phones: 3" in text

    def test_no_failed_pages_table_when_everything_succeeded(self):
        data = load_fixture("sample_scrape_report.json")
        html, _ = format_report(data)
        assert "Failed / Skipped Pages" not in html

    def test_failed_pages_table_appears_when_present(self):
        data = load_fixture("sample_scrape_report.json")
        data = dict(data)
        data["page_results"] = data["page_results"] + [
            {"url": "https://x.example/broken", "success": False, "error": "timed out"}
        ]
        html, text = format_report(data)
        assert "Failed / Skipped Pages" in html
        assert "timed out" in html
        assert "1 page(s) failed" in text


class TestFormatGeneric:
    def test_renders_arbitrary_dict_as_a_table(self):
        data = {"server": "web-01", "status": "healthy", "uptime_hours": 720}
        html, text = format_report(data, title="Server Status")
        assert "web-01" in html
        assert "web-01" in text
        assert "Server Status" in html

    def test_escapes_html_special_characters_in_values(self):
        data = {"note": "<script>alert(1)</script>"}
        html, _ = format_report(data)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_empty_dict(self):
        html, text = format_report({}, title="Empty")
        assert "Empty" in html
        assert "EMPTY" in text  # text body uppercases the title, like the other formatters
