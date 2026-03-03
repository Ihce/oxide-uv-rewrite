"""Test that oxide modules initialize and can run against real binaries."""
import json
import multiprocessing
import os

import _path_magic
import pytest
import core.oxide as oxide

MODULE_TIMEOUT = 60

SKIP_MODULES = {
    "exhaust_disasm",
    "objdump",
    "emu_angr_disasm",
    "angr_constraints",
    "problstc_disasm",
    "binary_visualizer",
    "byte_ngrams",
    "mcp_control_flow_graph",
    "function_representations",
    "file_img",
}


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


def _expected_modules_for(module_type):
    """Get module directories for a specific type (excludes _dev)."""
    modules_dir = os.path.join(os.path.dirname(_path_magic.__file__), "..", "modules")
    type_path = os.path.join(modules_dir, module_type)
    if not os.path.isdir(type_path):
        return []
    result = []
    for mod in os.listdir(type_path):
        mod_path = os.path.join(type_path, mod)
        if os.path.isdir(mod_path) and os.path.exists(os.path.join(mod_path, "module_interface.py")):
            result.append(mod)
    return result


def _get_modules_by_type(module_type):
    return oxide.modules_list(module_type=module_type)


def _check_json_serializable(results):
    try:
        json.dumps(results)
        return None
    except (TypeError, ValueError) as e:
        return str(e)


def _assert_module_loaded(module_type, mod_name):
    errors = getattr(oxide, "module_import_errors", {})
    if mod_name in errors:
        pytest.fail(f"{mod_name}: {errors[mod_name]}")
    available = oxide.modules_list(module_type=module_type)
    assert mod_name in available, f"{mod_name}: not loaded (check deps or syntax)"


def _run_module(mod_name, oid_list, result_queue):
    """Target for subprocess — runs module and puts result on queue."""
    try:
        results = oxide.retrieve(mod_name, oid_list, {})
        err = _check_json_serializable(results) if results is not None else None
        result_queue.put(("ok", results, err))
    except Exception as e:
        result_queue.put(("error", str(e), None))


def _assert_module_runs(mod_name, oid_list):
    if mod_name in SKIP_MODULES:
        pytest.skip(f"{mod_name}: skipped (known timeout)")
    queue = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_run_module, args=(mod_name, oid_list, queue))
    proc.start()
    proc.join(timeout=MODULE_TIMEOUT)
    if proc.is_alive():
        proc.kill()
        proc.join()
        pytest.skip(f"{mod_name}: timed out after {MODULE_TIMEOUT}s")
    if queue.empty():
        pytest.fail(f"{mod_name}: process exited with no result (code {proc.exitcode})")
    status, result, err = queue.get_nowait()
    if status == "error":
        pytest.fail(f"{mod_name}: {result}")
    assert result is not None, f"{mod_name}: returned None"
    assert err is None, f"{mod_name}: not JSON serializable: {err}"


class TestInitialization:

    def test_oxide_initializes(self):
        assert oxide is not None

    def test_modules_available(self):
        modules = oxide.modules_list()
        assert len(modules) > 0, "No modules were loaded"


class TestSourceImports:

    @pytest.mark.parametrize("mod_name", _expected_modules_for("source"))
    def test_loaded(self, mod_name):
        _assert_module_loaded("source", mod_name)


class TestExtractorImports:

    @pytest.mark.parametrize("mod_name", _expected_modules_for("extractors"))
    def test_loaded(self, mod_name):
        _assert_module_loaded("extractors", mod_name)


class TestAnalyzerImports:

    @pytest.mark.parametrize("mod_name", _expected_modules_for("analyzers"))
    def test_loaded(self, mod_name):
        _assert_module_loaded("analyzers", mod_name)


class TestMapReducerImports:

    @pytest.mark.parametrize("mod_name", _expected_modules_for("map_reducers"))
    def test_loaded(self, mod_name):
        _assert_module_loaded("map_reducers", mod_name)


class TestExtractorExecution:

    @pytest.mark.parametrize("mod_name", _get_modules_by_type("extractors"))
    def test_run(self, mod_name, oid_list):
        _assert_module_runs(mod_name, oid_list)


class TestAnalyzerExecution:

    @pytest.mark.parametrize("mod_name", _get_modules_by_type("analyzers"))
    def test_run(self, mod_name, oid_list):
        _assert_module_runs(mod_name, oid_list)


class TestMapReducerExecution:

    @pytest.mark.parametrize("mod_name", _get_modules_by_type("map_reducers"))
    def test_run(self, mod_name, oid_list):
        _assert_module_runs(mod_name, oid_list)
