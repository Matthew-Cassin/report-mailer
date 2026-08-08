"""Tests for report_mailer.models."""

from report_mailer.models import EmailAttachment, EmailMessage, EmailSendResult


class TestEmailAttachment:
    def test_construction_keeps_all_fields(self):
        att = EmailAttachment("report.json", b'{"a": 1}', "application/json")
        assert att.filename == "report.json"
        assert att.content == b'{"a": 1}'
        assert att.mime_type == "application/json"

    def test_default_mime_type(self):
        att = EmailAttachment("data.bin", b"raw")
        assert att.mime_type == "application/octet-stream"


class TestEmailMessage:
    def test_construction_keeps_all_fields(self):
        msg = EmailMessage(
            to=["a@x.com"],
            subject="Subject",
            html_body="<p>hi</p>",
            text_body="hi",
            cc=["b@x.com"],
        )
        assert msg.to == ["a@x.com"]
        assert msg.cc == ["b@x.com"]

    def test_default_cc_and_attachments_are_empty(self):
        msg = EmailMessage(to=["a@x.com"], subject="s", html_body="<p/>", text_body="t")
        assert msg.cc == []
        assert msg.attachments == []

    def test_default_lists_not_shared_between_instances(self):
        first = EmailMessage(to=["a"], subject="s", html_body="h", text_body="t")
        second = EmailMessage(to=["b"], subject="s", html_body="h", text_body="t")
        first.cc.append("x")
        first.attachments.append(EmailAttachment("f", b""))
        assert second.cc == []
        assert second.attachments == []


class TestEmailSendResult:
    def test_success_result(self):
        result = EmailSendResult(success=True, recipients=["a@x.com"])
        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        result = EmailSendResult(success=False, recipients=["a@x.com"], error="timed out")
        assert result.success is False
        assert result.error == "timed out"
