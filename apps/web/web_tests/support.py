import json
from pathlib import Path


def build_minimal_publish_root(base_dir: Path, *, run_id: str = "run-alpha") -> Path:
    publish_root = base_dir / "publish"
    (publish_root / "manifest").mkdir(parents=True)
    (publish_root / "acquisition").mkdir(parents=True)
    (publish_root / "calls").mkdir(parents=True)

    manifest = {
        "run_id": run_id,
        "status": "success",
        "started_at_utc": "2026-04-06T12:03:46Z",
        "finished_at_utc": "2026-04-06T12:05:44Z",
        "profile": "docker",
        "git_revision": "abc123",
        "inputs": {},
        "paths": {"publish_root": f"runs/{run_id}/publish", "run_root": f"runs/{run_id}"},
        "params": {},
        "enabled_methods": ["pure"],
        "repeat_residues": ["Q"],
        "artifacts": {},
    }
    (publish_root / "manifest" / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    (publish_root / "acquisition" / "taxonomy.tsv").write_text(
        "taxon_id\ttaxon_name\tparent_taxon_id\trank\tsource\n"
        "1\troot\t\tno rank\ttest\n"
        "9606\tHomo sapiens\t1\tspecies\ttest\n",
        encoding="utf-8",
    )
    (publish_root / "acquisition" / "genomes.tsv").write_text(
        "genome_id\tsource\taccession\tgenome_name\tassembly_type\ttaxon_id\tassembly_level\tspecies_name\tdownload_path\tnotes\n"
        "genome_1\tncbi_datasets\tGCF_000001405.40\tExample genome\thaploid\t9606\tChromosome\tHomo sapiens\t/tmp/pkg\t\n",
        encoding="utf-8",
    )
    (publish_root / "acquisition" / "sequences.tsv").write_text(
        "sequence_id\tgenome_id\tsequence_name\tsequence_length\tsequence_path\tgene_symbol\ttranscript_id\tisoform_id\tassembly_accession\ttaxon_id\tsource_record_id\tprotein_external_id\ttranslation_table\tgene_group\tlinkage_status\tpartial_status\n"
        "seq_1\tgenome_1\tNM_000001.1\t900\t/tmp/cds.fna\tGENE1\tNM_000001.1\tNP_000001.1\tGCF_000001405.40\t9606\tcds-1\tNP_000001.1\t1\tGENE1\tgff\t\n",
        encoding="utf-8",
    )
    (publish_root / "acquisition" / "proteins.tsv").write_text(
        "protein_id\tsequence_id\tgenome_id\tprotein_name\tprotein_length\tprotein_path\tgene_symbol\ttranslation_method\ttranslation_status\tassembly_accession\ttaxon_id\tgene_group\tprotein_external_id\n"
        "prot_1\tseq_1\tgenome_1\tNP_000001.1\t300\t/tmp/proteins.faa\tGENE1\ttranslated\ttranslated\tGCF_000001405.40\t9606\tGENE1\tNP_000001.1\n",
        encoding="utf-8",
    )
    (publish_root / "calls" / "run_params.tsv").write_text(
        "method\tparam_name\tparam_value\n"
        "pure\trepeat_residue\tQ\n",
        encoding="utf-8",
    )
    (publish_root / "calls" / "repeat_calls.tsv").write_text(
        "call_id\tmethod\tgenome_id\ttaxon_id\tsequence_id\tprotein_id\tstart\tend\tlength\trepeat_residue\trepeat_count\tnon_repeat_count\tpurity\taa_sequence\tcodon_sequence\tcodon_metric_name\tcodon_metric_value\twindow_definition\ttemplate_name\tmerge_rule\tscore\tsource_file\n"
        "call_1\tpure\tgenome_1\t9606\tseq_1\tprot_1\t10\t20\t11\tQ\t11\t0\t1.0\tQQQQQQQQQQQ\t\t\t\t\t\t\t\t/tmp/proteins.faa\n",
        encoding="utf-8",
    )
    return publish_root


def create_imported_run_fixture(
    *,
    run_id: str,
    genome_id: str,
    sequence_id: str,
    protein_id: str,
    call_id: str,
    accession: str,
):
    from apps.browser.models import Genome, PipelineRun, Protein, RepeatCall, RunParameter, Sequence, Taxon

    root, _ = Taxon.objects.get_or_create(
        taxon_id=1,
        defaults={"taxon_name": "root", "rank": "no rank"},
    )
    species, _ = Taxon.objects.get_or_create(
        taxon_id=9606,
        defaults={"taxon_name": "Homo sapiens", "rank": "species", "parent_taxon": root},
    )
    if species.parent_taxon_id != root.pk:
        species.parent_taxon = root
        species.save(update_fields=["parent_taxon", "updated_at"])

    pipeline_run = PipelineRun.objects.create(
        run_id=run_id,
        status="success",
        profile="docker",
        git_revision="abc123",
        manifest_path=f"/tmp/{run_id}/manifest/run_manifest.json",
        publish_root=f"/tmp/{run_id}/publish",
        manifest_payload={"run_id": run_id},
    )
    genome = Genome.objects.create(
        pipeline_run=pipeline_run,
        genome_id=genome_id,
        source="ncbi_datasets",
        accession=accession,
        genome_name=f"Genome for {run_id}",
        assembly_type="haploid",
        taxon=species,
        assembly_level="Chromosome",
        species_name="Homo sapiens",
    )
    sequence = Sequence.objects.create(
        pipeline_run=pipeline_run,
        genome=genome,
        taxon=species,
        sequence_id=sequence_id,
        sequence_name=f"NM_{run_id}",
        sequence_length=900,
        sequence_path=f"/tmp/{run_id}/cds.fna",
        gene_symbol="GENE1",
    )
    protein = Protein.objects.create(
        pipeline_run=pipeline_run,
        genome=genome,
        sequence=sequence,
        taxon=species,
        protein_id=protein_id,
        protein_name=f"NP_{run_id}",
        protein_length=300,
        protein_path=f"/tmp/{run_id}/proteins.faa",
        gene_symbol="GENE1",
    )
    run_parameter = RunParameter.objects.create(
        pipeline_run=pipeline_run,
        method=RunParameter.Method.PURE,
        param_name="repeat_residue",
        param_value="Q",
    )
    repeat_call = RepeatCall.objects.create(
        pipeline_run=pipeline_run,
        genome=genome,
        sequence=sequence,
        protein=protein,
        taxon=species,
        call_id=call_id,
        method=RepeatCall.Method.PURE,
        start=10,
        end=20,
        length=11,
        repeat_residue="Q",
        repeat_count=11,
        non_repeat_count=0,
        purity=1.0,
        aa_sequence="QQQQQQQQQQQ",
    )
    return {
        "pipeline_run": pipeline_run,
        "genome": genome,
        "sequence": sequence,
        "protein": protein,
        "run_parameter": run_parameter,
        "repeat_call": repeat_call,
        "taxon": species,
    }
