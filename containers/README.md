# Containers

## Purpose

This directory holds the reproducible runtime layers for HomoRepeat.

The current baseline is container-first:
- Docker/Podman for local development and workstations
- Apptainer later for cluster execution

The acquisition image is the first one because the current implementation work is in Slice 0 to 2.

---

## Acquisition image

File:
- `containers/acquisition.Dockerfile`

What it contains:
- Python 3.12
- `taxon-weaver`
- NCBI `datasets`
- NCBI `dataformat`

What it does not contain:
- the taxonomy SQLite database
- downloaded NCBI package caches
- project source code copied into the image

Those are runtime artifacts and should stay outside the image.

---

## Pinning policy

`taxon-weaver` is pinned to:
- ref: `v.0.1.1`
- commit: `aff9709a82ac09fa3f97a71cca809f8e8f98c213`

That matches the currently installed local package metadata used during implementation.

NCBI `datasets` and `dataformat` are installed from NCBI's official v2 Linux AMD64 download endpoints:
- https://www.ncbi.nlm.nih.gov/datasets/docs/v2/command-line-tools/download-and-install/

Important caveat:
- those NCBI binary URLs are rolling endpoints, not immutable release asset URLs
- the Dockerfile is a reproducible recipe for rebuilding the tool layer, but the final reproducible runtime for the pipeline should be the built image tag or digest that Nextflow later pins

So the practical model is:
1. build the image intentionally
2. record the resulting image tag or digest
3. pin that image in the future Nextflow config

---

## Build

Build the acquisition image from the repo root:

```bash
docker build -f containers/acquisition.Dockerfile -t homorepeat-acquisition:0.1 .
```

If you need to override the `taxon-weaver` source ref:

```bash
docker build \
  -f containers/acquisition.Dockerfile \
  --build-arg TAXON_WEAVER_REF=v.0.1.1 \
  --build-arg TAXON_WEAVER_COMMIT=aff9709a82ac09fa3f97a71cca809f8e8f98c213 \
  -t homorepeat-acquisition:0.1 .
```

---

## Smoke checks

Check the core tools inside the built image:

```bash
docker run --rm homorepeat-acquisition:0.1 python --version
docker run --rm homorepeat-acquisition:0.1 taxon-weaver --help
docker run --rm homorepeat-acquisition:0.1 datasets version
docker run --rm homorepeat-acquisition:0.1 dataformat --help
```

---

## Runtime expectations

The acquisition scripts expect the taxonomy DB to be available by path.

Recommended mount pattern:

```bash
docker run --rm \
  -v "$PWD":/work \
  -v "$PWD/cache/taxonomy":/data/taxonomy \
  -w /work \
  homorepeat-acquisition:0.1 \
  python bin/resolve_taxa.py \
  --requested-taxa runs/run_001/planning/requested_taxa.tsv \
  --taxonomy-db /data/taxonomy/ncbi_taxonomy.sqlite \
  --outdir runs/run_001/planning
```

For larger runs, mount an external cache directory as well:

```bash
-v "$PWD/cache/ncbi":/data/ncbi-cache
```

To run the live acquisition smoke check inside the container:

```bash
docker run --rm \
  -v "$PWD":/work \
  -v "$PWD/cache/taxonomy":/data/taxonomy \
  -v "$PWD/cache/ncbi":/data/ncbi-cache \
  -w /work \
  -e TAXONOMY_DB_PATH=/data/taxonomy/ncbi_taxonomy.sqlite \
  -e NCBI_API_KEY="$NCBI_API_KEY" \
  homorepeat-acquisition:0.1 \
  bash scripts/smoke_live_acquisition.sh
```

---

## Why this layer exists now

The repo does not have the Nextflow orchestration layer yet.
So the immediate goal is not process-level container wiring.

The immediate goal is:
- lock the external toolchain
- stop Slice 2 from depending on an undocumented local machine setup
- make the later Nextflow container binding straightforward
