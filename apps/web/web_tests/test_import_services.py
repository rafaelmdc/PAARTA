import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from apps.imports.services import ImportContractError, load_published_run

from .support import build_minimal_publish_root

REPO_ROOT = Path(__file__).resolve().parents[3]


class PublishedRunImportServiceTests(SimpleTestCase):
    def test_load_published_run_parses_real_smoke_run(self):
        publish_root = REPO_ROOT / "runs" / "latest" / "publish"
        if not publish_root.exists():
            self.skipTest("requires runs/latest/publish")

        payload = load_published_run(publish_root)

        self.assertEqual(payload.pipeline_run["run_id"], "phase4_pipeline_2026-04-06_12-03-46Z")
        self.assertGreater(len(payload.taxonomy_rows), 0)
        self.assertGreater(len(payload.genome_rows), 0)
        self.assertGreater(len(payload.sequence_rows), 0)
        self.assertGreater(len(payload.protein_rows), 0)
        self.assertGreater(len(payload.repeat_call_rows), 0)

    def test_load_published_run_rejects_missing_required_file(self):
        with TemporaryDirectory() as tempdir:
            publish_root = build_minimal_publish_root(Path(tempdir))
            (publish_root / "acquisition" / "genomes.tsv").unlink()

            with self.assertRaises(ImportContractError):
                load_published_run(publish_root)

    def test_load_published_run_rejects_malformed_manifest(self):
        with TemporaryDirectory() as tempdir:
            publish_root = build_minimal_publish_root(Path(tempdir))
            (publish_root / "manifest" / "run_manifest.json").write_text("{", encoding="utf-8")

            with self.assertRaises(ImportContractError):
                load_published_run(publish_root)

    def test_load_published_run_rejects_missing_required_columns(self):
        with TemporaryDirectory() as tempdir:
            publish_root = build_minimal_publish_root(Path(tempdir))
            (publish_root / "acquisition" / "genomes.tsv").write_text(
                "genome_id\tsource\tgenome_name\tassembly_type\ttaxon_id\n"
                "genome_1\tncbi_datasets\tExample genome\thaploid\t9606\n",
                encoding="utf-8",
            )

            with self.assertRaises(ImportContractError):
                load_published_run(publish_root)

    def test_load_published_run_rejects_manifest_missing_required_keys(self):
        with TemporaryDirectory() as tempdir:
            publish_root = build_minimal_publish_root(Path(tempdir))
            (publish_root / "manifest" / "run_manifest.json").write_text(
                json.dumps({"run_id": "run-alpha"}, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ImportContractError):
                load_published_run(publish_root)
