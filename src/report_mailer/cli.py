"""Command-line interface for report-mailer, built on Click."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import click

from .formatter import detect_report_type, format_report
from .logger import configure_logging
from .mailer import ReportMailer
from .models import EmailAttachment, EmailMessage, ReportMailerError

__all__ = ["send"]

_REPORT_TYPE_TITLES = {
    "quality_report": "CSV Data Quality Report",
    "scrape_report": "Contact Scrape Report",
    "generic": "Report",
}


@click.command()
@click.argument("report_json", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--to", "to_addrs", multiple=True, required=True, help="Recipient address (repeatable)."
)
@click.option("--cc", "cc_addrs", multiple=True, help="CC address (repeatable).")
@click.option(
    "--subject",
    default=None,
    help="Email subject. Auto-generated from the report type if omitted.",
)
@click.option(
    "--attach/--no-attach", default=True, show_default=True, help="Attach the raw report JSON."
)
@click.option("--smtp-host", required=True, help="SMTP server hostname.")
@click.option("--smtp-port", default=587, show_default=True, help="SMTP server port.")
@click.option(
    "--smtp-user",
    default=None,
    help="SMTP auth username. Also used as the From address unless overridden.",
)
@click.option(
    "--smtp-password",
    default=None,
    help="SMTP auth password. Defaults to the REPORT_MAILER_SMTP_PASSWORD env var -- "
    "avoid passing this directly on the command line where it can end up in shell history.",
)
@click.option("--sender", default=None, help="From address. Defaults to --smtp-user.")
@click.option("--no-tls", is_flag=True, default=False, help="Disable STARTTLS.")
@click.option(
    "--no-validate-recipients",
    is_flag=True,
    default=False,
    help="Skip validating recipient addresses before sending.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Build and print the email without actually sending it.",
)
@click.option(
    "--verbose", is_flag=True, default=False, help="Enable verbose (INFO-level) console logging."
)
def send(
    report_json: str,
    to_addrs: tuple,
    cc_addrs: tuple,
    subject: str,
    attach: bool,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    sender: str,
    no_tls: bool,
    no_validate_recipients: bool,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Email the report at REPORT_JSON to one or more recipients.

    Auto-detects whether REPORT_JSON is a csv-data-cleaner quality
    report, a contact-scraper scrape report, or a generic JSON object,
    and formats an HTML summary email accordingly.

        report-mailer quality_report.json --to client@example.com \\
            --smtp-host smtp.gmail.com --smtp-user me@gmail.com

    For recurring reports, schedule this command with cron (Linux/macOS)
    or Task Scheduler (Windows) -- this tool sends one email per
    invocation and does not include its own scheduler.
    """
    if verbose:
        configure_logging(level=logging.INFO)

    password = smtp_password or os.environ.get("REPORT_MAILER_SMTP_PASSWORD")

    with open(report_json, encoding="utf-8") as f:
        data = json.load(f)

    report_type = detect_report_type(data)
    html_body, text_body = format_report(data, title=Path(report_json).stem)
    resolved_subject = subject or _REPORT_TYPE_TITLES[report_type]

    attachments = []
    if attach:
        attachments.append(
            EmailAttachment(
                filename=Path(report_json).name,
                content=Path(report_json).read_bytes(),
                mime_type="application/json",
            )
        )

    message = EmailMessage(
        to=list(to_addrs),
        cc=list(cc_addrs),
        subject=resolved_subject,
        html_body=html_body,
        text_body=text_body,
        attachments=attachments,
    )

    if dry_run:
        click.echo(f"[dry run] Would send to: {', '.join(message.to)}")
        if message.cc:
            click.echo(f"[dry run] CC: {', '.join(message.cc)}")
        click.echo(f"[dry run] Subject: {message.subject}")
        click.echo(f"[dry run] Attachments: {[a.filename for a in message.attachments]}")
        click.echo("\n--- Plain-text body ---")
        click.echo(message.text_body)
        return

    try:
        mailer = ReportMailer(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            username=smtp_user,
            password=password,
            sender=sender,
            use_tls=not no_tls,
            validate_recipients=not no_validate_recipients,
        )
        result = mailer.send(message)
    except ReportMailerError as exc:
        raise click.ClickException(str(exc)) from exc

    if result.success:
        click.echo(f"Sent to {', '.join(result.recipients)}")
    else:
        click.echo(f"Failed to send: {result.error}", err=True)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(send())
