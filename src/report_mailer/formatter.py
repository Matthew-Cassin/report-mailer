"""Turns report JSON into an email-ready HTML body plus a plain-text
fallback.

Recognizes the JSON shapes produced by two sibling projects --
``csv-data-cleaner``'s ``DataQualityReport`` and ``contact-scraper``'s
``ScrapeReport`` -- and falls back to a generic key/value or tabular
rendering for anything else. Pure functions, no I/O: given the same
input dict, always produces the same output.

Email HTML uses inline ``style="..."`` attributes throughout rather
than a ``<style>`` block or external stylesheet -- most mail clients
(Gmail and Outlook in particular) strip or ignore non-inline CSS, so
inline styling is the only reliable way to control an email's
appearance across clients.
"""

from __future__ import annotations

import html
from typing import Any

__all__ = ["detect_report_type", "format_report"]

_TABLE_STYLE = "border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:14px;"
_TH_STYLE = "text-align:left;padding:8px;background:#2c3e50;color:#fff;border:1px solid #ddd;"
_TD_STYLE = "padding:8px;border:1px solid #ddd;"
_H1_STYLE = "font-family:Arial,sans-serif;color:#2c3e50;"
_P_STYLE = "font-family:Arial,sans-serif;color:#333;"
_STAT_BOX_STYLE = (
    "display:inline-block;margin:6px 12px 6px 0;padding:10px 16px;"
    "background:#f4f6f7;border-left:4px solid #2c3e50;font-family:Arial,sans-serif;"
)


def detect_report_type(data: dict[str, Any]) -> str:
    """Identify which sibling project produced ``data``, if any.

    Returns:
        ``"quality_report"`` (csv-data-cleaner), ``"scrape_report"``
        (contact-scraper), or ``"generic"`` for anything else.
    """
    if "statistics" in data and "quality_score_before" in data.get("statistics", {}):
        return "quality_report"
    if "pages_attempted" in data and "page_results" in data:
        return "scrape_report"
    return "generic"


def format_report(data: dict[str, Any], title: str = "Report") -> tuple[str, str]:
    """Format ``data`` as an ``(html_body, text_body)`` pair.

    Auto-detects the report type via :func:`detect_report_type` and
    dispatches to the matching formatter, falling back to a generic
    rendering for unrecognized shapes.
    """
    report_type = detect_report_type(data)
    if report_type == "quality_report":
        return _format_quality_report(data)
    if report_type == "scrape_report":
        return _format_scrape_report(data)
    return _format_generic(data, title)


def _format_quality_report(data: dict[str, Any]) -> tuple[str, str]:
    stats = data.get("statistics", {})
    issues = data.get("issues", [])
    before = stats.get("quality_score_before", 0.0)
    after = stats.get("quality_score_after", 0.0)
    delta = after - before

    stat_items = [
        ("Total rows", stats.get("total_rows", "?")),
        ("Rows kept", stats.get("processed_rows", "?")),
        ("Rows removed", stats.get("rows_removed", "?")),
        ("Quality before", f"{before:.2f}"),
        ("Quality after", f"{after:.2f}"),
        ("Issues found", len(issues)),
    ]

    html_parts = [
        f'<h1 style="{_H1_STYLE}">CSV Data Quality Report</h1>',
        f'<p style="{_P_STYLE}">Generated {html.escape(str(data.get("timestamp", "")))}</p>',
        _stat_boxes_html(stat_items),
        (
            f'<p style="{_P_STYLE}">'
            f"Quality score {'improved' if delta >= 0 else 'declined'} by "
            f"{abs(delta):.2f} after cleaning.</p>"
        ),
    ]
    if issues:
        html_parts.append(_issues_table_html(issues))
    else:
        html_parts.append(f'<p style="{_P_STYLE}">No issues found.</p>')

    text_parts = [
        "CSV DATA QUALITY REPORT",
        f"Generated: {data.get('timestamp', '')}",
        "",
        *[f"{label}: {value}" for label, value in stat_items],
        "",
        f"Quality score {'improved' if delta >= 0 else 'declined'} by {abs(delta):.2f}.",
    ]
    if issues:
        text_parts.append(f"\n{len(issues)} issue(s) found -- see attached report for detail.")

    return "\n".join(html_parts), "\n".join(text_parts)


