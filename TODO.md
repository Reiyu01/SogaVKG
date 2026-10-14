# Product TODO

## Phase 1 — Project workspace MVP

- [x] Create a project list, project workspace routes, and project overview page.
- [x] Manage project-scoped Mapping versions and restore a version to draft.
- [x] After a successful build, guide the user to that project's graph view.
- [x] Show graph node/relationship counts, source details, and build history on project overview.
- [x] Show unpublished Mapping draft changes clearly.
- [x] Record the Mapping version used by every build job and display it in history.
- [x] Disable and delete source profiles within a project.
- [x] Edit source profile names and connection settings within a project.
- [x] Import legacy example mappings into a newly created project.

## Phase 2 — Reliable ingestion for daily use

- [x] Validate Mapping fields, keys, and relationship targets before a build starts.
- [x] Preview entities, relationships, and expected row counts before a build.
- [x] Support full rebuild and safe incremental ingestion.
- [x] Report incremental created, updated, unchanged, and skipped node counts.
- [ ] Allow build-job cancellation and retry with preserved error logs.
- [x] Report data-quality samples for null keys, unmatched relations, and skipped rows.
- [x] Detect and report duplicate source keys.
- [x] Detect source-deletion cleanup candidates without automatic deletion.
- [ ] Build a cleanup-candidate UI for source rows removed from an incremental sync.
- [ ] Allow users to mark selected cleanup candidates inactive while retaining graph history.
- [ ] Add audited, double-confirmed permanent deletion for selected cleanup candidates.
- [ ] Show incremental job summaries and cleanup candidates in project build history.
- [x] Add automated integration tests: SQLite → Mapping → read-only graph projection → project-isolated query.

## Phase 3 — General-purpose data and Mapping support

- [x] Add PostgreSQL source-profile configuration and schema adapter foundation.
- [x] Complete PostgreSQL graph projection and single-Entity query support.
  - [x] Resolve source profiles through `SourceAdapter` by `source_type`.
  - [x] Remove direct SQLite connections from projection and query services.
  - [x] Support PostgreSQL graph records and relation expansion.
  - [x] Return an explicit error for unsupported cross-source SQL joins.
  - [x] Add PostgreSQL adapter contract and integration tests.
- [ ] Add PostgreSQL source-profile editing and connection-test feedback.
- [x] Implement Google Sheets source adapter.
- [ ] Implement MySQL source adapter.
- [ ] Separate source credentials from Mapping definitions.
- [ ] Support property-to-property relation matching, not only ID foreign keys.
- [ ] Build production-grade federated cross-source querying without mixing source data.
  - [ ] Move relation join rules from free-form Mapping YAML into a validated, versioned repository model.
  - [ ] Define restricted `SourceAdapter` query capabilities: projected columns, filters, batched key lookup, pagination, row estimates, and limits.
  - [ ] Add a `SemanticQueryPlanner` that produces bounded, project-scoped query plans and selects the filtered side first.
    - [x] Define a Mapping-constrained query-plan DSL: entity projections, approved filters, published relation-rule key handoffs, bounded pagination, and no raw SQL.
    - [x] Support static plans: the LLM proposes a complete multi-step plan, then the planner validates and executes it with bounded key handoffs. (Cost-based reordering remains pending.)
    - [ ] Add cost estimation for candidate start points using source row estimates, filter selectivity, key cardinality, and relation direction; reject plans that cannot fit policy budgets.
    - [ ] Add deterministic plan rewriting/reordering: choose the lowest-cardinality valid filtered side first, or return an explicit request for narrower filters.
    - [ ] Support adaptive plans: after each bounded source lookup, provide only key counts and approved summaries to choose the next step; enforce maximum hops (3–5), cycle detection, and total budget.
    - [ ] Add an adaptive execution loop that validates every follow-up LLM step against the same DSL and stops on empty results, policy exhaustion, duplicate/cyclic paths, or a completed answer.
    - [ ] Implement the hybrid orchestration mode: start from an LLM candidate plan, validate/rewrite it deterministically, and request a follow-up step only when intermediate cardinality materially changes the plan.
    - [ ] Validate every LLM-proposed step against project Mapping, field permissions, relation-rule direction, allowed operators, source availability, cycle detection, and data/key/result/time budgets.
    - [ ] Audit both the LLM candidate plan and the final executed plan, including per-step source, cardinality, rule/version lineage, rewrites, and policy rejections.
  - [ ] Add a `FederatedJoinExecutor` for Mapping-approved one-hop joins with parameterized source subqueries.
    - [x] First slice: bounded one-hop equality join over the restricted adapter contract, with source lineage.
  - [ ] Return field-level source provenance, join-rule version, and Mapping version for every federated result.
  - [ ] Enforce per-source timeouts, row/key/result limits, memory budgets, and explicit errors when a plan exceeds policy.
    - [x] First slice: join-key/source-row/result-row limits and an overall executor time budget.
  - [ ] Add query audit events with plan summary, source set, Mapping version, counts, duration, and failures; never store credentials.
    - [x] First slice: persist query kind, Mapping version, Entity lineage, plan summary, counts, duration, and errors.
  - [ ] Add real SQLite + PostgreSQL end-to-end integration tests; use Google Sheets only for bounded lookup/cache test cases.
    - [x] Acceptance baseline: two independent SQLite source profiles → Mapping resolution → adapter lookup → federated join → lineage result.
  - [ ] Add a materialized read-model option for approved high-volume or high-frequency federated queries.
