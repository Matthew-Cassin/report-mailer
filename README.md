# report-mailer

[![CI](https://github.com/Matthew-Cassin/report-mailer/actions/workflows/ci.yml/badge.svg)](https://github.com/Matthew-Cassin/report-mailer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Types](https://img.shields.io/badge/types-mypy%20strict-brightgreen)

A Python library and CLI that formats and emails the JSON reports my other tools already produce. Auto-detects [`csv-data-cleaner`](https://github.com/Matthew-Cassin/csv-data-cleaner)'s data-quality reports and [`contact-scraper`](https://github.com/Matthew-Cassin/contact-scraper)'s scrape reports (or falls back to a generic renderer for any other JSON), builds an HTML summary email with a plain-text fallback and the raw report attached, then sends it over SMTP.

## Installation

```bash
# Install directly from GitHub
pip install git+https://github.com/Matthew-Cassin/report-mailer.git

# Or clone and install locally for development
git clone https://github.com/Matthew-Cassin/report-mailer.git
cd report-mailer
pip install -e .
```

This pulls in [`email-phone-validator`](https://github.com/Matthew-Cassin/email-phone-validator) automatically, which report-mailer uses to validate recipient addresses before attempting to send -- a typo'd address fails fast as an ordinary result, not a wasted SMTP round-trip.

## Features

- **Auto-detects report type**: recognizes `csv-data-cleaner`'s `DataQualityReport` JSON and `contact-scraper`'s `ScrapeReport` JSON by shape, and formats each with a purpose-built summary; anything else gets a clean generic key/value or tabular rendering.
- **Real HTML email, not a hack**: inline styles throughout (mail clients like Gmail and Outlook strip `<style>` blocks), and every value is HTML-escaped.
- **Validates recipients** via `email-phone-validator` before ever opening an SMTP connection.
- **Never crashes on a send failure.** A bad SMTP connection, an auth failure, an unreachable server -- all come back as an ordinary result you can inspect, the same design used throughout this whole toolset.
- **Attaches the original report** alongside the HTML summary, so nothing is lost to formatting.
- **No built-in scheduler, on purpose.** For recurring reports, this CLI is one command meant to be invoked by cron or Task Scheduler -- see [Recurring Reports](#recurring-reports) below.

## Quick Start

The examples below send to a local debugging SMTP server (`aiosmtpd`) rather than a real inbox, so they're safe to run and reproduce exactly:

```bash
pip install aiosmtpd
python3 -u -m aiosmtpd -n -l localhost:8025   # prints received mail, delivers nothing
```

### 1. Basic Python usage: format and send a report

```python
from report_mailer import format_report, ReportMailer
from report_mailer.models import EmailMessage, EmailAttachment
import json

data = json.load(open("quality_report.json"))  # from csv-data-cleaner
html_body, text_body = format_report(data)
print(text_body)
```

```
CSV DATA QUALITY REPORT
Generated: 2026-08-08T03:23:06.790257+00:00

Total rows: 10
Rows kept: 9
Rows removed: 1
Quality before: 0.92
Quality after: 0.94
Issues found: 12

Quality score improved by 0.02.

12 issue(s) found -- see attached report for detail.
```

```python
mailer = ReportMailer("localhost", smtp_port=8025, sender="reports@mytools.dev", use_tls=False)
message = EmailMessage(
    to=["client@example.com"],
    subject="CSV Data Quality Report",
    html_body=html_body,
    text_body=text_body,
    attachments=[EmailAttachment("quality_report.json", json.dumps(data).encode(), "application/json")],
)
result = mailer.send(message)
print(f"Sent: {result.success}, recipients: {result.recipients}")
```

```
Sent: True, recipients: ['client@example.com']
```

### 2. CLI usage: preview before sending

```bash
report-mailer scrape_report.json --to client@example.com --smtp-host localhost --dry-run
```

```
[dry run] Would send to: client@example.com
[dry run] Subject: Contact Scrape Report
[dry run] Attachments: ['sample_scrape_report.json']

--- Plain-text body ---
CONTACT SCRAPE REPORT

Pages attempted: 1
Pages succeeded: 1
Pages failed: 0
Skipped (robots.txt): 0
Contacts found: 6
Valid contacts: 6
Unique emails: 3
Unique phones: 3
```

### 3. CLI usage: send for real

```bash
report-mailer scrape_report.json --to client@example.com \
    --smtp-host localhost --smtp-port 8025 --sender reports@mytools.dev --no-tls
```

```
Sent to client@example.com
```

Against a real mail provider, drop `--no-tls` and add `--smtp-user`, with the password read from the `REPORT_MAILER_SMTP_PASSWORD` environment variable rather than passed on the command line:

```bash
export REPORT_MAILER_SMTP_PASSWORD="your-app-password"
report-mailer quality_report.json --to client@example.com \
    --smtp-host smtp.gmail.com --smtp-user you@gmail.com
```

## Recurring Reports

This tool sends one report, once, per invocation -- it does not include its own scheduler, since the OS already has a better one. For a report that goes out automatically:

**cron (Linux/macOS)** -- e.g. every Monday at 8am:
```
0 8 * * 1 cd /path/to/reports && report-mailer quality_report.json --to team@company.com --smtp-host smtp.gmail.com --smtp-user you@gmail.com
```

**Task Scheduler (Windows)**: create a Basic Task that runs `report-mailer.exe` with the same arguments on your chosen schedule.

Combine with the other tools in this pipeline for a fully automated flow: `contact-scraper --crawl` (or `csv-data-cleaner`) writes a fresh report on a schedule, then a second scheduled `report-mailer` call -- a few minutes later -- emails it out.

## How It Works

**Detection.** `detect_report_type()` looks for the distinguishing keys each sibling project's JSON always has (`statistics.quality_score_before` for `csv-data-cleaner`, `pages_attempted` + `page_results` for `contact-scraper`) and falls back to `"generic"` otherwise.

**Formatting.** Each report type has a purpose-built formatter producing both an HTML body (stat boxes, an issues/failed-pages table capped at 20 rows with a "see attached" note beyond that) and a plain-text fallback. All formatting is pure -- no I/O, no network -- so it's fully unit-testable against real captured report JSON.

**Sending.** `ReportMailer.send()` validates recipients (unless disabled), builds a `multipart/mixed` MIME message (a `multipart/alternative` text+HTML body, plus any attachments), connects over SMTP, optionally `STARTTLS`s and logs in, and sends. Every step that talks to the network is wrapped so a failure becomes an `EmailSendResult(success=False, error=...)` rather than a crash.

## API Reference

### `ReportMailer`

```python
ReportMailer(smtp_host, smtp_port=587, username=None, password=None, use_tls=True,
             timeout=10, sender=None, validate_recipients=True, email_validator=None)
```

| Method | Description |
|---|---|
| `send(message) -> EmailSendResult` | Send an `EmailMessage`. Never raises for a connection/auth/send failure. |

### Formatting

`detect_report_type(data) -> str` -- `"quality_report"`, `"scrape_report"`, or `"generic"`.

`format_report(data, title="Report") -> Tuple[str, str]` -- `(html_body, text_body)`.

### Dataclasses

**`EmailAttachment`** -- `filename`, `content` (bytes), `mime_type`.

**`EmailMessage`** -- `to`, `subject`, `html_body`, `text_body`, `cc`, `attachments`.

**`EmailSendResult`** -- `success`, `recipients`, `error`.

## CLI Reference

```
report-mailer REPORT_JSON --to EMAIL [OPTIONS]
```

| Option | Description |
|---|---|
| `--to EMAIL` | Recipient address (repeatable). Required. |
| `--cc EMAIL` | CC address (repeatable). |
| `--subject TEXT` | Email subject. Auto-generated from the report type if omitted. |
| `--attach` / `--no-attach` | Attach the raw report JSON (default: on). |
| `--smtp-host HOST` | SMTP server hostname. Required. |
| `--smtp-port PORT` | SMTP server port (default 587). |
| `--smtp-user USER` | SMTP auth username; also the default `From` address. |
| `--smtp-password PASS` | SMTP auth password. Prefer the `REPORT_MAILER_SMTP_PASSWORD` env var instead -- avoid this flag where shell history is a concern. |
| `--sender EMAIL` | `From` address, if different from `--smtp-user`. |
| `--no-tls` | Disable STARTTLS. |
| `--no-validate-recipients` | Skip pre-send address validation. |
| `--dry-run` | Build and print the email without sending it. |
| `--verbose` | Enable INFO-level console logging. |

## Limitations

- **No scheduling built in**, deliberately -- see [Recurring Reports](#recurring-reports).
- **Report-type detection is shape-based**, not versioned. If a future version of `csv-data-cleaner` or `contact-scraper` renames its top-level JSON keys, detection would need updating here too; the generic formatter is always a safe fallback in the meantime.
- **Recipient validation checks format/MX only** (`EmailValidator(check_mx=False)` by default) -- it catches typos and malformed addresses, not whether a specific mailbox actually exists or accepts mail; that's still discovered at send time via the SMTP server's response.
- **A real MIME line-length bug was found and fixed empirically while building this**: Python's default `MIMEText` encoding for plain-ASCII content doesn't wrap long lines, and a real formatter-produced HTML body exceeded SMTP's hard 998-octet line limit (RFC 5321) and was rejected by a real server. Fixed by forcing quoted-printable encoding on both the HTML and plain-text parts; regression-tested in `test_mailer.py`.
- **Gmail and other major providers require an app password or OAuth2**, not your regular account password, for SMTP auth from a script -- consult your provider's docs.

## License

MIT -- see [LICENSE](LICENSE) for the full text.

## Contributing

Contributions are welcome. Please open an issue to discuss a change before submitting a pull request, and make sure `pytest` and `flake8` are clean.
