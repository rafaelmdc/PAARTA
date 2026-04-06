from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.browser.models import Genome, PipelineRun, Protein, RepeatCall, RunParameter, Sequence, Taxon, TaxonClosure
from apps.imports.models import ImportBatch

from .support import build_minimal_publish_root


class ImportRunCommandTests(TestCase):
    def test_import_run_creates_models_and_closure(self):
        with TemporaryDirectory() as tempdir:
            publish_root = build_minimal_publish_root(Path(tempdir))

            stdout = StringIO()
            call_command("import_run", publish_root=str(publish_root), stdout=stdout)

            self.assertIn("Imported run run-alpha", stdout.getvalue())
            self.assertEqual(PipelineRun.objects.count(), 1)
            self.assertEqual(ImportBatch.objects.count(), 1)
            self.assertEqual(Taxon.objects.count(), 2)
            self.assertEqual(TaxonClosure.objects.count(), 3)
            self.assertEqual(Genome.objects.count(), 1)
            self.assertEqual(Sequence.objects.count(), 1)
            self.assertEqual(Protein.objects.count(), 1)
            self.assertEqual(RunParameter.objects.count(), 1)
            self.assertEqual(RepeatCall.objects.count(), 1)
            self.assertEqual(ImportBatch.objects.get().status, ImportBatch.Status.COMPLETED)

    def test_import_run_fails_without_replace_for_existing_run(self):
        with TemporaryDirectory() as tempdir:
            publish_root = build_minimal_publish_root(Path(tempdir))
            stdout = StringIO()

            call_command("import_run", publish_root=str(publish_root), stdout=stdout)

            with self.assertRaises(CommandError):
                call_command("import_run", publish_root=str(publish_root), stdout=stdout)

            self.assertEqual(PipelineRun.objects.count(), 1)
            self.assertEqual(ImportBatch.objects.count(), 2)
            self.assertEqual(
                ImportBatch.objects.filter(status=ImportBatch.Status.FAILED).count(),
                1,
            )

    def test_import_run_replace_existing_reloads_run_scoped_rows(self):
        with TemporaryDirectory() as tempdir:
            publish_root = build_minimal_publish_root(Path(tempdir))
            stdout = StringIO()
            call_command("import_run", publish_root=str(publish_root), stdout=stdout)

            (publish_root / "acquisition" / "genomes.tsv").write_text(
                "genome_id\tsource\taccession\tgenome_name\tassembly_type\ttaxon_id\tassembly_level\tspecies_name\tdownload_path\tnotes\n"
                "genome_1\tncbi_datasets\tGCF_000001405.40\tReplacement genome\thaploid\t9606\tChromosome\tHomo sapiens\t/tmp/pkg\tupdated\n",
                encoding="utf-8",
            )
            (publish_root / "calls" / "repeat_calls.tsv").write_text(
                "call_id\tmethod\tgenome_id\ttaxon_id\tsequence_id\tprotein_id\tstart\tend\tlength\trepeat_residue\trepeat_count\tnon_repeat_count\tpurity\taa_sequence\tcodon_sequence\tcodon_metric_name\tcodon_metric_value\twindow_definition\ttemplate_name\tmerge_rule\tscore\tsource_file\n"
                "call_2\tpure\tgenome_1\t9606\tseq_1\tprot_1\t11\t21\t11\tQ\t11\t0\t1.0\tQQQQQQQQQQQ\t\t\t\t\t\t\t\t/tmp/proteins.faa\n",
                encoding="utf-8",
            )

            call_command(
                "import_run",
                publish_root=str(publish_root),
                replace_existing=True,
                stdout=stdout,
            )

            self.assertEqual(PipelineRun.objects.count(), 1)
            self.assertEqual(Genome.objects.count(), 1)
            self.assertEqual(RepeatCall.objects.count(), 1)
            self.assertEqual(Genome.objects.get().genome_name, "Replacement genome")
            self.assertEqual(RepeatCall.objects.get().call_id, "call_2")

    def test_import_run_rolls_back_on_broken_references(self):
        with TemporaryDirectory() as tempdir:
            publish_root = build_minimal_publish_root(Path(tempdir), run_id="run-broken")
            stdout = StringIO()
            (publish_root / "acquisition" / "sequences.tsv").write_text(
                "sequence_id\tgenome_id\tsequence_name\tsequence_length\tsequence_path\tgene_symbol\ttranscript_id\tisoform_id\tassembly_accession\ttaxon_id\tsource_record_id\tprotein_external_id\ttranslation_table\tgene_group\tlinkage_status\tpartial_status\n"
                "seq_1\tmissing_genome\tNM_000001.1\t900\t/tmp/cds.fna\tGENE1\tNM_000001.1\tNP_000001.1\tGCF_000001405.40\t9606\tcds-1\tNP_000001.1\t1\tGENE1\tgff\t\n",
                encoding="utf-8",
            )

            with self.assertRaises(CommandError):
                call_command("import_run", publish_root=str(publish_root), stdout=stdout)

            self.assertFalse(PipelineRun.objects.filter(run_id="run-broken").exists())
            self.assertEqual(Genome.objects.count(), 0)
            self.assertEqual(Sequence.objects.count(), 0)
            self.assertEqual(Protein.objects.count(), 0)
            self.assertEqual(RunParameter.objects.count(), 0)
            self.assertEqual(RepeatCall.objects.count(), 0)
            self.assertEqual(Taxon.objects.count(), 0)
            self.assertEqual(TaxonClosure.objects.count(), 0)
            self.assertEqual(ImportBatch.objects.count(), 1)
            self.assertEqual(ImportBatch.objects.get().status, ImportBatch.Status.FAILED)
