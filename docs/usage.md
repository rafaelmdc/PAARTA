# Usage

This guide is for running PAARTA locally, loading PAASTA output, browsing the
imported data, and downloading results.

## Start PAARTA

Copy the example environment file and start the Docker stack:

```bash
cp .env.example .env
docker compose up --build
```

The first run builds the image and applies database migrations. When the stack
is ready, open:

```text
http://localhost:8000
```

On later starts:

```bash
docker compose up
```

The main services are:

| Service | URL or role |
|---------|-------------|
| Web app | `http://localhost:8000` |
| Import page | `http://localhost:8000/imports/` |
| Import history | `http://localhost:8000/imports/history/` |
| PostgreSQL | local port `5432` |
| Celery workers | uploads, imports, graph warmup, and downloads |

## Local Trusted Mode

The import page and admin/status pages normally require a Django staff login.
For a single-user local workstation, you can skip login by setting this in
`.env`:

```bash
no_admin=1
```

Use this only when the app is not exposed to a network. With `no_admin=1`, every
web visitor receives staff/admin permissions.

## What PAARTA Imports

PAARTA imports published PAASTA runs. PAASTA runs the pipeline; PAARTA reads the
published output and stores it in the database for browsing.

Normal browser pages read from the database. They do not read pipeline files at
request time.

The supported format is publish contract v2. A valid run has a `publish/`
directory like this:

```text
publish/
  calls/
    repeat_calls.tsv
    run_params.tsv
  tables/
    genomes.tsv
    taxonomy.tsv
    matched_sequences.tsv
    matched_proteins.tsv
    repeat_call_codon_usage.tsv
    repeat_context.tsv
    download_manifest.tsv
    normalization_warnings.tsv
    accession_status.tsv
    accession_call_counts.tsv
  summaries/
    status_summary.json
    acquisition_validation.json
  metadata/
    run_manifest.json
```

`metadata/run_manifest.json` must include:

```json
{
  "publish_contract_version": 2
}
```

## Choose an Import Method

For most local users, the easiest path is **browser upload**. Use mounted runs
for very large outputs or shared server storage. Use the command line for
automation.

| Situation | Best method |
|-----------|-------------|
| You have a zipped run on your computer | Browser upload |
| The run folder is already on the Docker host | Mounted run import |
| You are scripting imports | Command-line import |
| The output is very large and uncompressed | Mounted run import |

## Method 1: Browser Upload for Zipped Runs

Use this when you have a zipped PAASTA run and want to load it from the browser.

1. Create a zip file containing exactly one
   `publish/metadata/run_manifest.json`.
2. Open `http://localhost:8000/imports/`.
3. Choose the zip file in the upload form.
4. Wait for the uploaded run to reach **Ready**.
5. Click **Import**.
6. Watch progress on `/imports/` or `/imports/history/`.

The zip can contain `publish/` at the top level:

```text
publish/
  metadata/
    run_manifest.json
  ...
```

It can also contain one parent folder:

```text
my-run/
  publish/
    metadata/
      run_manifest.json
    ...
```

It must not contain multiple `publish/metadata/run_manifest.json` files.

### Upload Limits and Safety

By default, zipped uploads are limited to 5 GB:

```text
HOMOREPEAT_UPLOAD_MAX_ZIP_BYTES=5368709120
```

Uploads are chunked in the browser, checked with SHA-256 per chunk, and
resumable after a browser refresh or network interruption. After upload, a
background worker assembles the zip, extracts it safely, validates the publish
contract, and copies the accepted run into:

```text
/data/imports/library/<run-id>/publish
```

The extraction step rejects invalid zips, absolute paths, `..` traversal,
symlinks, special files, too many files, and excessive extracted size.

Uploaded zips are validated for path and size safety, but they are not malware
scanned. For internet-facing or untrusted-user deployments, use HTTPS, a trusted
reverse proxy, quotas, and malware scanning before accepting uploads.

### Resume and Recovery

If the browser closes during upload, reopen `/imports/` in the same browser
session and choose the same file. PAARTA asks the server which chunks were
accepted and resumes from the missing chunks.

If extraction fails:

| Button | Use when |
|--------|----------|
| **Retry** | The source zip is intact and the failure was likely temporary, such as a worker restart or temporary disk issue. |
| **Clear files** | The upload is not recoverable, such as a checksum mismatch, corrupt zip, or invalid publish contract. |

