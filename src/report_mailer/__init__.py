"""report-mailer: format and email the reports your other tools produce.

Turns the JSON output of ``csv-data-cleaner`` (a ``DataQualityReport``)
or ``contact-scraper`` (a ``ScrapeReport``) -- or any generic JSON
object -- into an HTML summary email with a plain-text fallback and the
raw report attached, then sends it over SMTP.

Public API:
    ReportMailer: The main entry point -- send an
        :class:`EmailMessage` over SMTP.
    format_report: Turn report JSON into ``(html_body, text_body)``.
    detect_report_type: Identify which sibling project produced a given
        report dict (``"quality_report"``, ``"scrape_report"``, or
        ``"generic"``).
    EmailMessage: A fully-composed email, ready for ``ReportMailer``.
    EmailAttachment: A single file attached to an ``EmailMessage``.
    EmailSendResult: The outcome of a send attempt.
    ReportMailerError: Raised for unrecoverable errors (bad
        configuration or wrong argument types) as distinct from a
        merely failed send, which is never an exception -- see its
        docstring.

This package intentionally has no scheduler of its own -- for recurring
reports, invoke its CLI from cron (Linux/macOS) or Task Scheduler
(Windows); see the README.

Example:
    >>> from report_mailer import format_report
    >>> html, text = format_report({"server": "web-01", "status": "ok"})
    >>> "web-01" in text
    True
"""

from .formatter import detect_report_type, format_report
from .mailer import ReportMailer
from .models import EmailAttachment, EmailMessage, EmailSendResult, ReportMailerError

__version__ = "1.0.0"

__all__ = [
    "EmailAttachment",
    "EmailMessage",
    "EmailSendResult",
    "ReportMailer",
    "ReportMailerError",
    "__version__",
    "detect_report_type",
    "format_report",
]
