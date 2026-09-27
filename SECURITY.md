# Security Policy

## Supported versions

AgentAudit is currently pre-1.0. Security fixes are applied to the latest released version.

## Reporting a vulnerability

Please do **not** open a public GitHub issue for a vulnerability that could expose secrets, private traces, authentication material, or unsafe execution behaviour.

Until a private security-reporting channel is configured for the repository, contact the repository maintainer privately through their GitHub profile and include:

- affected version or commit;
- a concise description of the issue;
- reproduction steps or a minimal proof of concept;
- potential impact; and
- any suggested mitigation.

Do not include real secrets, personal data, or confidential production traces in the report.

## Security scope

AgentAudit evaluates and records agent behaviour; it does not sandbox agent code or tools. Users remain responsible for isolating untrusted execution, protecting credentials, and redacting sensitive trace data before storage or sharing.
