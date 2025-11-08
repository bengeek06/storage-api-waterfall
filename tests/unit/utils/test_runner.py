"""
test_runner.py
--------------

Test runner script to execute all storage service tests.
Provides organized test execution with detailed reporting.
"""

import unittest
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def run_all_tests():
    """Run all test suites."""

    # Test modules to run
    test_modules = [
        "tests.test_storage_collaborative",
        "tests.test_storage_validation",
        "tests.test_storage_bucket_upload_download",
        "tests.test_storage_integration",
        "tests.test_api",
        "tests.test_config",
        "tests.test_health",
        "tests.test_version",
    ]

    print("🧪 Running Storage Service Test Suite")
    print("=" * 50)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Load tests from each module
    for module_name in test_modules:
        try:
            tests = loader.loadTestsFromName(module_name)
            suite.addTests(tests)
            print(f"✅ Loaded tests from {module_name}")
        except Exception as e:
            print(f"❌ Failed to load tests from {module_name}: {e}")

    print("\n" + "=" * 50)
    print("🚀 Starting test execution...")
    print("=" * 50)

    # Run tests with detailed output
    runner = unittest.TextTestRunner(
        verbosity=2, stream=sys.stdout, buffer=True
    )

    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)

    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped) if hasattr(result, "skipped") else 0

    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_tests - failures - errors - skipped}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    print(f"Skipped: {skipped}")

    if result.wasSuccessful():
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n💥 Some tests failed!")

        if result.failures:
            print(f"\n❌ Failures ({len(result.failures)}):")
            for test, traceback in result.failures:
                print(
                    f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}"
                )

        if result.errors:
            print(f"\n⚠️  Errors ({len(result.errors)}):")
            for test, traceback in result.errors:
                print(
                    f"  - {test}: {traceback.split('Exception:')[-1].strip()}"
                )

        return 1


def run_specific_test_suite(suite_name):
    """Run a specific test suite."""

    suite_mapping = {
        "collaborative": "tests.test_storage_collaborative",
        "validation": "tests.test_storage_validation",
        "upload": "tests.test_storage_bucket_upload_download",
        "integration": "tests.test_storage_integration",
        "api": "tests.test_api",
        "config": "tests.test_config",
        "health": "tests.test_health",
        "version": "tests.test_version",
    }

    if suite_name not in suite_mapping:
        print(f"❌ Unknown test suite: {suite_name}")
        print(f"Available suites: {', '.join(suite_mapping.keys())}")
        return 1

    module_name = suite_mapping[suite_name]

    print(f"🧪 Running {suite_name} test suite")
    print("=" * 50)

    loader = unittest.TestLoader()
    runner = unittest.TextTestRunner(verbosity=2)

    try:
        tests = loader.loadTestsFromName(module_name)
        result = runner.run(tests)
        return 0 if result.wasSuccessful() else 1
    except Exception as e:
        print(f"❌ Failed to run {suite_name} tests: {e}")
        return 1


if __name__ == "__main__":

    if len(sys.argv) > 1:
        # Run specific test suite
        suite_name = sys.argv[1]
        exit_code = run_specific_test_suite(suite_name)
    else:
        # Run all tests
        exit_code = run_all_tests()

    sys.exit(exit_code)
