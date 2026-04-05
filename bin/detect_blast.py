#!/usr/bin/env python3
"""Detect similarity-style repeat tracts from canonical protein inputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.detect_blast import (  # noqa: E402
    find_diamond_blastp_tracts,
    find_template_local_tracts,
    format_similarity_score,
)
from lib.fasta_io import read_fasta  # noqa: E402
from lib.repeat_features import CALL_FIELDNAMES, build_call_row  # noqa: E402
from lib.run_params import write_run_params  # noqa: E402
from lib.tsv_io import ContractError, read_tsv, write_tsv  # noqa: E402


PROTEINS_REQUIRED = [
    "protein_id",
    "sequence_id",
    "genome_id",
    "protein_name",
    "protein_length",
    "protein_path",
    "taxon_id",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proteins-tsv", required=True, help="Path to canonical proteins.tsv")
    parser.add_argument("--proteins-fasta", required=True, help="Path to canonical proteins.faa")
    parser.add_argument("--repeat-residue", required=True, help="Target amino-acid residue")
    parser.add_argument(
        "--backend",
        required=True,
        choices=["template_local", "diamond_blastp"],
        help="Similarity backend identity",
    )
    parser.add_argument("--outdir", required=True, help="Output directory for blast-like detection artifacts")
    parser.add_argument("--template-length", type=int, default=10, help="Fallback template length")
    parser.add_argument("--match-score", type=int, default=2, help="Fallback match score")
    parser.add_argument("--mismatch-score", type=int, default=-1, help="Fallback mismatch score")
    parser.add_argument("--min-repeat-count", type=int, default=6, help="Minimum target-residue count")
    parser.add_argument(
        "--merge-gap-max",
        type=int,
        help="Optional maximum gap length for merging positive fallback hits",
    )
    parser.add_argument("--diamond-bin", default="diamond", help="Path to the DIAMOND executable")
    parser.add_argument(
        "--diamond-evalue",
        type=float,
        default=1000.0,
        help="E-value cutoff for diamond blastp",
    )
    parser.add_argument(
        "--diamond-max-target-seqs",
        type=int,
        help="Optional DIAMOND max-target-seqs override",
    )
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repeat_residue = args.repeat_residue.strip().upper()
    if len(repeat_residue) != 1:
        raise ContractError(f"--repeat-residue must be one amino-acid symbol: {args.repeat_residue!r}")
    if args.template_length < 1:
        raise ContractError("--template-length must be positive")
    if args.min_repeat_count < 1:
        raise ContractError("--min-repeat-count must be positive")
    if args.match_score <= 0:
        raise ContractError("--match-score must be positive")
    if args.mismatch_score >= 0:
        raise ContractError("--mismatch-score must be negative")
    if args.merge_gap_max is not None and args.merge_gap_max < 0:
        raise ContractError("--merge-gap-max must be non-negative")
    if args.diamond_evalue <= 0:
        raise ContractError("--diamond-evalue must be positive")
    if args.diamond_max_target_seqs is not None and args.diamond_max_target_seqs < 1:
        raise ContractError("--diamond-max-target-seqs must be positive when provided")

    proteins_rows = read_tsv(args.proteins_tsv, required_columns=PROTEINS_REQUIRED)
    protein_records = dict(read_fasta(args.proteins_fasta))
    outdir = Path(args.outdir)
    template_name = f"{repeat_residue}{args.template_length}"

    row_by_protein_id = {row.get("protein_id", ""): row for row in proteins_rows}
    missing_protein_ids = sorted(protein_id for protein_id in row_by_protein_id if protein_id not in protein_records)
    if missing_protein_ids:
        missing_text = ", ".join(missing_protein_ids[:5])
        if len(missing_protein_ids) > 5:
            missing_text = f"{missing_text}, ..."
        raise ContractError(f"Protein FASTA is missing protein_id values: {missing_text}")

    if args.backend == "template_local":
        merge_gap_max = args.merge_gap_max if args.merge_gap_max is not None else args.template_length // 2
        tracts_by_protein_id = {
            protein_id: find_template_local_tracts(
                protein_records[protein_id],
                repeat_residue,
                template_length=args.template_length,
                match_score=args.match_score,
                mismatch_score=args.mismatch_score,
                min_repeat_count=args.min_repeat_count,
                merge_gap_max=merge_gap_max,
            )
            for protein_id in row_by_protein_id
        }
        merge_rule = f"positive_segment_gap<={merge_gap_max}"
        param_values: dict[str, object] = {
            "backend": args.backend,
            "repeat_residue": repeat_residue,
            "template_length": args.template_length,
            "template_name": template_name,
            "match_score": args.match_score,
            "mismatch_score": args.mismatch_score,
            "min_repeat_count": args.min_repeat_count,
            "merge_gap_max": merge_gap_max,
        }
    else:
        tracts_by_protein_id = find_diamond_blastp_tracts(
            Path(args.proteins_fasta),
            protein_records,
            repeat_residue,
            workdir=outdir / "_diamond_work",
            diamond_bin=args.diamond_bin,
            template_length=args.template_length,
            min_repeat_count=args.min_repeat_count,
            evalue=args.diamond_evalue,
            max_target_seqs=args.diamond_max_target_seqs,
        )
        merge_rule = "diamond_hsp_trim"
        param_values = {
            "backend": args.backend,
            "repeat_residue": repeat_residue,
            "template_length": args.template_length,
            "template_name": template_name,
            "min_repeat_count": args.min_repeat_count,
            "diamond_evalue": args.diamond_evalue,
            "diamond_max_target_seqs": args.diamond_max_target_seqs or max(len(protein_records), 1),
            "diamond_masking": 0,
        }

    call_rows: list[dict[str, object]] = []
    for protein_id, row in row_by_protein_id.items():
        for tract in tracts_by_protein_id.get(protein_id, []):
            call_rows.append(
                build_call_row(
                    method="blast",
                    genome_id=row.get("genome_id", ""),
                    taxon_id=row.get("taxon_id", ""),
                    sequence_id=row.get("sequence_id", ""),
                    protein_id=protein_id,
                    repeat_residue=repeat_residue,
                    start=tract.start,
                    end=tract.end,
                    aa_sequence=tract.aa_sequence,
                    source_file=row.get("protein_path", ""),
                    template_name=template_name,
                    merge_rule=merge_rule,
                    score=format_similarity_score(tract.score),
                )
            )

    call_rows.sort(
        key=lambda row: (
            str(row.get("protein_id", "")),
            int(row.get("start", 0)),
            str(row.get("call_id", "")),
        )
    )
    write_tsv(outdir / "blast_calls.tsv", call_rows, fieldnames=CALL_FIELDNAMES)
    write_run_params(outdir / "run_params.tsv", "blast", param_values)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
