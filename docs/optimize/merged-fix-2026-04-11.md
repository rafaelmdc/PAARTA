# Merged Fix Notes

Date: 2026-04-11

## Scope

This note records why merged browser mode is not part of the raw-browser
optimization pass on `rehaul`.

The raw browser and the merged browser do not fail for the same reason. The raw
browser is dominated by hot ordered queries and repeated page-chrome work.
Merged mode is dominated by Python-side materialization and in-memory grouping.

## Current Failure Mode

`apps/browser/merged.py` still loads large raw repeat-call sets into Python with
`list(...)` and then groups them in memory for:

- accession summaries
- merged protein groups
- merged repeat-call groups
- accession analytics

That design scales with raw row count, not with the number of rows actually
rendered on screen.

## What Will Not Fix It

These changes may help raw mode but do not solve merged mode:

- trimming a few selected columns
- removing one or two joins
- adding a couple more browse indexes
- making fragment payloads smaller

Those changes reduce overhead, but they do not change the fact that merged mode
still materializes too much raw data in process memory.

## Required Direction

If merged mode needs to scale, it must stop depending on Python-side
materialization of large repeat-call querysets.

The realistic options are:

1. database-first aggregation queries for the merged views
2. persisted merged summary tables built at import time
3. materialized rollups refreshed during import/update workflows

Any acceptable redesign must keep memory bounded relative to the requested page,
not the full raw repeat-call dataset.

## Planning Rule

For the current optimization pass:

- raw/run-mode optimization is the active target
- merged mode is not part of raw-browser acceptance criteria
- merged redesign gets its own profiling and execution plan later