- [x] Ingest multiple SQLite sources into one project.
- [ ] Support concept-level Identity Mapping across source-backed data models.
  - [x] Persist project-scoped entity alignments with source/target matching columns.
  - [x] Expose `CONCEPT_EQUIVALENT_TO` edges in the conceptual graph and LLM schema description.
  - [x] Preserve existing entity mappings when a later source-backed model is added to a project.
  - [x] Add a project UI to create, review, and remove Identity Mappings such as `GoogleSheetAsset.asset_code ↔ Asset.asset_code`.
  - [x] Preview exact matches, unmatched keys, null keys, and duplicate keys before publishing an Identity Mapping.
  - [x] Validate identity cardinality (default one-to-one); block publishing when either side has duplicate non-empty keys.
  - [x] Allow an explicit normalization rule for safe keys.
  - [x] Make AI semantic queries optionally expand aligned concepts at query time without materializing instance-to-instance identity edges.
  - [x] Return both source records and field-conflict provenance when an LLM query follows an Identity Mapping.
  - [x] Add audit history and Mapping-version snapshots for Identity Mapping changes.
- [ ] Provide Mapping templates for common domains.

## Phase 4 — Production operation and governance

- [ ] Add users, organizations, project roles, and authorization checks.
- [ ] Record query audit trails, source lineage, and AI-query history.
- [ ] Provision one isolated Neo4j database per project and route all project operations to it.
- [ ] Replace in-process background jobs with a persistent asynchronous worker and queue.
- [ ] Add Docker Compose/deployment configuration, health monitoring, backup, and restore procedures.
- [ ] Add API rate limiting, credential management, encryption, and data-retention/deletion policies.

## Project isolation before production

- [ ] **One Neo4j database per project.** Provision a dedicated Neo4j database when a project is created, store its database identifier with the project, and route all ingestion, graph exploration, and query execution through that database.
- [ ] Add project deletion/archival rules that preserve or explicitly remove the associated Neo4j database.
- [ ] Add per-project Neo4j credentials or least-privilege access controls.
- [ ] Add migration tooling from the development shared database to project-specific databases.

## Project model

- [x] Scope mappings, sources, and build jobs to a project.
- [x] Create immutable Mapping-version snapshots at build time.
- [x] Require a selected project for graph and AI-query APIs.
