# Security

The `ops-field-brief` runtime CLI is local-only: it reads one CSV, writes a report, does not open network connections, and does not store credentials.

The repository also contains `scripts/autonomous_agent.py`, a maintenance helper that is local-only by default. Its optional Gemini assessment can make an outbound HTTPS request only when **both** conditions are true:

1. the manual invocation includes `--allow-external-api`; and
2. `GEMINI_API_KEY` is present in the environment.

An API key by itself does not enable network access, and the scheduled GitHub Actions audit does not pass `--allow-external-api`. Regression tests enforce these safe-default paths.

When manually enabled, the optional API response is **untrusted**. The maintenance helper redacts the configured key from returned text, limits logged feedback to 4,000 characters, and JSON-escapes it onto a single log line. This prevents raw control characters, line breaks, and GitHub workflow-command markers from being interpreted as runner instructions. The normal local-only schedule remains unchanged.

## Reporting a problem

If you find a security issue, open a private GitHub security advisory on this repository, or use the contact information on the [profile README](https://github.com/rodrix91/rodrix91). Please do not open a public issue for an unfixed vulnerability.

## Scope

In scope: unexpected crashes, unsafe path handling, misleading pipeline output, accidental network access, or behavior that could expose credentials through the optional maintenance path.

Out of scope: the contents of the CSV the user intentionally chooses to read and failures of an explicitly enabled third-party API outside this repository's control.
