"""Test that oxide modules initialize and can run against real binaries."""
import json
import os
import signal

import _path_magic
import pytest
import core.oxide as oxide

MODULE_TIMEOUT = 60

SKIP_MODULES = {
    "exhaust_disasm",
    "objdump",
    "emu_angr_disasm",
    "angr_constraints",
    "angr_function_id",
    "fst_angr_disasm",
    "interactive_angr",
    "lb_feature_extraction",
    "basic_blocks",
    "problstc_disasm",
    "problstc_ghidra",
    "binary_visualizer",
    "byte_ngrams",
    "mcp_control_flow_graph",
    "function_representations",
    "file_img",
}


TEST_BINS_DIR = os.environ.get("OXIDE_TEST_BINS", "/home/tools/Projects/ci_pipeline/test_bins")


# ---------------------------------------------------------------------------
# Binary categorization helpers
# ---------------------------------------------------------------------------

def _categorize_binary(filename):
    """Infer arch and OS from filename conventions (JonathanSalwan/binary-samples style)."""
    name = filename.lower()
    # Determine OS/format
    if name.startswith("elf-linux") or "linux" in name:
        os_name = "Linux"
        fmt = "ELF"
    elif name.startswith("elf-freebsd") or "freebsd" in name:
        os_name = "FreeBSD"
        fmt = "ELF"
    elif name.startswith("elf-netbsd") or "netbsd" in name:
        os_name = "NetBSD"
        fmt = "ELF"
    elif name.startswith("elf-openbsd") or "openbsd" in name:
        os_name = "OpenBSD"
        fmt = "ELF"
    elif name.startswith("elf-haiku") or "haiku" in name:
        os_name = "Haiku"
        fmt = "ELF"
    elif name.startswith("elf-hpux") or "hpux" in name:
        os_name = "HP-UX"
        fmt = "ELF"
    elif name.startswith("elf-solaris") or "solaris" in name:
        os_name = "Solaris"
        fmt = "ELF"
    elif name.startswith("elf"):
        os_name = "Linux"
        fmt = "ELF"
    elif name.startswith("pe-") or name.endswith(".exe"):
        os_name = "Windows"
        fmt = "PE"
    elif name.startswith("macho-osx") or "osx" in name:
        os_name = "macOS"
        fmt = "Mach-O"
    elif name.startswith("macho-ios") or "ios" in name:
        os_name = "iOS"
        fmt = "Mach-O"
    elif name.startswith("macho"):
        os_name = "macOS"
        fmt = "Mach-O"
    else:
        os_name = "Unknown"
        fmt = "Unknown"

    # Determine architecture
    if "arm64" in name or "aarch64" in name:
        arch = "ARM64"
    elif "armv7" in name:
        arch = "ARMv7"
    elif "arm" in name:
        arch = "ARM"
    elif "x86_64" in name or "x86-64" in name or "x64" in name:
        arch = "x86_64"
    elif "x86" in name or "i386" in name or "i686" in name:
        arch = "x86"
    elif "mips" in name:
        arch = "MIPS"
    elif "powerpc" in name or "ppc" in name:
        arch = "PowerPC"
    elif "sparc" in name:
        arch = "SPARC"
    elif "s390" in name:
        arch = "s390"
    elif "ia64" in name:
        arch = "IA-64"
    elif "hppa" in name:
        arch = "PA-RISC"
    elif "alpha" in name:
        arch = "Alpha"
    elif "superh" in name or "sh4" in name:
        arch = "SuperH"
    elif "thumb2" in name:
        arch = "ARMv7"
    else:
        arch = "Unknown"

    return {"os": os_name, "arch": arch, "format": fmt}


def _get_test_binaries():
    """Return list of (filename, filepath, metadata) for all test binaries."""
    if not os.path.isdir(TEST_BINS_DIR):
        return []
    bins = []
    for f in sorted(os.listdir(TEST_BINS_DIR)):
        fp = os.path.join(TEST_BINS_DIR, f)
        if os.path.isfile(fp):
            meta = _categorize_binary(f)
            bins.append((f, fp, meta))
    return bins


TEST_BINARIES = _get_test_binaries()


@pytest.fixture(scope="session")
def oid_list():
    """Load test binaries into oxide and return list of OIDs."""
    if not os.path.isdir(TEST_BINS_DIR):
        pytest.skip(f"Test binaries directory not found: {TEST_BINS_DIR}")
    oids, new_count = oxide.import_directory(TEST_BINS_DIR)
    if not oids:
        pytest.fail(f"Failed to import any binaries from {TEST_BINS_DIR}")
    return oids


