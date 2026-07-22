# Security Policy

CMM OS treats security as a core architectural requirement.

The project executes structured operations, modifies source code, maintains persistent technical memory, and is designed to evolve toward autonomous and domain-aware workflows. Security reports are therefore handled with priority, especially when they involve execution boundaries, rollback, permissions, secrets, memory integrity, or supply-chain risk.

---

## Supported versions

Security fixes are provided for the latest stable release and, when practical, for the immediately preceding release line.

| Version | Supported |
| --- | --- |
| `v0.7.x` | Yes |
| `< v0.7.0` | No |

Support coverage may change as the project evolves. The current release status is documented in [`ROADMAP.md`](ROADMAP.md) and the repository release notes.

---

## Reporting a vulnerability

Do not open a public GitHub issue for a suspected vulnerability.

Report security issues privately through one of the following channels:

1. GitHub private vulnerability reporting, when enabled for this repository.
2. A private message to the maintainer through the GitHub profile associated with this repository.
3. A private security advisory created from the repository Security tab.

Include the subject:

```text
[CMM OS Security] Short vulnerability title
```

Please avoid sending secrets, credentials, private repositories, or sensitive personal data unless strictly necessary to reproduce the issue.

---

## What to include

A useful security report should include:

- affected CMM OS version or commit;
- operating system and Python version;
- installation method;
- affected component;
- vulnerability category;
- clear impact description;
- preconditions required for exploitation;
- minimal reproduction steps;
- proof of concept, when safe;
- expected behavior;
- actual behavior;
- whether repository or persistent state was modified;
- whether rollback succeeded;
- relevant logs, traces, or stack output;
- suggested remediation, when available.

For code-execution issues, also include:

- the operation identifier;
- executor involved;
- input payload;
- permission context;
- filesystem scope;
- process scope;
- whether unrestricted shell execution was reached.

For persistence or knowledge-integrity issues, also include:

- affected storage layer;
- whether provenance was altered;
- whether data was silently overwritten;
- whether corruption persisted after restart;
- whether backup or migration paths were affected.

---

## Scope

Security reports are especially relevant when they involve:

### Execution safety

- arbitrary command execution;
- unrestricted shell access;
- sandbox escape;
- unsafe subprocess use;
- path traversal;
- unauthorized filesystem access;
- operation registry bypass;
- executor boundary bypass;
- unsafe deserialization;
- command, tool, or prompt injection leading to side effects.

### Authorization and autonomy

- privilege escalation;
- approval bypass;
- policy-engine bypass;
- unauthorized operation execution;
- hidden autonomy escalation;
- cross-domain permission leakage;
- agent impersonation;
- token misuse;
- session hijacking.

### Source transformation integrity

- mutation outside the declared scope;
- unsafe refactoring accepted as valid;
- broken reference preservation;
- rollback failure;
- partial repository corruption;
- byte-level restoration failure;
- precondition or postcondition bypass;
- commit-gate bypass.

### Secrets and privacy

- credential leakage;
- secrets stored in logs;
- secrets included in prompts;
- sensitive data sent to unauthorized providers;
- private memory exposure;
- cross-session data leakage;
- cross-user data leakage;
- unsafe export or backup handling.

### Memory and knowledge integrity

- silent fact mutation;
- provenance removal;
- inference promoted to fact without evidence;
- contradiction suppression;
- unauthorized memory modification;
- malicious memory persistence;
- knowledge poisoning;
- stale or invalid knowledge treated as current without traceability.

### Supply chain and extensibility

- malicious plugin execution;
- dependency confusion;
- compromised package handling;
- signature or manifest bypass;
- unsafe plugin permissions;
- extension isolation failure;
- model-provider impersonation;
- integration credential exposure.

### Availability and recovery

- denial of service;
- infinite autonomous loops;
- unbounded retries;
- unrecoverable workflow state;
- migration corruption;
- backup corruption;
- dead-letter or event replay abuse;
- resource-budget bypass.

---

## Out of scope

The following are generally not considered security vulnerabilities unless they produce a concrete security impact:

- feature requests;
- expected limitations already documented;
- unsupported dynamic Python behavior;
- ambiguous static-analysis cases that are rejected before mutation;
- failures requiring full control of the local machine;
- missing hardening in an explicitly development-only configuration;
- denial of service requiring unrealistic resource access;
- reports generated only by automated scanners without a reproducible impact;
- vulnerable dependencies with no reachable impact in CMM OS;
- social engineering directed at maintainers;
- attacks against third-party services outside CMM OS control.

