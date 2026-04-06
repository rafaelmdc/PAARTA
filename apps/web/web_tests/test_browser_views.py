from django.test import TestCase
from django.urls import reverse

from .support import create_imported_run_fixture


class BrowserViewTests(TestCase):
    def setUp(self):
        self.alpha = create_imported_run_fixture(
            run_id="run-alpha",
            genome_id="genome_alpha",
            sequence_id="seq_alpha",
            protein_id="prot_alpha",
            call_id="call_alpha",
            accession="GCF_ALPHA",
        )
        self.beta = create_imported_run_fixture(
            run_id="run-beta",
            genome_id="genome_beta",
            sequence_id="seq_beta",
            protein_id="prot_beta",
            call_id="call_beta",
            accession="GCF_BETA",
        )

    def test_browser_home_shows_counts_and_recent_runs(self):
        response = self.client.get(reverse("browser:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Imported runs")
        self.assertContains(response, "run-alpha")
        self.assertContains(response, "run-beta")

    def test_run_list_renders_imported_runs(self):
        response = self.client.get(reverse("browser:run-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "run-alpha")
        self.assertContains(response, "run-beta")
        self.assertContains(response, reverse("browser:run-detail", args=[self.alpha["pipeline_run"].pk]))

    def test_run_list_search_filters_results(self):
        response = self.client.get(reverse("browser:run-list"), {"q": "run-beta"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "run-beta")
        self.assertNotContains(response, "run-alpha")

    def test_run_detail_shows_counts_and_scoped_links(self):
        response = self.client.get(reverse("browser:run-detail", args=[self.alpha["pipeline_run"].pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "run-alpha")
        self.assertContains(response, "Distinct taxa referenced")
        self.assertContains(response, "?run=run-alpha")
        self.assertContains(response, "Method: pure")

    def test_section_placeholder_accepts_run_filter(self):
        response = self.client.get(reverse("browser:taxon-list"), {"run": "run-alpha"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "run-alpha")
        self.assertContains(response, "next slice")
