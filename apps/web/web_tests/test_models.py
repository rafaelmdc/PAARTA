from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.browser.models import PipelineRun, Taxon, TaxonClosure
from apps.imports.models import ImportBatch


class PipelineRunModelTests(TestCase):
    def test_run_id_must_be_unique(self):
        PipelineRun.objects.create(run_id="run-alpha", status="success")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PipelineRun.objects.create(run_id="run-alpha", status="failed")


class TaxonModelTests(TestCase):
    def test_taxon_can_reference_parent(self):
        root = Taxon.objects.create(taxon_id=1, taxon_name="root", rank="no rank")
        child = Taxon.objects.create(
            taxon_id=9606,
            taxon_name="Homo sapiens",
            rank="species",
            parent_taxon=root,
        )

        self.assertEqual(child.parent_taxon, root)
        self.assertEqual(root.children.get(), child)

    def test_taxon_id_must_be_unique(self):
        Taxon.objects.create(taxon_id=9606, taxon_name="Homo sapiens", rank="species")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Taxon.objects.create(taxon_id=9606, taxon_name="Duplicate", rank="species")


class TaxonClosureModelTests(TestCase):
    def setUp(self):
        self.root = Taxon.objects.create(taxon_id=1, taxon_name="root", rank="no rank")
        self.species = Taxon.objects.create(
            taxon_id=9606,
            taxon_name="Homo sapiens",
            rank="species",
            parent_taxon=self.root,
        )

    def test_taxon_closure_requires_unique_ancestor_descendant_pair(self):
        TaxonClosure.objects.create(ancestor=self.root, descendant=self.species, depth=1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TaxonClosure.objects.create(ancestor=self.root, descendant=self.species, depth=1)

    def test_taxon_closure_depth_must_be_non_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TaxonClosure.objects.create(ancestor=self.root, descendant=self.root, depth=-1)


class ImportBatchModelTests(TestCase):
    def test_import_batch_can_link_to_pipeline_run(self):
        pipeline_run = PipelineRun.objects.create(run_id="run-alpha", status="success")
        batch = ImportBatch.objects.create(
            pipeline_run=pipeline_run,
            source_path="/tmp/run-alpha/publish",
            status=ImportBatch.Status.PENDING,
        )

        self.assertEqual(batch.pipeline_run, pipeline_run)
        self.assertEqual(batch.status, ImportBatch.Status.PENDING)
