# Security decisions

Generated from the decision registry; do not edit by hand; regenerated on each run.
Applies to: auth, middleware, anything handling credentials or tokens

### [DEC-BAK-6] Authentication Token Validation on External API Calls

All calls to external LLM providers include authentication tokens (API keys, bearer tokens) validated before use; failed authentication is logged and triggers alerts to detect credential expiry or compromise.

Scope: Applies to Cross-Cutting Security and Async I/O & Concurrency domain (HTTP client configuration). Covers all external API calls to LLM providers and vector databases.
Source: sys_architecture_decisions (system)

### [DEC-BAK-10] Secret Management via Environment Variables with No-Log Enforcement

LLM API keys and authentication tokens are read from environment variables at startup and never logged, included in traces, or exposed in error messages, enforcing zero-exposure of secrets.

Scope: Applies to Cross-Cutting Security (secret management) and Observability Architecture (log sanitization). Covers all API keys, tokens, and credentials; does not apply to non-sensitive configuration.
Source: sys_architecture_decisions (system)

### [DEC-BAK-25] Project-Level Data Isolation via API Key-Based Access Control

Implement data isolation at the project level using LangSmith Hub API keys and access control lists, ensuring single-tenant isolation without requiring application-level multi-tenancy logic. This pattern simplifies security while leveraging platform-provided isolation guarantees.

Scope: Governs data isolation and access control across all prompt templates, examples, and evaluation results. Applies to authentication and authorization for all prompt management operations. Excludes cross-project sharing or multi-tenant scenarios.
Source: sys_architecture_decisions (system)

### [DEC-SEC-2] Structured Access Logging for Audit Trail

All access to agent APIs is logged in structured JSON format with request context (user ID, agent ID, timestamp, result), enabling audit trail and compliance verification.

Scope: Applies to Observability Architecture (logging) and Cross-Cutting Security. Covers all external API access; does not apply to internal function calls.
Source: sys_architecture_decisions (system)

### [DEC-SEC-3] Encryption and Data Masking for Sensitive Data

Enforce encryption of sensitive data in transit (TLS) and at rest, with request/response data masking in audit logs to protect PII and meet 80% security coverage and 70% data privacy requirements.

Scope: Applies to all provider API communication and audit logging within the abstraction layer. Masking rules are configured per domain to identify sensitive field patterns. Encryption applies to all data in transit; at-rest encryption depends on storage backend selection.
Source: sys_architecture_decisions (system)
