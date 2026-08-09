"""Sends composed :class:`~report_mailer.models.EmailMessage` objects via SMTP.

:class:`ReportMailer` wraps the standard library's ``smtplib``/``email``
modules: builds a multipart HTML+plain-text message (with optional file
attachments), connects, and sends. A connection failure, an auth error,
or an SMTP server rejecting a recipient always comes back as a normal
:class:`~report_mailer.models.EmailSendResult`, never a raised exception
-- see that class's docstring, and
:class:`~report_mailer.models.ReportMailerError`'s.
"""

from __future__ import annotations

import smtplib
from email import encoders
from email.charset import QP, Charset
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from email_phone_validator import EmailValidator

from .models import EmailMessage, EmailSendResult, ReportMailerError

__all__ = ["ReportMailer"]

# Found empirically while building this: MIMEText's default encoding
# for plain ASCII content is unencoded 7bit, which does not wrap long
# lines -- a real-world HTML body (with everything on a handful of long
# lines, as ``formatter.py`` produces) can exceed SMTP's hard per-line
# length limit (RFC 5321 4.5.3.1.6) and get rejected by the server.
# Forcing quoted-printable encoding soft-wraps every line safely,
# regardless of content.
_QP_CHARSET = Charset("utf-8")
_QP_CHARSET.body_encoding = QP


class ReportMailer:
    """Sends report emails over SMTP.

    Args:
        smtp_host: The SMTP server hostname.
        smtp_port: The SMTP server port. Must be positive. Defaults to
            ``587`` (the conventional STARTTLS submission port).
        username: SMTP auth username. When set together with
            ``password``, :meth:`send` logs in before sending.
        password: SMTP auth password.
        use_tls: When ``True`` (the default), issues ``STARTTLS`` after
            connecting, before any auth/send.
        timeout: Seconds to wait on the SMTP connection before giving
            up. Must be positive.
        sender: The ``From`` address. Defaults to ``username`` if not
            given -- one of the two must end up set, or construction
            raises.
        validate_recipients: When ``True`` (the default), every
            recipient in a message's ``to``/``cc`` is checked with
            ``email_phone_validator.EmailValidator`` before attempting
            to send; an invalid address becomes a failed
            :class:`~report_mailer.models.EmailSendResult` rather than
            an SMTP round-trip that was doomed anyway.
        email_validator: A custom ``EmailValidator`` instance. Defaults
            to ``EmailValidator(check_mx=False)`` when
            ``validate_recipients`` is ``True``.

    Raises:
        ReportMailerError: If ``smtp_port``/``timeout`` is not positive,
            or if neither ``sender`` nor ``username`` is given.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        timeout: int = 10,
        sender: str | None = None,
        validate_recipients: bool = True,
        email_validator: EmailValidator | None = None,
    ) -> None:
        if smtp_port <= 0:
            raise ReportMailerError(f"smtp_port must be positive, got {smtp_port}")
        if timeout <= 0:
            raise ReportMailerError(f"timeout must be positive, got {timeout}")

        resolved_sender = sender or username
        if not resolved_sender:
            raise ReportMailerError("either sender or username must be provided")

        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.timeout = timeout
        self.sender = resolved_sender
        self.validate_recipients = validate_recipients
        self.email_validator = email_validator or EmailValidator(check_mx=False)

    def send(self, message: EmailMessage) -> EmailSendResult:
        """Send ``message``. Never raises for a connection/auth/send failure.

        Raises:
            ReportMailerError: If ``message`` has no recipients at all
                (nothing to even attempt).
        """
        recipients = list(message.to) + list(message.cc)
        if not recipients:
            raise ReportMailerError("EmailMessage must have at least one recipient")

        if self.validate_recipients:
            invalid = self._invalid_recipients(recipients)
            if invalid:
                return EmailSendResult(
                    success=False,
                    recipients=recipients,
                    error=f"invalid recipient address(es): {', '.join(invalid)}",
                )

        mime_message = self._build_mime(message)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.sendmail(self.sender, recipients, mime_message.as_string())
        except smtplib.SMTPException as exc:
            return EmailSendResult(success=False, recipients=recipients, error=str(exc))
        except OSError as exc:
            return EmailSendResult(success=False, recipients=recipients, error=str(exc))

        return EmailSendResult(success=True, recipients=recipients)

    def _invalid_recipients(self, recipients: list[str]) -> list[str]:
        return [r for r in recipients if not self.email_validator.validate(r).is_valid]

    def _build_mime(self, message: EmailMessage) -> MIMEMultipart:
        mime = MIMEMultipart("mixed")
        mime["Subject"] = message.subject
        mime["From"] = self.sender
        mime["To"] = ", ".join(message.to)
        if message.cc:
            mime["Cc"] = ", ".join(message.cc)

        alt = MIMEMultipart("alternative")
        # MIMEText genuinely accepts an email.charset.Charset at runtime
        # (that's how body_encoding=QP gets applied instead of base64);
        # typeshed's stub only declares `str | None`.
        alt.attach(MIMEText(message.text_body, "plain", _charset=_QP_CHARSET))  # type: ignore[arg-type]
        alt.attach(MIMEText(message.html_body, "html", _charset=_QP_CHARSET))  # type: ignore[arg-type]
        mime.attach(alt)

        for attachment in message.attachments:
            maintype, _, subtype = attachment.mime_type.partition("/")
            part = MIMEBase(maintype or "application", subtype or "octet-stream")
            part.set_payload(attachment.content)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", f'attachment; filename="{attachment.filename}"'
            )
            mime.attach(part)

        return mime
