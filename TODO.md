# Product TODO

## Phase 1 — Project workspace MVP

- [x] Create a project list, project workspace routes, and project overview page.
- [x] Manage project-scoped Mapping versions and restore a version to draft.
- [x] After a successful build, guide the user to that project's graph view.
- [x] Show graph node/relationship counts, source details, and build history on project overview.
- [x] Show unpublished Mapping draft changes clearly.
- [ ] Record the Mapping version used by every build job and display it in history.
- [x] Disable and delete source profiles within a project.
- [ ] Edit source profile names and connection settings within a project.
- [ ] Import legacy example mappings into a newly created project.

## Phase 2 — Reliable ingestion for daily use

- [x] Validate Mapping fields, keys, and relationship targets before a build starts.
- [x] Preview entities, relationships, and expected row counts before a build.
- [x] Support full rebuild and safe incremental ingestion.
- [x] Report incremental created, updated, unchanged, and skipped node counts.
- [ ] Allow build-job cancellation and retry with preserved error logs.
- [x] Report data-quality samples for null keys, unmatched relations, and skipped rows.
- [ ] Detect and report duplicate source keys.
- [x] Detect source-deletion cleanup candidates without automatic deletion.
- [ ] Build a cleanup-candidate UI for source rows removed from an incremental sync.
- [ ] Allow users to mark selected cleanup candidates inactive while retaining graph history.
- [ ] Add audited, double-confirmed permanent deletion for selected cleanup candidates.
- [ ] Show incremental job summaries and cleanup candidates in project build history.
- [ ] Add automated integration tests: SQLite → Mapping → Neo4j → project-isolated query.

## Phase 3 — General-purpose data and Mapping support

- [ ] Implement PostgreSQL, MySQL, and Google Sheets source adapters.
- [ ] Separate source credentials from Mapping definitions.
- [ ] Support property-to-property relation matching, not only ID foreign keys.
- [ ] Ingest multiple sources into one project.
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
