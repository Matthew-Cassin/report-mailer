"""Core data structures shared across report-mailer.

Mirrors the pattern used throughout this portfolio: a *failed send* is
always a normal, inspectable result (:class:`EmailSendResult` with
``success=False``), never an exception -- an SMTP timeout, an auth
failure, or an unreachable server is exactly the kind of "reached out
into the world and it didn't work" outcome that
:class:`~contact_scraper.models.PageResult` treats the same way.
:class:`ReportMailerError` is reserved strictly for bad configuration or
wrong argument types, something the caller must fix in code before a
send can even be attempted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

__all__ = ["EmailAttachment", "EmailMessage", "EmailSendResult", "ReportMailerError"]


@dataclass
class EmailAttachment:
    """A single file attached to an outgoing email.

    Attributes:
        filename: The name the attachment will show up as in the
            recipient's mail client, e.g. ``"quality_report.json"``.
        content: The raw file bytes.
        mime_type: The attachment's MIME type, e.g.
            ``"application/json"`` or ``"text/csv"``.
    """

    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


@dataclass
class EmailMessage:
    """A fully-composed email, ready to hand to
    :class:`~report_mailer.mailer.ReportMailer`.

    Attributes:
        to: Recipient addresses.
        subject: The email subject line.
        html_body: The HTML version of the message body.
        text_body: The plain-text fallback, shown by mail clients that
            don't render HTML.
        cc: Carbon-copy addresses.
        attachments: Files to attach, e.g. the underlying report JSON
            or CSV.
    """

    to: List[str]
    subject: str
    html_body: str
    text_body: str
    cc: List[str] = field(default_factory=list)
    attachments: List[EmailAttachment] = field(default_factory=list)


@dataclass
class EmailSendResult:
    """The outcome of attempting to send one :class:`EmailMessage`.

    A connection failure, an authentication error, or an SMTP server
    rejecting a recipient is always represented here rather than
    raised -- ``success=False`` with ``error`` set. This is what lets a
    caller sending several reports in a row keep going after one
    fails, the same way a multi-page scrape keeps going after one bad
    page.

    Attributes:
        success: Whether the message was successfully handed off to the
            SMTP server.
        recipients: The addresses (``to`` + ``cc``) the send was
            attempted for.
        error: A human-readable failure reason. ``None`` on success.
    """

    success: bool
    recipients: List[str]
    error: Optional[str] = None


class ReportMailerError(Exception):
    """Raised when a send cannot even be attempted, not just when it fails.

    A send that times out, gets rejected by the SMTP server, or fails
    auth is an ordinary :class:`EmailSendResult` with ``success=False``
    -- that is the expected, everyday outcome and callers should not
    need a try/except for it (see that class's docstring).

    ``ReportMailerError`` is reserved for cases the caller must fix in
    code before a send can even start, such as:

    * Constructing ``ReportMailer`` with invalid configuration (e.g. a
      non-positive ``port`` or ``timeout``).
    * Building an :class:`EmailMessage` with no recipients at all.
    * Calling a method with a value of the wrong type.

    A merely *malformed* recipient address (a well-typed string that
    isn't a valid email) is not an exception either -- when
    ``ReportMailer`` is configured to validate recipients (the default;
    see its docstring), a bad address comes back as a failed
    :class:`EmailSendResult` instead, the same as any other send
    failure.
    """
