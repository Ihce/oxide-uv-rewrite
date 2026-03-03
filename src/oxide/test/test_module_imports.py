"""Test that oxide modules initialize and import correctly."""
import _path_magic
import core.oxide as oxide


def test_oxide_initializes():
    """Verify that the oxide core can be imported and initialized."""
    assert oxide is not None


def test_modules_available():
    """Verify that modules are discovered and available."""
    modules = oxide.modules_list()
    assert len(modules) > 0, "No modules were loaded"


def test_extractors_loaded():
    """Verify extractor modules loaded."""
    mods = oxide.modules_list(module_type="extractors")
    assert len(mods) > 0, "No extractor modules loaded"


def test_analyzers_loaded():
    """Verify analyzer modules loaded."""
    mods = oxide.modules_list(module_type="analyzers")
    assert len(mods) > 0, "No analyzer modules loaded"


def test_source_loaded():
    """Verify source modules loaded."""
    mods = oxide.modules_list(module_type="source")
    assert len(mods) > 0, "No source modules loaded"


def test_all_modules_have_documentation():
    """Verify all loaded modules have documentation."""
    modules = oxide.modules_list()
    for mod in modules:
        doc = oxide.documentation(mod)
        assert doc is not None, f"Module '{mod}' has no documentation"


def test_module_import_errors_reported():
    """Log any module import errors for visibility (does not fail)."""
    errors = getattr(oxide, "module_import_errors", {})
    if errors:
        for mod, err in errors.items():
            print(f"  Warning: {mod} failed to import: {err}")
