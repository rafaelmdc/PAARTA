# HomoRepeat

Monorepo for the HomoRepeat workflow core and the future web frontend.

Current workflow baseline:
- accession-driven acquisition from NCBI RefSeq packages
- `pure` and `threshold` detection methods
- codon attachment from normalized CDS
- SQLite build from flat contracts
- canonical merged `repeat_calls.tsv`
- report JSON plus an offline-capable ECharts HTML bundle

## Repo layout

- `apps/pipeline/`: Nextflow workflow, configs, and operator scripts
- `apps/web/`: reserved Django scaffold for the future frontend
- `src/homorepeat/`: shared Python package used by CLI tasks and future app code
- `examples/`: checked-in example inputs and params
- `runs/`: published run roots
- `runtime/cache/`: runtime caches such as taxonomy DBs
- `tests/`: unit and CLI coverage for the package-backed workflow logic

## Quick start

1. Install the local package into the Python interpreter that will run wrappers and tests:

```bash
python3 -m pip install -e .
```

2. Build the local development images:

```bash
bash apps/pipeline/scripts/build_dev_containers.sh
```

3. Confirm the taxonomy DB exists:

```bash
ls runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

4. Run the pipeline on the checked-in smoke accession list:

```bash
HOMOREPEAT_PHASE4_PROFILE=docker \
bash apps/pipeline/scripts/run_phase4_pipeline.sh examples/accessions/smoke_human.txt
```

That creates one timestamped run root under `runs/`.
The wrapper updates `runs/latest` on success and writes a published run manifest under `publish/manifest/run_manifest.json`.

To use a checked-in params example:

```bash
HOMOREPEAT_PHASE4_PROFILE=docker \
HOMOREPEAT_PARAMS_FILE=examples/params/smoke_default.json \
bash apps/pipeline/scripts/run_phase4_pipeline.sh examples/accessions/smoke_human.txt
```

## Compose stack

The repo root now includes [compose.yaml](/home/rafael/Documents/GitHub/homorepeat/compose.yaml) for local container orchestration.

Use it to start the Django dev app plus Postgres:

```bash
docker compose up web postgres
```

Use it to build the pipeline images expected by the Nextflow `docker` profile:

```bash
docker compose build pipeline-acquisition pipeline-detection
```

Current services:
- `postgres`: development PostgreSQL for the future Django app
- `web`: Django development server from `apps/web`
- `pipeline-acquisition`: build target for the acquisition runtime image
- `pipeline-detection`: build target for the detection runtime image

## Verified smoke

Verified on April 6, 2026:
- `docker compose build web pipeline-acquisition pipeline-detection` completed successfully
- `docker compose up web postgres` started the Django and Postgres stack successfully
- `curl http://127.0.0.1:8000/` returned the web health response
- the Nextflow wrapper completed successfully with the `docker` profile on `examples/accessions/smoke_human.txt`

Latest verified run:
- `runs/phase4_pipeline_2026-04-06_12-03-46Z`
- `runs/latest` points to that run
- published manifest: `publish/manifest/run_manifest.json`

## Direct Nextflow run

If you prefer the raw `nextflow run` entrypoint:

```bash
nextflow run apps/pipeline \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt \
  --taxonomy_db runtime/cache/taxonomy/ncbi_taxonomy.sqlite \
  --run_root runs/manual_smoke \
  --output_dir runs/manual_smoke/publish \
  -params-file examples/params/smoke_default.json
```

## Main outputs

A successful run publishes these stable artifacts under `runs/<run_id>/publish/`:
- `acquisition/genomes.tsv`
- `acquisition/taxonomy.tsv`
- `acquisition/sequences.tsv`
- `acquisition/proteins.tsv`
- `calls/repeat_calls.tsv`
- `calls/run_params.tsv`
- `calls/by_method/`
- `database/sqlite/homorepeat.sqlite`
- `reports/summary_by_taxon.tsv`
- `reports/regression_input.tsv`
- `reports/echarts_options.json`
- `reports/echarts_report.html`
- `reports/echarts.min.js`
- `manifest/run_manifest.json`

Internal execution artifacts are written under `runs/<run_id>/internal/`:
- `internal/planning/`
- `internal/nextflow/nextflow.log`
- `internal/nextflow/trace.txt`
- `publish/reports/nextflow_report.html`
- `publish/reports/nextflow_timeline.html`
- `publish/reports/nextflow_dag.html`

## Runtime profiles

Recommended:
- `docker`

Available:
- `local`

`local` assumes the host already has the required CLI toolchain.
`docker` is the validated path for reproducible runs.
Both profiles expect the selected Python interpreter to have `homorepeat` installed.
The `docker` profile expects the local image tags `homorepeat-acquisition:dev` and `homorepeat-detection:dev`, which can be built through Compose or the helper script.

## Repo entrypoints

Primary workflow files:
- `apps/pipeline/main.nf`
- `apps/pipeline/nextflow.config`
- `apps/pipeline/conf/base.config`
- `apps/pipeline/conf/docker.config`
- `apps/pipeline/conf/local.config`

Primary helper scripts:
- `apps/pipeline/scripts/build_dev_containers.sh`
- `apps/pipeline/scripts/run_phase4_pipeline.sh`
- `apps/pipeline/scripts/smoke_live_acquisition.sh`
- `apps/pipeline/scripts/smoke_live_detection.sh`

Python package entrypoint:
- `src/homorepeat/`

## Key docs

Core:
- [architecture](docs/architecture.md)
- [contracts](docs/contracts.md)
- [methods](docs/methods.md)
- [roadmap](docs/roadmap.md)
- [operations](docs/operations.md)
