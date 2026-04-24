"""Tests for Phase 6: PayloadBuild model, warmup tasks, and filter state reconstruction."""

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.browser.models import PayloadBuild
from apps.browser.stats.warmup import (
    WARMUP_BUILD_TYPES,
    compute_scope_key,
    default_warmup_scope_params,
    get_bundle_builders,
)
from apps.browser.tasks import run_post_import_warmup, warm_stats_bundle


# ---------------------------------------------------------------------------
# PayloadBuild model
# ---------------------------------------------------------------------------


class PayloadBuildModelTests(TestCase):
    _counter = 0

    def _make_build(self, **kwargs):
        PayloadBuildModelTests._counter += 1
        defaults = {
            "build_type": "ranked_length_summary",
            "scope_key": f"scope-{self._counter}",
            "scope_params": {},
            "catalog_version": 1,
        }
        defaults.update(kwargs)
        return PayloadBuild.objects.create(**defaults)

    def test_default_status_is_pending(self):
        build = self._make_build()
        self.assertEqual(build.status, PayloadBuild.Status.PENDING)

    def test_is_ready_only_for_ready_status(self):
        for status, expected in [
            (PayloadBuild.Status.PENDING, False),
            (PayloadBuild.Status.BUILDING, False),
            (PayloadBuild.Status.READY, True),
            (PayloadBuild.Status.FAILED, False),
        ]:
            with self.subTest(status=status):
                self.assertEqual(self._make_build(status=status).is_ready, expected)

    def test_is_terminal_for_ready_and_failed(self):
        for status, expected in [
            (PayloadBuild.Status.PENDING, False),
            (PayloadBuild.Status.BUILDING, False),
            (PayloadBuild.Status.READY, True),
            (PayloadBuild.Status.FAILED, True),
        ]:
            with self.subTest(status=status):
                self.assertEqual(self._make_build(status=status).is_terminal, expected)

    def test_str_includes_build_type_status_and_version(self):
        build = self._make_build(
            build_type="codon_length_composition",
            status=PayloadBuild.Status.READY,
            catalog_version=7,
        )
        s = str(build)
        self.assertIn("codon_length_composition", s)
        self.assertIn("ready", s)
        self.assertIn("7", s)

    def test_unique_constraint_on_build_type_scope_key_catalog_version(self):
        from django.db import IntegrityError

        PayloadBuild.objects.create(
            build_type="ranked_length_summary", scope_key="dup-key", scope_params={}, catalog_version=5
        )
        with self.assertRaises(IntegrityError):
            PayloadBuild.objects.create(
                build_type="ranked_length_summary", scope_key="dup-key", scope_params={}, catalog_version=5
            )


# ---------------------------------------------------------------------------
# Warmup scope helpers
# ---------------------------------------------------------------------------


class WarmupScopeHelpersTests(SimpleTestCase):
    def test_compute_scope_key_is_stable(self):
        params = default_warmup_scope_params()
        self.assertEqual(compute_scope_key(params), compute_scope_key(params))

    def test_compute_scope_key_differs_for_different_params(self):
        params_a = default_warmup_scope_params()
        params_b = {**params_a, "rank": "species"}
        self.assertNotEqual(compute_scope_key(params_a), compute_scope_key(params_b))

    def test_compute_scope_key_is_40_char_hex(self):
        key = compute_scope_key(default_warmup_scope_params())
        self.assertEqual(len(key), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in key))

    def test_warmup_build_types_are_non_empty(self):
        self.assertGreater(len(WARMUP_BUILD_TYPES), 0)

    def test_get_bundle_builders_covers_all_warmup_types(self):
        builders = get_bundle_builders()
        for build_type in WARMUP_BUILD_TYPES:
            self.assertIn(build_type, builders, f"Missing builder for {build_type!r}")

    def test_default_scope_params_has_expected_keys(self):
        params = default_warmup_scope_params()
        for key in ("run", "branch", "branch_q", "rank", "q", "method", "residue",
                    "length_min", "length_max", "purity_min", "purity_max",
                    "min_count", "top_n"):
            self.assertIn(key, params)

    def test_default_scope_params_has_empty_filter_values(self):
        params = default_warmup_scope_params()
        self.assertEqual(params["run"], "")
        self.assertEqual(params["branch"], "")
        self.assertEqual(params["q"], "")
        self.assertIsNone(params["length_min"])
        self.assertIsNone(params["length_max"])