When unsure, report privately and explain the suspected impact.

---

## Disclosure process

After receiving a report, the maintainer will aim to:

1. acknowledge receipt;
2. verify and classify the issue;
3. determine affected versions;
4. define a remediation plan;
5. prepare tests and a fix;
6. validate rollback, compatibility, and migration impact;
7. publish a security advisory when appropriate;
8. release the fix;
9. credit the reporter unless anonymity is requested.

Response times depend on severity and maintainer availability, but critical issues affecting execution boundaries, secrets, permissions, or persistent data will receive priority.

---

## Severity guidance

### Critical

Examples:

- unauthenticated arbitrary code execution;
- unrestricted host command execution;
- secret exfiltration;
- complete authorization bypass;
- destructive mutation outside the declared repository;
- backup or recovery compromise affecting all stored data.

### High

Examples:

- approval bypass for sensitive operations;
- privilege escalation;
- persistent memory poisoning;
- rollback failure causing repository corruption;
- cross-session sensitive-data leakage;
- malicious plugin escape from declared permissions.

### Medium

Examples:

- limited path traversal;
- partial information disclosure;
- denial of service with realistic preconditions;
- unsafe behavior requiring authenticated local access;
- incorrect permission enforcement with constrained impact.

### Low

Examples:

- minor metadata leakage;
- hardening gaps with no direct exploit path;
- verbose error messages exposing non-sensitive internals;
- defense-in-depth improvements.

Final severity may differ based on exploitability, scope, required privileges, reversibility, persistence, and user impact.

---

## Coordinated disclosure

Please allow reasonable time for investigation and remediation before public disclosure.

Do not:

- publish proof-of-concept exploit code before a fix is available;
- access data that does not belong to you;
- modify or delete third-party data;
- degrade services;
- exfiltrate secrets;
- persist access;
- perform destructive testing against public infrastructure.

Good-faith research that respects these limits will be treated constructively.

---

## Security design principles

CMM OS follows these principles:

- least privilege;
- explicit permissions;
- no unrestricted execution by default;
- typed and registered operations;
- validation before trust;
- preconditions before mutation;
- postconditions after mutation;
- rollback whenever technically possible;
- explicit human approval for sensitive actions;
- structured errors;
- auditable side effects;
- provider isolation;
- secrets outside source code;
- local-first privacy;
- versioned contracts;
- recoverable persistent state;
- no silent escalation of autonomy;
- no silent mutation of knowledge.

Contributions that weaken these guarantees require explicit architectural review.

---

## Secure development expectations

Security-sensitive changes should include:

- threat analysis;
- abuse cases;
- permission review;
- input validation;
- negative tests;
- rollback tests;
- concurrency tests when applicable;
- structured logging without secrets;
- migration and compatibility impact;
- documentation of remaining limitations.

Changes involving external input must assume the input may be malicious.

Changes involving model output must never treat generated text as trusted executable intent without contract validation and policy checks.

---

## Dependency security

Dependencies should be:

- necessary;
- actively maintained;
- version constrained where appropriate;
- reviewed for license compatibility;
- scanned for known vulnerabilities;
- isolated behind adapters when provider-specific.

Security updates may be released independently of roadmap phases.

---

## Secrets

Never commit:

- API keys;
- access tokens;
- passwords;
- private keys;
- session cookies;
- production configuration;
- private repository credentials;
- personal or medical data;
- model-provider secrets.

Use environment variables or an approved secrets manager.

Logs, traces, test fixtures, examples, and issue reports must not contain real secrets.

---

## Security updates

Security fixes may include:

- patch releases;
- configuration changes;
- migration steps;
- revoked credentials;
- updated dependencies;
- disabled operations;
- temporary feature restrictions;
- backup verification instructions.

When a vulnerability affects stored state, the advisory should explain whether users must:

- rotate credentials;
- restore a backup;
- reindex technical memory;
- invalidate cached results;
- rebuild containers;
- rerun migrations;
- inspect audit records.

---

## Credit

CMM OS appreciates responsible security research.

Reporters may be credited in:

- the security advisory;
- release notes;
- the changelog;
- a dedicated acknowledgements section.

Anonymous reporting and anonymous credit requests will be respected.
