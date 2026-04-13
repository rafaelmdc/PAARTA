from ._browser_views import BrowserViewTests
from ._suite import build_named_test_suite


TEST_NAMES = [
    "test_accession_status_list_filters_by_run_batch_and_status",
    "test_accession_call_count_list_filters_by_run_batch_method_and_residue",
    "test_download_manifest_list_filters_by_run_batch_and_status",
    "test_normalization_warning_list_filters_by_run_batch_and_accession",
]


def load_tests(loader, tests, pattern):
    return build_named_test_suite(BrowserViewTests, TEST_NAMES)
