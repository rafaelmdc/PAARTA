# General Code Cleanup And Refactor Plan

## Summary

This plan restructures the Python codebase around domain boundaries and stable
public entrypoints so the repo is easier to follow, review, and extend.

The goal is not a behavior change. The goal is to split the current monoliths
into smaller modules with clearer ownership while preserving the existing web
surface, import pipeline behavior, and database schema.

## Why This Cleanup Is Needed

The repo has a few clear concentration points where too much logic now lives in
one file:

- `apps/browser/views.py` at 2687 lines
- `apps/imports/services/import_run.py` at 2206 lines
- `apps/imports/services/published_run.py` at 889 lines
- `apps/browser/merged.py` at 845 lines
- `apps/browser/models.py` at 607 lines

Those files mix several kinds of work in one place:

- public entrypoints and internal helpers
- domain logic and shared infrastructure
- orchestration and low-level row writing
- query construction and presentation wiring

That shape now makes navigation, review, and safe edits harder than necessary.

## Refactor Standards

This cleanup should follow the same standards used in mature Django codebases.

### Package By Domain And Responsibility

Split modules by what they are for, not just by file size.

Examples:

- browser list/detail views by browsing domain
- import parsing vs import orchestration vs row writers
- shared pagination/filter/query helpers separated from URL-facing views
- merged analytics separated from raw browser views

### Keep Public Interfaces Stable

Preserve outward behavior while changing internal structure.

The cleanup should keep stable:

- browser route names and URL patterns
- query parameter names
- template paths unless a separate task changes them
- management command flags and command names
- model class names and table mappings
- top-level service exports already used by commands or tests

### Avoid Utility Buckets

Do not replace one monolith with a generic `utils.py` or `helpers.py` dump.

Shared modules should have a narrow reason to exist:

- pagination
- cursor helpers
- filter resolution
- query annotations
- import state management
- import row writers

### Keep Runtime And Tests Aligned

When runtime modules split by domain, tests should follow the same shape.

That keeps failures easier to locate and prevents a new test monolith from
replacing the old runtime monolith.

### Prefer Incremental, Reviewable Steps

Each implementation phase should:

- preserve behavior
- be narrow enough to review safely
- validate the affected subsystem first
- avoid mixing structural cleanup with new features

## Repo-Specific Invariants

The current repo already has important public surfaces that should remain
stable during cleanup.

Stable import surfaces to preserve:

- `apps.browser.views`
- `apps.browser.merged`
- `apps.browser.models`
- `apps.imports.services`
- `apps.imports.services.import_run`
- `apps.imports.services.published_run`

Stable runtime entrypoints to preserve:

- `apps/browser/urls.py`
- `apps/imports/management/commands/import_run.py`
- the browser templates under `templates/browser/`
- the imports templates under `templates/imports/`

Schema and migration rules:

- no migration churn during structural refactors
- `python manage.py makemigrations --check --dry-run` must stay clean
- existing migration files are not rewritten as part of cleanup

## Target Refactor Shape

The cleanup should move the repo toward small packages with stable re-export
surfaces.

Target planning areas:

- `apps/browser/views/`
- `apps/browser/merged/`
- `apps/browser/models/`
- `apps/imports/services/published_run/`
- `apps/imports/services/import_run/`
- a test layout that mirrors those boundaries

The detailed target package map is recorded in
[module-map.md](/home/rafael/Documents/GitHub/homorepeat/docs/cleanup/module-map.md).

## Sequencing Rules

This cleanup should be implemented in this order:

1. write and lock the cleanup docs
2. split browser view foundations
3. split browser domain views
4. split merged browser helpers
5. split published-run parsing
6. split import-run orchestration and row writers
7. split browser models
8. split tests to match runtime structure
9. do a final cleanup pass for duplicate helpers and import hygiene

That order keeps the highest-value monoliths first while avoiding unnecessary
breakage in public entrypoints.

## Definition Of Done

The cleanup program is complete when all of the following are true:

- the largest Python modules are split into smaller packages by responsibility
- public imports and entrypoints remain stable
- no new circular imports are introduced
- no migration diff is produced by structural-only phases
- tests are organized by domain rather than monolithic catch-all files
- each phase has a recorded acceptance result in
  [phases.md](/home/rafael/Documents/GitHub/homorepeat/docs/cleanup/phases.md)

## Non-Goals

This cleanup plan does not itself include:

- new browser features
- schema redesign
- query-performance changes unless a later task explicitly asks for them
- template redesign
- API or URL redesign

Those can happen later, but they should not be mixed into the cleanup program
by default.