def _issues_table_html(issues: list[dict[str, Any]], max_rows: int = 20) -> str:
    rows = issues[:max_rows]
    header = (
        f'<tr><th style="{_TH_STYLE}">Row</th><th style="{_TH_STYLE}">Field</th>'
        f'<th style="{_TH_STYLE}">Type</th><th style="{_TH_STYLE}">Message</th></tr>'
    )
    body = "".join(
        f'<tr><td style="{_TD_STYLE}">{html.escape(str(i.get("row_index", "")))}</td>'
        f'<td style="{_TD_STYLE}">{html.escape(str(i.get("field", "")))}</td>'
        f'<td style="{_TD_STYLE}">{html.escape(str(i.get("issue_type", "")))}</td>'
        f'<td style="{_TD_STYLE}">{html.escape(str(i.get("message", "")))}</td></tr>'
        for i in rows
    )
    footer = ""
    if len(issues) > max_rows:
        footer = (
            f'<p style="{_P_STYLE}">... and {len(issues) - max_rows} more '
            f"-- see the attached report for the full list.</p>"
        )
    return f'<table style="{_TABLE_STYLE}">{header}{body}</table>{footer}'


def _format_scrape_report(data: dict[str, Any]) -> tuple[str, str]:
    stat_items = [
        ("Pages attempted", data.get("pages_attempted", "?")),
        ("Pages succeeded", data.get("pages_succeeded", "?")),
        ("Pages failed", data.get("pages_failed", "?")),
        ("Skipped (robots.txt)", data.get("pages_skipped_robots", "?")),
        ("Contacts found", data.get("total_contacts_found", "?")),
        ("Valid contacts", data.get("valid_contacts_found", "?")),
        ("Unique emails", data.get("unique_valid_emails", "?")),
        ("Unique phones", data.get("unique_valid_phones", "?")),
    ]

    failed_pages = [
        p for p in data.get("page_results", []) if p.get("error") or p.get("skipped_reason")
    ]

    html_parts = [
        f'<h1 style="{_H1_STYLE}">Contact Scrape Report</h1>',
        _stat_boxes_html(stat_items),
    ]
    if failed_pages:
        html_parts.append(_failed_pages_table_html(failed_pages))

    text_parts = [
        "CONTACT SCRAPE REPORT",
        "",
        *[f"{label}: {value}" for label, value in stat_items],
    ]
    if failed_pages:
        text_parts.append(f"\n{len(failed_pages)} page(s) failed or were skipped.")

    return "\n".join(html_parts), "\n".join(text_parts)


def _failed_pages_table_html(pages: list[dict[str, Any]], max_rows: int = 20) -> str:
    rows = pages[:max_rows]
    header = f'<tr><th style="{_TH_STYLE}">URL</th><th style="{_TH_STYLE}">Reason</th></tr>'
    body = "".join(
        f'<tr><td style="{_TD_STYLE}">{html.escape(str(p.get("url", "")))}</td>'
        f'<td style="{_TD_STYLE}">'
        f'{html.escape(str(p.get("error") or p.get("skipped_reason") or ""))}</td></tr>'
        for p in rows
    )
    return (
        f'<h3 style="{_H1_STYLE}">Failed / Skipped Pages</h3>'
        f'<table style="{_TABLE_STYLE}">{header}{body}</table>'
    )


def _stat_boxes_html(items: list[tuple[str, Any]]) -> str:
    boxes = "".join(
        f'<div style="{_STAT_BOX_STYLE}"><b>{html.escape(str(value))}</b><br>'
        f'<span style="font-size:12px;color:#666;">{html.escape(label)}</span></div>'
        for label, value in items
    )
    return f"<div>{boxes}</div>"


def _format_generic(data: dict[str, Any], title: str) -> tuple[str, str]:
    html_rows = "".join(
        f'<tr><td style="{_TD_STYLE}"><b>{html.escape(str(k))}</b></td>'
        f'<td style="{_TD_STYLE}">{html.escape(str(v))}</td></tr>'
        for k, v in data.items()
    )
    html_body = (
        f'<h1 style="{_H1_STYLE}">{html.escape(title)}</h1>'
        f'<table style="{_TABLE_STYLE}">{html_rows}</table>'
    )
    text_body = f"{title.upper()}\n\n" + "\n".join(f"{k}: {v}" for k, v in data.items())
    return html_body, text_body
