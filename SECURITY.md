# Security and privacy

ApplyLess processes career documents, which can contain sensitive personal
information. The v0.1 design minimizes collection and transmission.

## Data flow

- The HTTP server binds to `127.0.0.1` by default.
- Resume and job-description text is sent from the local page to the local
  Python process.
- The process scores the text in memory. It does not write the inputs to a
  database or log file.
- No analytics, external fonts, CDNs, model APIs, or remote requests are used.
- Responses use a restrictive Content Security Policy and JSON is marked
  `no-store`.

The browser page remains in browser memory after analysis. Close the tab or
reload it if you want to clear the text fields.

## Non-goals

This project does not protect against a compromised operating system, browser,
or Python environment. Running untrusted software or serving ApplyLess on a
public interface changes the threat model and is unsupported.

## Reporting

Do not include a real resume, account credential, or other personal data in a
security report. Describe the issue with synthetic data and open a private
security advisory when the repository supports it.

