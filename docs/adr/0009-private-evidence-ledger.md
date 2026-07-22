# ADR 0009 — Local private evidence ledger

**Status:** Accepted
**Date:** 2026-07-21

## Context

Customer discovery often starts from multiple PRDs, security documents,
workbooks, presentations, and workshop notes. Sending source text directly to
a coding-agent model before classification or approval creates avoidable data
exposure and loses requirement provenance.

## Decision

Document intake stores extracted chunks, hashes, review decisions,
requirements, evidence links, and traceability links in the gitignored
`.accelerator/private/evidence.db` SQLite database.

Every source begins as `local_only`. Agent-facing commands cannot return source
text until the user records `approved_for_model`. Sanitized traceability reports
and draft evidence comments contain requirement/source/chunk IDs rather than
source excerpts, filenames, or headings.

## Consequences

- Multi-document discovery retains provenance and conflict information.
- Local inspection does not imply model disclosure.
- The database is local operational state, not a parallel deployment config.
- Teams needing shared evidence must configure an approved secure store rather
  than commit the local database.