# ---------------------------------------------------------------------------
# build_stats_filter_state_from_params
# ---------------------------------------------------------------------------


class BuildStatsFilterStateFromParamsTests(TestCase):
    def test_default_params_produce_valid_filter_state(self):
        from apps.browser.stats.filters import build_stats_filter_state_from_params
        from apps.browser.stats.params import DEFAULT_MIN_COUNT, DEFAULT_TOP_N, DEFAULT_UNSCOPED_RANK

        params = default_warmup_scope_params()
        state = build_stats_filter_state_from_params(params)

        self.assertIsNone(state.current_run)
        self.assertEqual(state.current_run_id, "")
        self.assertEqual(state.rank, DEFAULT_UNSCOPED_RANK)
        self.assertEqual(state.q, "")
        self.assertEqual(state.residue, "")
        self.assertIsNone(state.length_min)
        self.assertIsNone(state.length_max)
        self.assertEqual(state.min_count, DEFAULT_MIN_COUNT)
        self.assertEqual(state.top_n, DEFAULT_TOP_N)
        self.assertFalse(state.branch_scope_active)

    def test_params_with_run_resolves_none_for_missing_run(self):
        from apps.browser.stats.filters import build_stats_filter_state_from_params

        params = {**default_warmup_scope_params(), "run": "nonexistent-run-id"}
        state = build_stats_filter_state_from_params(params)
        self.assertIsNone(state.current_run)

    def test_params_with_custom_rank_are_respected(self):
        from apps.browser.stats.filters import build_stats_filter_state_from_params

        params = {**default_warmup_scope_params(), "rank": "genus"}
        state = build_stats_filter_state_from_params(params)
        self.assertEqual(state.rank, "genus")

    def test_cache_key_matches_normal_filter_state_for_same_params(self):
        from apps.browser.stats.filters import build_stats_filter_state_from_params
        from django.test import RequestFactory

        params = default_warmup_scope_params()
        task_state = build_stats_filter_state_from_params(params)

        rf = RequestFactory()
        query = "&".join(
            f"{k}={v}" for k, v in params.items()
            if v is not None and v != ""
        )
        request = rf.get(f"/?{query}")
        from apps.browser.stats.filters import build_stats_filter_state
        web_state = build_stats_filter_state(request)

        # Both states built from the same params should produce the same cache key.
        self.assertEqual(task_state.cache_key(), web_state.cache_key())


# ---------------------------------------------------------------------------
# run_post_import_warmup task
# ---------------------------------------------------------------------------


class RunPostImportWarmupTests(TestCase):
    @patch("apps.browser.tasks.warm_stats_bundle.delay")
    def test_creates_payload_builds_for_all_warmup_types(self, mock_delay):
        run_post_import_warmup(catalog_version=42)

        created = list(PayloadBuild.objects.filter(catalog_version=42))
        self.assertEqual(len(created), len(WARMUP_BUILD_TYPES))
        build_types_created = {b.build_type for b in created}
        self.assertEqual(build_types_created, WARMUP_BUILD_TYPES)

    @patch("apps.browser.tasks.warm_stats_bundle.delay")
    def test_dispatches_warm_stats_bundle_for_each_new_build(self, mock_delay):
        run_post_import_warmup(catalog_version=43)

        self.assertEqual(mock_delay.call_count, len(WARMUP_BUILD_TYPES))
        dispatched_pks = {c.args[0] for c in mock_delay.call_args_list}
        created_pks = set(PayloadBuild.objects.filter(catalog_version=43).values_list("pk", flat=True))
        self.assertEqual(dispatched_pks, created_pks)

    @patch("apps.browser.tasks.warm_stats_bundle.delay")
    def test_idempotent_for_same_catalog_version(self, mock_delay):
        run_post_import_warmup(catalog_version=44)
        mock_delay.reset_mock()
        run_post_import_warmup(catalog_version=44)

        # Second call must not dispatch any new tasks (builds already exist).
        mock_delay.assert_not_called()
        self.assertEqual(PayloadBuild.objects.filter(catalog_version=44).count(), len(WARMUP_BUILD_TYPES))

    @patch("apps.browser.tasks.warm_stats_bundle.delay")
    def test_different_catalog_versions_create_separate_builds(self, mock_delay):
        run_post_import_warmup(catalog_version=10)
        run_post_import_warmup(catalog_version=11)

        self.assertEqual(PayloadBuild.objects.filter(catalog_version=10).count(), len(WARMUP_BUILD_TYPES))
        self.assertEqual(PayloadBuild.objects.filter(catalog_version=11).count(), len(WARMUP_BUILD_TYPES))


