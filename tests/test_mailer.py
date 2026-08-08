"""Tests for report_mailer.mailer.

SMTP itself is mocked here -- a real send through a local debugging
SMTP server (aiosmtpd) was verified by hand while building this module,
including the actual quoted-printable line-wrapping bug it caught (see
TestBuildMime::test_no_line_exceeds_smtp_length_limit below, which
regression-tests that specific fix).
"""

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from report_mailer.mailer import ReportMailer
from report_mailer.models import EmailAttachment, EmailMessage, ReportMailerError


def make_mailer(**kwargs):
    kwargs.setdefault("sender", "reports@x.com")
    kwargs.setdefault("validate_recipients", False)
    return ReportMailer("smtp.x.com", **kwargs)


class TestConstructorValidation:
    def test_non_positive_port_raises(self):
        with pytest.raises(ReportMailerError, match="smtp_port"):
            ReportMailer("smtp.x.com", smtp_port=0, sender="a@x.com")

    def test_non_positive_timeout_raises(self):
        with pytest.raises(ReportMailerError, match="timeout"):
            ReportMailer("smtp.x.com", timeout=0, sender="a@x.com")

    def test_no_sender_and_no_username_raises(self):
        with pytest.raises(ReportMailerError, match="sender"):
            ReportMailer("smtp.x.com")

    def test_sender_defaults_to_username(self):
        mailer = ReportMailer("smtp.x.com", username="me@x.com")
        assert mailer.sender == "me@x.com"

    def test_explicit_sender_overrides_username(self):
        mailer = ReportMailer("smtp.x.com", username="me@x.com", sender="reports@x.com")
        assert mailer.sender == "reports@x.com"


