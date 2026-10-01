# Security Policy

## Supported versions

The Community edition follows a rolling release model. Only the latest release
on the `main` branch receives security fixes.

| Version | Supported |
| ------- | --------- |
| latest  | yes       |
| older   | no        |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, use one of the private channels below:

- Open a [GitHub Security Advisory](https://github.com/jsonnguyen19/sonsery-flow-community/security/advisories/new) (Security tab -> Report a vulnerability).
- If you cannot use GitHub, email the maintainer directly: **hongsonit10@gmail.com** (PGP on request).

Please include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof-of-concept.
- Affected version(s) and platform(s).
- Any suggested mitigation, if known.

## What to expect

- Acknowledgement within 72 hours.
- Initial assessment within 7 days.
- Fix or mitigation plan communicated once the issue is triaged.
- Credit in the release notes if you want it (opt-in).

We ask that you give us a reasonable time to address the issue before any public
disclosure.

## Scope notes for this project

The tool runs locally on your machine and bridges your web AI tab to your
terminal through a localhost HTTP bridge. In-scope issues include, for example:

- Command injection through the payload parser.
- Path traversal in the file tools (read / replace / write).
- Authentication bypass on the local bridge.
- Secret leakage through logs or clipboard handling.

Out of scope: issues that require an already-compromised local machine, or
attacks that rely on the user pasting malicious payloads into their own AI chat.
