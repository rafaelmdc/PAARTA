import unittest


def build_named_test_suite(test_case_class, test_names):
    suite = unittest.TestSuite()
    for name in test_names:
        suite.addTest(test_case_class(name))
    return suite