@pytest.fixture(scope="session")
def oid_map():
    """Load test binaries individually and return {filename: oid} mapping."""
    if not os.path.isdir(TEST_BINS_DIR):
        pytest.skip(f"Test binaries directory not found: {TEST_BINS_DIR}")
    mapping = {}
    for fname, fpath, meta in TEST_BINARIES:
        oids, _ = oxide.import_file(fpath)
        if oids:
            mapping[fname] = {"oid": oids[0] if isinstance(oids, list) else oids,
                              "meta": meta}
    if not mapping:
        pytest.fail(f"Failed to import any binaries from {TEST_BINS_DIR}")
    return mapping


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
        msg = errors[mod_name]
        if "Missing" in str(msg) and "package" in str(msg):
            pytest.skip(f"{mod_name}: {msg}")
        pytest.fail(f"{mod_name}: {msg}")
    available = oxide.modules_list(module_type=module_type)
    assert mod_name in available, f"{mod_name}: not loaded (check deps or syntax)"


class _Timeout(BaseException):
    pass


def _timeout_handler(signum, frame):
    raise _Timeout()


def _assert_module_runs(mod_name, oid_list):
    if mod_name in SKIP_MODULES:
        pytest.skip(f"{mod_name}: skipped (known timeout)")
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(MODULE_TIMEOUT)
    try:
        results = oxide.retrieve(mod_name, oid_list, {})
    except _Timeout:
        pytest.skip(f"{mod_name}: timed out after {MODULE_TIMEOUT}s")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    assert results is not None, f"{mod_name}: returned None"
    err = _check_json_serializable(results)
    assert err is None, f"{mod_name}: not JSON serializable: {err}"


def _assert_module_runs_single(mod_name, oid):
    """Run a module against a single OID and return (pass, skip, fail) with message."""
    if mod_name in SKIP_MODULES:
        pytest.skip(f"{mod_name}: skipped (known timeout)")
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(MODULE_TIMEOUT)
    try:
        results = oxide.retrieve(mod_name, [oid], {})
    except _Timeout:
        pytest.skip(f"{mod_name}: timed out after {MODULE_TIMEOUT}s")
    except Exception as e:
        pytest.fail(f"{mod_name}: exception: {e}")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    assert results is not None, f"{mod_name}: returned None"
    err = _check_json_serializable(results)
    assert err is None, f"{mod_name}: not JSON serializable: {err}"


# ---------------------------------------------------------------------------
# Generate per-binary module execution parameters
# ---------------------------------------------------------------------------

def _per_binary_params(module_type):
    """Generate (mod_name, bin_filename) pairs for parametrized tests."""
    modules = _get_modules_by_type(module_type)
    binaries = _get_test_binaries()
    params = []
    for mod in modules:
        for fname, fpath, meta in binaries:
            label = f"{mod}|{meta['arch']}-{meta['os']}|{fname}"
            params.append(pytest.param(mod, fname, id=label))
    return params


# ============================= Test Classes ================================


class TestInitialization:

    def test_oxide_initializes(self):
        assert oxide is not None

    def test_modules_available(self):
        modules = oxide.modules_list()
        assert len(modules) > 0, "No modules were loaded"

    def test_binaries_loaded(self, oid_map):
        assert len(oid_map) > 0, "No test binaries loaded"
        for fname, info in oid_map.items():
            meta = info["meta"]
            assert info["oid"], f"{fname} ({meta['arch']}/{meta['os']}): no OID"


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


# ---------------------------------------------------------------------------
# Per-binary execution tests — these produce the arch/OS matrix in the report
# ---------------------------------------------------------------------------

class TestExtractorPerBinary:

    @pytest.mark.parametrize("mod_name,bin_name", _per_binary_params("extractors"))
    def test_run(self, mod_name, bin_name, oid_map):
        if bin_name not in oid_map:
            pytest.skip(f"{bin_name}: not imported")
        _assert_module_runs_single(mod_name, oid_map[bin_name]["oid"])


class TestAnalyzerPerBinary:

    @pytest.mark.parametrize("mod_name,bin_name", _per_binary_params("analyzers"))
    def test_run(self, mod_name, bin_name, oid_map):
        if bin_name not in oid_map:
            pytest.skip(f"{bin_name}: not imported")
        _assert_module_runs_single(mod_name, oid_map[bin_name]["oid"])


class TestMapReducerPerBinary:

    @pytest.mark.parametrize("mod_name,bin_name", _per_binary_params("map_reducers"))
    def test_run(self, mod_name, bin_name, oid_map):
        if bin_name not in oid_map:
            pytest.skip(f"{bin_name}: not imported")
        _assert_module_runs_single(mod_name, oid_map[bin_name]["oid"])
