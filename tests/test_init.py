"""Tests for the report_mailer package's top-level public API."""

import report_mailer


def test_version_is_a_string():
    assert isinstance(report_mailer.__version__, str)


def test_all_declared_exports_are_actually_importable():
    for name in report_mailer.__all__:
        assert hasattr(report_mailer, name), f"{name} declared in __all__ but not exported"


def test_main_entry_point_is_exported():
    assert report_mailer.ReportMailer is not None
    assert report_mailer.format_report is not None