# ---------------------------------------------------------------------------
# warm_stats_bundle task
# ---------------------------------------------------------------------------


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class WarmStatsBundleTests(TestCase):
    _counter = 0

    def _make_pending_build(self, build_type="ranked_length_summary"):
        WarmStatsBundleTests._counter += 1
        return PayloadBuild.objects.create(
            build_type=build_type,
            scope_key=f"test-scope-{self._counter}",
            scope_params=default_warmup_scope_params(),
            catalog_version=1,
            status=PayloadBuild.Status.PENDING,
        )

    @patch("apps.browser.stats.warmup.get_bundle_builders")
    @patch("apps.browser.stats.filters.build_stats_filter_state_from_params")
    def test_happy_path_marks_build_ready(self, mock_filter_state, mock_builders):
        mock_builder = MagicMock()
        mock_builders.return_value = {"ranked_length_summary": mock_builder}
        mock_filter_state.return_value = MagicMock()

        build = self._make_pending_build()
        warm_stats_bundle.apply(args=[build.pk])

        build.refresh_from_db()
        self.assertEqual(build.status, PayloadBuild.Status.READY)
        self.assertIsNotNone(build.finished_at)
        mock_builder.assert_called_once()

    @patch("apps.browser.stats.warmup.get_bundle_builders")
    def test_unknown_build_type_marks_failed(self, mock_builders):
        mock_builders.return_value = {}  # no builders registered

        build = self._make_pending_build(build_type="nonexistent_type")
        warm_stats_bundle.apply(args=[build.pk])

        build.refresh_from_db()
        self.assertEqual(build.status, PayloadBuild.Status.FAILED)
        self.assertIn("nonexistent_type", build.error_message)

    @patch("apps.browser.stats.warmup.get_bundle_builders")
    @patch("apps.browser.stats.filters.build_stats_filter_state_from_params")
    def test_already_claimed_build_is_skipped(self, mock_filter_state, mock_builders):
        mock_builders.return_value = {"ranked_length_summary": MagicMock()}

        WarmStatsBundleTests._counter += 1
        build = PayloadBuild.objects.create(
            build_type="ranked_length_summary",
            scope_key=f"claimed-{self._counter}",
            scope_params={},
            catalog_version=1,
            status=PayloadBuild.Status.BUILDING,  # already claimed
        )
        warm_stats_bundle.apply(args=[build.pk])

        build.refresh_from_db()
        self.assertEqual(build.status, PayloadBuild.Status.BUILDING)
        mock_filter_state.assert_not_called()

    def test_nonexistent_build_id_is_silently_ignored(self):
        # Should not raise — the task handles missing rows gracefully.
        warm_stats_bundle.apply(args=[999999])

    @patch("apps.browser.stats.warmup.get_bundle_builders")
    @patch("apps.browser.stats.filters.build_stats_filter_state_from_params")
    def test_builder_exception_marks_build_failed_after_max_retries(self, mock_filter_state, mock_builders):
        mock_builders.return_value = {"ranked_length_summary": MagicMock(side_effect=RuntimeError("db down"))}
        mock_filter_state.return_value = MagicMock()

        build = self._make_pending_build()
        # apply() with throw=False prevents the retry exception from propagating.
        warm_stats_bundle.apply(args=[build.pk], throw=False)

        build.refresh_from_db()
        self.assertEqual(build.status, PayloadBuild.Status.FAILED)
        self.assertIn("db down", build.error_message)