Ready and imported library data is not removed by automatic upload cleanup.
Cleanup only removes stale upload working files.

## Method 2: Mounted Run Import

Use this when PAASTA run folders are already on the machine running Docker.

Edit `.env`:

```bash
HOMOREPEAT_RUNS_ROOT=/path/to/paasta/runs
```

Recreate or start the stack so Docker receives the mount:

```bash
docker compose up -d
```

Then open:

```text
http://localhost:8000/imports/
```

PAARTA scans `HOMOREPEAT_RUNS_ROOT` for published runs. Select a detected run,
queue the import, and monitor progress on the same page.

Inside the containers, the mounted directory is available at:

```text
/workspace/homorepeat_pipeline/runs
```

## Method 3: Command-Line Import

Use this for scripted imports or administrative work:

```bash
docker compose exec web python manage.py import_run \
  --publish-root /workspace/homorepeat_pipeline/runs/<run-id>/publish
```

To process the oldest queued import manually:

```bash
docker compose exec web python manage.py import_run --next-pending
```

For any other management command:

```bash
docker compose exec web python manage.py <command>
```

## Import Status

The import pages show both upload status and database import status.

Common upload states:

| Status | Meaning |
|--------|---------|
| Receiving | Browser chunks are still being uploaded. |
| Received | All chunks are present; extraction is waiting or about to start. |
| Extracting | The upload worker is assembling and validating the zip. |
| Ready | The run was validated and can be imported. |
| Queued | The database import has been queued. |
| Imported | The linked import completed. |
| Failed | Upload, extraction, validation, or import failed. Check the shown error. |

## Disk Space for Uploads

Plan for temporary working space during zipped uploads. PAARTA needs room for
chunk files, the assembled zip, extracted files, and the final validated library
copy.

A conservative estimate per upload in flight is:

```text
2 x zip size + 2 x estimated extracted size + 1 GiB
```

With the default extraction estimate of `zip size x 3`, plan for about:

```text
zip size x 8 + 1 GiB
```

The disk preflight check is enabled by default and rejects uploads or
extractions that would leave less than:

```text
HOMOREPEAT_UPLOAD_MIN_FREE_BYTES=1073741824
```

For very large uncompressed outputs, prefer mounted run imports.

## Browse and Download Data

After an import completes, use these pages:

| URL | Description |
|-----|-------------|
| `/browser/homorepeats/` | Main homorepeat table: organism, assembly, gene, repeat type, architecture, length, purity, and position |
| `/browser/codon-usage/` | Per-repeat codon usage profiles |
| `/browser/lengths/` | Repeat-length distributions by taxonomy |
| `/browser/codon-ratios/` | Residue-scoped codon composition |
| `/browser/codon-composition-length/` | Codon composition across repeat-length bins |
| `/browser/runs/` | Imported runs and provenance |
| `/browser/accessions/`, `/browser/genomes/`, `/browser/sequences/`, `/browser/proteins/`, `/browser/calls/` | Supporting catalog browsers |
| `/browser/warnings/`, `/browser/accession-status/`, `/browser/accession-call-counts/`, `/browser/download-manifest/` | Operational provenance tables |

Most tables support:

- search
- column filters
- sorting
- TSV download with `?download=tsv`

The homorepeat table also supports:

```text
?download=aa_fasta
?download=dna_fasta
```

## Developer Checks

Most users do not need these. They are useful when changing PAARTA code.

Run all tests:

```bash
python3 manage.py test web_tests
```

Run focused test modules:

```bash
python3 manage.py test web_tests.test_browser_stats
python3 manage.py test web_tests.test_browser_lengths
python3 manage.py test web_tests.test_browser_codon_ratios
python3 manage.py test web_tests.test_browser_codon_composition_lengths
python3 manage.py test web_tests.test_import_uploads
python3 manage.py test web_tests.test_import_tasks
```

Check JavaScript syntax:

```bash
node --check static/js/stats-chart-shell.js
node --check static/js/pairwise-overview.js
node --check static/js/taxonomy-gutter.js
node --check static/js/repeat-length-explorer.js
node --check static/js/repeat-codon-ratio-explorer.js
node --check static/js/codon-composition-length-explorer.js
```
