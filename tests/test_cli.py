"""Tests for report_mailer.cli.

SMTP is mocked -- real end-to-end CLI behavior against a local
debugging SMTP server was verified by hand while building this module.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from report_mailer.cli import send

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def run(args):
    return CliRunner().invoke(send, args)


class TestDryRun:
    def test_dry_run_does_not_touch_smtp(self):
        with patch("report_mailer.cli.ReportMailer") as mock_mailer_class:
            result = run(
                [
                    str(FIXTURES_DIR / "sample_quality_report.json"),
                    "--to", "client@example.com",
                    "--smtp-host", "smtp.x.com",
                    "--dry-run",
                ]
            )
        assert result.exit_code == 0
        mock_mailer_class.assert_not_called()
        assert "dry run" in result.output
        assert "client@example.com" in result.output

    def test_dry_run_auto_detects_subject(self):
        result = run(
            [
                str(FIXTURES_DIR / "sample_scrape_report.json"),
                "--to", "client@example.com",
                "--smtp-host", "smtp.x.com",
                "--dry-run",
            ]
        )
        assert "Contact Scrape Report" in result.output


class TestSend:
    @patch("report_mailer.cli.ReportMailer")
    def test_successful_send_reports_recipients(self, mock_mailer_class):
        from report_mailer.models import EmailSendResult

        mock_mailer = MagicMock()
        mock_mailer.send.return_value = EmailSendResult(success=True, recipients=["a@x.com"])
        mock_mailer_class.return_value = mock_mailer

        result = run(
            [
                str(FIXTURES_DIR / "sample_quality_report.json"),
                "--to", "a@x.com",
                "--smtp-host", "smtp.x.com",
            ]
        )

        assert result.exit_code == 0
        assert "Sent to a@x.com" in result.output

    @patch("report_mailer.cli.ReportMailer")
    def test_failed_send_exits_nonzero(self, mock_mailer_class):
        from report_mailer.models import EmailSendResult

        mock_mailer = MagicMock()
        mock_mailer.send.return_value = EmailSendResult(
            success=False, recipients=["a@x.com"], error="connection refused"
        )
        mock_mailer_class.return_value = mock_mailer

        result = run(
            [
                str(FIXTURES_DIR / "sample_quality_report.json"),
                "--to", "a@x.com",
                "--smtp-host", "smtp.x.com",
            ]
        )

        assert result.exit_code != 0
        assert "connection refused" in result.output

    @patch("report_mailer.cli.ReportMailer")
    def test_bad_smtp_config_reports_a_clean_error_not_a_traceback(self, mock_mailer_class):
        from report_mailer.models import ReportMailerError

        mock_mailer_class.side_effect = ReportMailerError("smtp_port must be positive, got 0")

        result = run(
            [
                str(FIXTURES_DIR / "sample_quality_report.json"),
                "--to", "a@x.com",
                "--smtp-host", "smtp.x.com",
                "--smtp-port", "0",
            ]
        )

        assert result.exit_code != 0
        assert "Traceback" not in result.output

    @patch("report_mailer.cli.ReportMailer")
    def test_attachment_included_by_default(self, mock_mailer_class):
        from report_mailer.models import EmailSendResult

        mock_mailer = MagicMock()
        mock_mailer.send.return_value = EmailSendResult(success=True, recipients=["a@x.com"])
        mock_mailer_class.return_value = mock_mailer

        run(
            [
                str(FIXTURES_DIR / "sample_quality_report.json"),
                "--to", "a@x.com",
                "--smtp-host", "smtp.x.com",
            ]
        )

        sent_message = mock_mailer.send.call_args[0][0]
        assert len(sent_message.attachments) == 1
        assert sent_message.attachments[0].filename == "sample_quality_report.json"

    @patch("report_mailer.cli.ReportMailer")
    def test_no_attach_flag_omits_attachment(self, mock_mailer_class):
        from report_mailer.models import EmailSendResult

        mock_mailer = MagicMock()
        mock_mailer.send.return_value = EmailSendResult(success=True, recipients=["a@x.com"])
        mock_mailer_class.return_value = mock_mailer

        run(
            [
                str(FIXTURES_DIR / "sample_quality_report.json"),
                "--to", "a@x.com",
                "--smtp-host", "smtp.x.com",
                "--no-attach",
            ]
        )

        sent_message = mock_mailer.send.call_args[0][0]
        assert sent_message.attachments == []

    @patch("report_mailer.cli.ReportMailer")
    def test_custom_subject_overrides_auto_detected_one(self, mock_mailer_class):
        from report_mailer.models import EmailSendResult

        mock_mailer = MagicMock()
        mock_mailer.send.return_value = EmailSendResult(success=True, recipients=["a@x.com"])
        mock_mailer_class.return_value = mock_mailer

        run(
            [
                str(FIXTURES_DIR / "sample_quality_report.json"),
                "--to", "a@x.com",
                "--smtp-host", "smtp.x.com",
                "--subject", "Weekly Report",
            ]
        )

        sent_message = mock_mailer.send.call_args[0][0]
        assert sent_message.subject == "Weekly Report"

    @patch.dict("os.environ", {"REPORT_MAILER_SMTP_PASSWORD": "from-env-secret"})
    @patch("report_mailer.cli.ReportMailer")
    def test_password_read_from_env_var_when_not_passed(self, mock_mailer_class):
        from report_mailer.models import EmailSendResult

        mock_mailer = MagicMock()
        mock_mailer.send.return_value = EmailSendResult(success=True, recipients=["a@x.com"])
        mock_mailer_class.return_value = mock_mailer

        run(
            [
                str(FIXTURES_DIR / "sample_quality_report.json"),
                "--to", "a@x.com",
                "--smtp-host", "smtp.x.com",
                "--smtp-user", "me@x.com",
            ]
        )

        _, kwargs = mock_mailer_class.call_args
        assert kwargs["password"] == "from-env-secret"
