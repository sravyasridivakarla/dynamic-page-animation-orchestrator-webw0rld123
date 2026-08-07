# Infrastructure decisions

Generated from the decision registry; do not edit by hand; regenerated on each run.
Applies to: Dockerfile, docker-compose*, deploy/, infra/

### [DEC-DAT-10] Single-Region Deployment with Managed Failover

Deploy Azure AI Search in a single primary region with managed failover and backup, deferring multi-region replication to future scaling phases. This minimizes operational complexity and cost for small-project scale while maintaining 98% availability SLA.

Scope: Governs Azure AI Search deployment topology and disaster recovery strategy. Applies to all vector index and embedding infrastructure. Exception: if multi-region latency requirements emerge, upgrade to multi-region replica strategy.
Source: sys_architecture_decisions (system)

### [DEC-INF-3] Provider Health Monitoring and SLA Tracking

Implement continuous health monitoring for all providers with periodic probes and SLA compliance tracking. Health metrics feed circuit breaker decisions and inform provider selection logic.

Scope: Governs provider health assessment and SLA tracking for all integrated providers (Anthropic Claude primary, fallback providers). Health checks are independent of application request traffic. SLA tracking is per-provider with composite availability calculated across all providers.
Source: sys_architecture_decisions (system)
