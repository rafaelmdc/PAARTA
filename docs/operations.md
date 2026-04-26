# Operations

## Management Commands

Migrate:

```bash
python3 manage.py migrate
```

Import a published run:

```bash
python3 manage.py import_run --publish-root /absolute/path/to/<run>/publish
```

The supported published-run import surface is publish contract v2. The manifest
at `metadata/run_manifest.json` must include `publish_contract_version: 2`.
The required v2 public files are `calls/repeat_calls.tsv`,
`calls/run_params.tsv`, the run-level TSVs under `tables/`, run summaries under
`summaries/`, and the manifest under `metadata/`.

The v2 importer does not read the older public `acquisition/`, `status/`,
`calls/finalized/`, `cds.fna`, or `proteins.faa` paths. Full sequence/protein
bodies must be present in the matched TSV columns:
`matched_sequences.tsv.nucleotide_sequence` and
`matched_proteins.tsv.amino_acid_sequence`.

Process the oldest queued import:

```bash
python3 manage.py import_run --next-pending
```

Rebuild canonical browser metadata:

```bash
python3 manage.py backfill_canonical_catalog
python3 manage.py backfill_browser_metadata
```

Rebuild codon rollups:

```bash
python3 manage.py backfill_codon_composition_summaries
python3 manage.py backfill_codon_composition_length_summaries
```

In Compose, prefix commands with:

```bash
docker compose exec web
```

## Import and Rollup Maintenance

The canonical catalog sync path rebuilds:

- canonical codon composition summaries
- canonical codon composition by length summaries
- canonical protein repeat-call counts

If codon share values in an unfiltered view do not match a filtered/branch view,
first rebuild the relevant rollup table and then compare against live
aggregation. Unfiltered views are the ones most likely to use rollups.

For codon-by-length summaries, shares for a complete selected residue codon set
should sum to 1 within each taxon/bin, aside from rounding. If they do not,
check for:

- stale rollup rows
- denominator bugs that count codon-usage rows instead of distinct repeat calls
- incomplete or invalid imported codon fractions

## Cache Behavior

Stats bundles and taxonomy gutter payloads are cached using a hash of validated
filter state. Cache TTL comes from `HOMOREPEAT_BROWSER_STATS_CACHE_TTL`, default
60 seconds.

Taxonomy gutter payloads also include a local cache version in
`apps/browser/stats/taxonomy_gutter.py`. Bump it when changing payload shape or
alignment semantics.

## Validation Checklist

Before merging statistical or chart changes:

```bash
python3 manage.py test web_tests.test_browser_stats
python3 manage.py test web_tests.test_browser_lengths
python3 manage.py test web_tests.test_browser_codon_ratios
python3 manage.py test web_tests.test_browser_codon_composition_lengths
```

For frontend chart changes:

```bash
node --check static/js/stats-chart-shell.js
node --check static/js/taxonomy-gutter.js
node --check static/js/pairwise-overview.js
node --check static/js/repeat-length-explorer.js
node --check static/js/repeat-codon-ratio-explorer.js
node --check static/js/codon-composition-length-explorer.js
```

Manual browser checks should cover:

- unfiltered and branch-scoped routes
- two-codon and multi-codon residues
- y-axis wheel pan and Shift+wheel zoom
- horizontal x-axis sliders where present
- taxonomy gutter alignment after zoom
- no-JS fallback tables where relevant

## Database Notes

PostgreSQL is the production-like path. Large publish contract v2 imports should
use PostgreSQL because run-level TSVs are streamed into temporary tables with
`COPY` and joined in SQL. SQLite remains useful for compact local fixtures and
parser checks, but it does not exercise the production staging path or
PostgreSQL-specific SQL rollup paths.

When changing raw SQL rollups, validate both:

- PostgreSQL rebuild command in the Compose stack
- Django tests using the Python/live fallback semantics

For a real v2 import validation, run:

```bash
docker compose exec web python manage.py import_run \
  --publish-root /workspace/homorepeat_pipeline/runs/<run-id>/publish
```

Then compare source table row counts against imported raw counts for repeat
calls, matched sequences, matched proteins, repeat-call codon usage, repeat
context, and operational tables. Also confirm canonical sequence/protein bodies
are populated after sync and codon rollups rebuild successfully.

## Documentation Rules

Keep evergreen documentation in:

- `docs/usage.md`
- `docs/architecture.md`
- `docs/statistics.md`
- `docs/operations.md`

Keep dated handoff notes in `docs/journal/`.

Do not add new long-lived implementation-plan folders unless they describe a
current architectural contract. Temporary plans should be converted into a
session log or deleted after implementation.
