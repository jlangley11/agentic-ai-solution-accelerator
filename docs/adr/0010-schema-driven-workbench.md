# ADR 0010 — Schema-driven customer workbench

**Status:** Accepted
**Date:** 2026-07-21

## Context

The original frontend manually mirrored the sales request, response sections,
endpoint, and worker topology. Reusing it for another customer scenario
required editing TypeScript in several places and risked showing unvalidated
streaming model fragments.

## Decision

Scenarios may declare a response schema and experience metadata in
`accelerator.yaml`. `GET /scenario/metadata` exposes request/response JSON
Schema, the endpoint, agents, output sections, and approval mode.

The reference frontend preserves the tailored sales experience and provides a
generic workbench for other scenarios. Generic results render only validated
`partial` events and final briefings; raw `chunk` events are ignored.

HITL remains external and fail-closed. The workbench displays pending actions
but does not create an alternate approval bypass.

## Consequences

- New scenarios receive a usable form-and-report experience from their schemas.
- Tailored layouts can coexist with generic rendering.
- Browser history is demo-only; production identity and durable storage remain
  customer deployment adapters.
