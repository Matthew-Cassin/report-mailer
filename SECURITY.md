# Security Policy

## Supported Versions

Only the latest published release receives security fixes.

| Version | Supported |
| ------- | --------- |
| 1.x     | ✅        |
| < 1.0   | ❌        |

## Reporting a Vulnerability

Please report suspected vulnerabilities privately via [GitHub's private
vulnerability reporting](https://github.com/Matthew-Cassin/report-mailer/security/advisories/new)
rather than filing a public issue. Include reproduction steps and the
affected version. Expect an initial response within 5 business days.

## Credential Handling

This tool never accepts SMTP credentials as command-line arguments logged
in shell history by default -- `--smtp-password` falls back to the
`REPORT_MAILER_SMTP_PASSWORD` environment variable, which is the
recommended way to supply it in CI/scheduled contexts.