# ---------------------------------------------------------------------------
# PayloadBuildStatusView endpoint
# ---------------------------------------------------------------------------


class PayloadBuildStatusViewTests(TestCase):
    def test_returns_404_for_unknown_pk(self):
        response = self.client.get(reverse("browser:payloadbuild-status", kwargs={"pk": 9999}))
        self.assertEqual(response.status_code, 404)

    def test_returns_json_for_pending_build(self):
        build = PayloadBuild.objects.create(
            build_type="ranked_length_summary",
            scope_key="s1",
            scope_params={},
            catalog_version=1,
            status=PayloadBuild.Status.PENDING,
        )
        response = self.client.get(reverse("browser:payloadbuild-status", kwargs={"pk": build.pk}))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["id"], build.pk)
        self.assertEqual(data["status"], "pending")
        self.assertFalse(data["is_ready"])
        self.assertIsNone(data["started_at"])
        self.assertIsNone(data["error_message"])

    def test_returns_json_for_ready_build(self):
        now = timezone.now()
        build = PayloadBuild.objects.create(
            build_type="codon_length_composition",
            scope_key="s2",
            scope_params={},
            catalog_version=2,
            status=PayloadBuild.Status.READY,
            started_at=now,
            finished_at=now,
        )
        response = self.client.get(reverse("browser:payloadbuild-status", kwargs={"pk": build.pk}))
        data = json.loads(response.content)
        self.assertEqual(data["status"], "ready")
        self.assertTrue(data["is_ready"])
        self.assertIsNotNone(data["finished_at"])

    def test_returns_json_for_failed_build(self):
        build = PayloadBuild.objects.create(
            build_type="ranked_length_summary",
            scope_key="s3",
            scope_params={},
            catalog_version=1,
            status=PayloadBuild.Status.FAILED,
            error_message="timeout exceeded",
        )
        response = self.client.get(reverse("browser:payloadbuild-status", kwargs={"pk": build.pk}))
        data = json.loads(response.content)
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["error_message"], "timeout exceeded")


# ---------------------------------------------------------------------------
# Post-import warmup dispatch
# ---------------------------------------------------------------------------


class PostImportWarmupDispatchTests(TestCase):
    def test_catalog_version_increment_dispatches_warmup(self):
        """A successful catalog version increment should trigger run_post_import_warmup."""
        from apps.imports.services.import_run.state import _dispatch_post_import_warmup

        with patch("celery.current_app.send_task") as mock_send:
            _dispatch_post_import_warmup(catalog_version=99)

        mock_send.assert_called_once_with(
            "apps.browser.tasks.run_post_import_warmup",
            args=[99],
        )

    def test_warmup_dispatch_failure_is_swallowed(self):
        """Warmup dispatch errors must not propagate and break import completion."""
        from apps.imports.services.import_run.state import _dispatch_post_import_warmup

        with patch("celery.current_app.send_task", side_effect=Exception("broker down")):
            # Should not raise.
            _dispatch_post_import_warmup(catalog_version=100)


# ---------------------------------------------------------------------------
# Service boundary
# ---------------------------------------------------------------------------


class PayloadBuildServiceBoundaryTests(SimpleTestCase):
    def test_tasks_module_has_no_view_layer_imports(self):
        import sys
        import apps.browser.tasks as mod

        view_modules = [k for k in sys.modules if "apps.browser.views" in k]
        for view_mod in view_modules:
            attr_name = view_mod.split(".")[-1]
            self.assertFalse(
                hasattr(mod, attr_name),
                f"tasks.py must not import from view layer ({view_mod})",
            )

    def test_warmup_module_has_no_view_layer_imports(self):
        import sys
        import apps.browser.stats.warmup as mod

        view_modules = [k for k in sys.modules if "apps.browser.views" in k]
        for view_mod in view_modules:
            attr_name = view_mod.split(".")[-1]
            self.assertFalse(
                hasattr(mod, attr_name),
                f"warmup.py must not import from view layer ({view_mod})",
            )