class TestSend:
    def test_no_recipients_raises(self):
        mailer = make_mailer()
        message = EmailMessage(to=[], subject="s", html_body="<p/>", text_body="t")
        with pytest.raises(ReportMailerError, match="recipient"):
            mailer.send(message)

    @patch("report_mailer.mailer.smtplib.SMTP")
    def test_successful_send(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        mailer = make_mailer()
        message = EmailMessage(to=["a@x.com"], subject="s", html_body="<p/>", text_body="t")

        result = mailer.send(message)

        assert result.success is True
        assert result.recipients == ["a@x.com"]
        mock_smtp.sendmail.assert_called_once()

    @patch("report_mailer.mailer.smtplib.SMTP")
    def test_starttls_called_when_use_tls_true(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        mailer = make_mailer(use_tls=True)
        message = EmailMessage(to=["a@x.com"], subject="s", html_body="<p/>", text_body="t")

        mailer.send(message)

        mock_smtp.starttls.assert_called_once()

    @patch("report_mailer.mailer.smtplib.SMTP")
    def test_starttls_not_called_when_use_tls_false(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        mailer = make_mailer(use_tls=False)
        message = EmailMessage(to=["a@x.com"], subject="s", html_body="<p/>", text_body="t")

        mailer.send(message)

        mock_smtp.starttls.assert_not_called()

    @patch("report_mailer.mailer.smtplib.SMTP")
    def test_login_called_when_credentials_given(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        mailer = ReportMailer(
            "smtp.x.com", username="me@x.com", password="secret", validate_recipients=False
        )
        message = EmailMessage(to=["a@x.com"], subject="s", html_body="<p/>", text_body="t")

        mailer.send(message)

        mock_smtp.login.assert_called_once_with("me@x.com", "secret")

    @patch("report_mailer.mailer.smtplib.SMTP")
    def test_login_not_called_without_credentials(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        mailer = make_mailer()
        message = EmailMessage(to=["a@x.com"], subject="s", html_body="<p/>", text_body="t")

        mailer.send(message)

        mock_smtp.login.assert_not_called()

    @patch("report_mailer.mailer.smtplib.SMTP")
    def test_smtp_exception_is_a_failed_result_not_an_exception(self, mock_smtp_class):
        mock_smtp_class.return_value.__enter__.side_effect = smtplib.SMTPConnectError(
            421, "cannot connect"
        )
        mailer = make_mailer()
        message = EmailMessage(to=["a@x.com"], subject="s", html_body="<p/>", text_body="t")

        result = mailer.send(message)

        assert result.success is False
        assert result.error is not None

    @patch("report_mailer.mailer.smtplib.SMTP")
    def test_os_error_is_a_failed_result_not_an_exception(self, mock_smtp_class):
        mock_smtp_class.return_value.__enter__.side_effect = TimeoutError("timed out")
        mailer = make_mailer()
        message = EmailMessage(to=["a@x.com"], subject="s", html_body="<p/>", text_body="t")

        result = mailer.send(message)

        assert result.success is False
        assert "timed out" in result.error

    def test_invalid_recipient_is_a_failed_result_without_hitting_smtp(self):
        mailer = make_mailer(validate_recipients=True)
        message = EmailMessage(to=["not-an-email"], subject="s", html_body="<p/>", text_body="t")

        with patch("report_mailer.mailer.smtplib.SMTP") as mock_smtp_class:
            result = mailer.send(message)
            mock_smtp_class.assert_not_called()

        assert result.success is False
        assert "invalid recipient" in result.error

    @patch("report_mailer.mailer.smtplib.SMTP")
    def test_cc_recipients_included_in_sendmail_call(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        mailer = make_mailer()
        message = EmailMessage(
            to=["a@x.com"], cc=["b@x.com"], subject="s", html_body="<p/>", text_body="t"
        )

        result = mailer.send(message)

        assert result.recipients == ["a@x.com", "b@x.com"]
        _, call_recipients, _ = mock_smtp.sendmail.call_args[0]
        assert call_recipients == ["a@x.com", "b@x.com"]


class TestBuildMime:
    def test_no_line_exceeds_smtp_length_limit(self):
        # Regression test for a real bug found empirically: MIMEText's
        # default 7bit encoding doesn't wrap long lines, and a real
        # formatter.py HTML body (everything on a handful of long
        # lines) exceeded SMTP's 998-octet line limit and was rejected
        # by a real server. Forcing quoted-printable fixed it.
        mailer = make_mailer()
        long_html = "<p>" + "x" * 5000 + "</p>"
        message = EmailMessage(to=["a@x.com"], subject="s", html_body=long_html, text_body="t")

        mime = mailer._build_mime(message)

        for line in mime.as_string().splitlines():
            assert len(line) <= 998, f"line exceeds SMTP limit: {len(line)} chars"

    def test_attachment_is_base64_encoded_with_correct_filename(self):
        mailer = make_mailer()
        message = EmailMessage(
            to=["a@x.com"],
            subject="s",
            html_body="<p/>",
            text_body="t",
            attachments=[EmailAttachment("report.json", b'{"x":1}', "application/json")],
        )

        mime = mailer._build_mime(message)
        raw = mime.as_string()

        assert 'filename="report.json"' in raw
        assert "Content-Transfer-Encoding: base64" in raw

    def test_headers_include_subject_from_and_to(self):
        mailer = make_mailer()
        message = EmailMessage(to=["a@x.com"], subject="Hello", html_body="<p/>", text_body="t")

        mime = mailer._build_mime(message)

        assert mime["Subject"] == "Hello"
        assert mime["From"] == "reports@x.com"
        assert mime["To"] == "a@x.com"

    def test_cc_header_only_present_when_cc_given(self):
        mailer = make_mailer()
        no_cc = EmailMessage(to=["a@x.com"], subject="s", html_body="<p/>", text_body="t")
        with_cc = EmailMessage(
            to=["a@x.com"], cc=["b@x.com"], subject="s", html_body="<p/>", text_body="t"
        )

        assert mailer._build_mime(no_cc)["Cc"] is None
        assert mailer._build_mime(with_cc)["Cc"] == "b@x.com"
