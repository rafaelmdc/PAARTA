from django.test import TestCase
from django.urls import reverse

from .support import create_imported_run_fixture


class BrowserLengthExplorerTests(TestCase):
    def setUp(self):
        self.alpha = create_imported_run_fixture(
            run_id="run-alpha",
            genome_id="genome_alpha",
            sequence_id="seq_alpha",
            protein_id="prot_alpha",
            call_id="call_alpha",
            accession="GCF_ALPHA",
            taxon_key="human",
            genome_name="Human reference genome",
        )
        self.beta = create_imported_run_fixture(
            run_id="run-beta",
            genome_id="genome_beta",
            sequence_id="seq_beta",
            protein_id="prot_beta",
            call_id="call_beta",
            accession="GCF_BETA",
            taxon_key="mouse",
            genome_name="Mouse reference genome",
        )

    def test_length_explorer_renders_with_default_scope(self):
        response = self.client.get(reverse("browser:lengths"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "browser/repeat_length_explorer.html")
        self.assertContains(response, "Lineage-aware repeat length exploration over the current catalog.")
        self.assertEqual(response.context["current_rank"], "class")
        self.assertEqual(response.context["current_top_n"], 25)
        self.assertEqual(response.context["current_min_count"], 3)
        self.assertEqual(response.context["matching_repeat_calls_count"], 2)

    def test_length_explorer_normalizes_run_and_numeric_filters(self):
        response = self.client.get(
            reverse("browser:lengths"),
            {
                "run": "run-beta",
                "residue": "q",
                "top_n": "999",
                "min_count": "0",
                "length_min": "bad",
                "length_max": "12",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_run_id"], "run-beta")
        self.assertEqual(response.context["current_residue"], "Q")
        self.assertEqual(response.context["current_top_n"], 100)
        self.assertEqual(response.context["current_min_count"], 1)
        self.assertIsNone(response.context["current_length_min"])
        self.assertEqual(response.context["current_length_max"], 12)
        self.assertEqual(response.context["matching_repeat_calls_count"], 1)

    def test_length_explorer_branch_scope_defaults_rank_to_species(self):
        response = self.client.get(
            reverse("browser:lengths"),
            {
                "branch_q": "Prim",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["branch_scope_active"])
        self.assertEqual(response.context["current_branch_q"], "Prim")
        self.assertEqual(response.context["current_rank"], "species")
        self.assertEqual(response.context["matching_repeat_calls_count"], 1)
