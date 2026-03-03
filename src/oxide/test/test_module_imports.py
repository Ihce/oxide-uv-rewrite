"""Test that oxide modules initialize and can run against real binaries."""
import json
import os

import _path_magic
import pytest
import core.oxide as oxide


TEST_BINS_DIR = os.environ.get("OXIDE_TEST_BINS", "/home/tools/Projects/ci_pipeline/test_bins")


@pytest.fixture(scope="session")
def oid_list():
    """Load test binaries into oxide and return list of OIDs."""
    if not os.path.isdir(TEST_BINS_DIR):
        pytest.skip(f"Test binaries directory not found: {TEST_BINS_DIR}")
    oids, new_count = oxide.import_directory(TEST_BINS_DIR)
    if not oids:
        pytest.fail(f"Failed to import any binaries from {TEST_BINS_DIR}")
    return oids


# --- Basic initialization tests ---

def test_oxide_initializes():
    assert oxide is not None


def test_modules_available():
    modules = oxide.modules_list()
    assert len(modules) > 0, "No modules were loaded"


def test_extractors_loaded():
    mods = oxide.modules_list(module_type="extractors")
    assert len(mods) > 0, "No extractor modules loaded"


def test_analyzers_loaded():
    mods = oxide.modules_list(module_type="analyzers")
    assert len(mods) > 0, "No analyzer modules loaded"


def test_source_loaded():
    mods = oxide.modules_list(module_type="source")
    assert len(mods) > 0, "No source modules loaded"


# --- Per-module import tests ---

def _all_expected_modules():
    """Get all module directories that should have loaded (excludes _dev)."""
    modules_dir = os.path.join(os.path.dirname(_path_magic.__file__), "..", "modules")
    expected = []
    for module_type in os.listdir(modules_dir):
        if module_type.endswith("_dev"):
            continue
        type_path = os.path.join(modules_dir, module_type)
        if not os.path.isdir(type_path) or module_type.startswith("."):
            continue
        for mod in os.listdir(type_path):
            mod_path = os.path.join(type_path, mod)
            if os.path.isdir(mod_path) and os.path.exists(os.path.join(mod_path, "module_interface.py")):
                expected.append((module_type, mod))
    return expected


@pytest.mark.parametrize(
    "module_type,mod_name",
    _all_expected_modules(),
    ids=lambda x: str(x),
)
def test_module_loaded(module_type, mod_name):
    """Verify that a module loaded without import errors."""
    errors = getattr(oxide, "module_import_errors", {})
    if mod_name in errors:
        pytest.fail(f"{mod_name}: {errors[mod_name]}")

    available = oxide.modules_list(module_type=module_type)
    assert mod_name in available, f"{mod_name}: not loaded (check deps or syntax)"


# --- Per-module execution tests against real binaries ---

def _get_modules_by_type(module_type):
    return oxide.modules_list(module_type=module_type)


def _check_json_serializable(results):
    """Return error string if not JSON serializable, else None."""
    try:
        json.dumps(results)
        return None
    except (TypeError, ValueError) as e:
        return str(e)


@pytest.mark.parametrize("mod_name", _get_modules_by_type("extractors"), ids=lambda m: f"extractor:{m}")
def test_extractor(mod_name, oid_list):
    results = oxide.retrieve(mod_name, oid_list, {})
    assert results is not None, f"{mod_name}: returned None"
    err = _check_json_serializable(results)
    assert err is None, f"{mod_name}: not JSON serializable: {err}"


@pytest.mark.parametrize("mod_name", _get_modules_by_type("analyzers"), ids=lambda m: f"analyzer:{m}")
def test_analyzer(mod_name, oid_list):
    results = oxide.retrieve(mod_name, oid_list, {})
    assert results is not None, f"{mod_name}: returned None"
    err = _check_json_serializable(results)
    assert err is None, f"{mod_name}: not JSON serializable: {err}"


@pytest.mark.parametrize("mod_name", _get_modules_by_type("map_reducers"), ids=lambda m: f"map_reducer:{m}")
def test_map_reducer(mod_name, oid_list):
    results = oxide.retrieve(mod_name, oid_list, {})
    assert results is not None, f"{mod_name}: returned None"
    err = _check_json_serializable(results)
    assert err is None, f"{mod_name}: not JSON serializable: {err}"
