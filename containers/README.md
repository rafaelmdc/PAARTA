# Containers

## Purpose

This directory holds the reproducible runtime layers for HomoRepeat.

The current baseline is container-first:
- Docker/Podman for local development and workstations
- Apptainer later for cluster execution

The runtime is split by process class where the toolchains are materially different.

Current images:
- acquisition
- detection

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

## Detection image

File:
- `containers/detection.Dockerfile`

What it contains:
- Python 3.12
- `diamond`

What it does not contain:
- `taxon-weaver`
- NCBI `datasets`
- project source code copied into the image

This split is intentional.
Acquisition and detection have different external toolchains, and later Nextflow process labels should be able to pin different images without carrying unnecessary binaries into every task.

---

## Pinning policy

`taxon-weaver` is pinned to:
- ref: `v.0.1.1`
- commit: `aff9709a82ac09fa3f97a71cca809f8e8f98c213`

That matches the currently installed local package metadata used during implementation.

NCBI `datasets` and `dataformat` are installed from NCBI's official v2 Linux AMD64 download endpoints:
- https://www.ncbi.nlm.nih.gov/datasets/docs/v2/command-line-tools/download-and-install/

`diamond` is installed from the official GitHub release archive for the pinned version:
- https://github.com/bbuchfink/diamond/releases

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

Build the detection image from the repo root:

```bash
docker build -f containers/detection.Dockerfile -t homorepeat-detection:0.1 .
```

If you need to override the pinned DIAMOND version:

```bash
docker build \
  -f containers/detection.Dockerfile \
  --build-arg DIAMOND_VERSION=2.1.15 \
  --build-arg DIAMOND_ARCHIVE_URL=https://github.com/bbuchfink/diamond/releases/download/v2.1.15/diamond-linux64.tar.gz \
  -t homorepeat-detection:0.1 .
```

---

## Smoke checks

Check the core tools inside the built image:

```bash
docker run --rm homorepeat-acquisition:0.1 python --version
docker run --rm homorepeat-acquisition:0.1 taxon-weaver --help
docker run --rm homorepeat-acquisition:0.1 datasets version
docker run --rm homorepeat-acquisition:0.1 dataformat --help
docker run --rm homorepeat-detection:0.1 diamond version
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

To run similarity detection with DIAMOND inside the detection image:

```bash
docker run --rm \
  -v "$PWD":/work \
  -w /work \
  homorepeat-detection:0.1 \
  python bin/detect_blast.py \
  --proteins-tsv runs/run_001/merged/acquisition/proteins.tsv \
  --proteins-fasta runs/run_001/merged/acquisition/proteins.faa \
  --repeat-residue Q \
  --backend diamond_blastp \
  --outdir runs/run_001/merged/detection/blast_q
```

---

## Why this layer exists now

The repo does not have the Nextflow orchestration layer yet.
So the immediate goal is not process-level container wiring.

The immediate goal is:
- lock the external toolchains
- keep acquisition and detection dependencies separate
- stop implementation from depending on an undocumented local machine setup
- make the later Nextflow per-process container binding straightforward
