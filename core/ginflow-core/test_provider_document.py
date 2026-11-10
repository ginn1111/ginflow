"""Tests for provider document builder and local adapter."""
import tempfile
from pathlib import Path

from provider_document import build_provider_document, content_hash, write_local_document

PACKAGE = {
    "key": "UNIT-1", "objective": "ship it", "scope": ["core"], "acceptance": ["passes"],
    "contract": "contract text", "spec": "spec text", "plan": ["step one", "step two"],
    "verification": ["make test"],
}
HEADINGS = ["## Objective", "## Scope", "## Acceptance", "## Contract", "## Spec", "## Plan", "## Verification"]


def raises(fn, text):
    try:
        fn()
    except ValueError as error:
        assert text in str(error), error
    else:
        raise AssertionError("expected ValueError")


def test_builder_sections_metadata_and_hash():
    doc = build_provider_document("local", PACKAGE, {"root": "/r"})
    body = doc["body"]
    assert body.startswith("---\nprovider: local\nwork_unit: UNIT-1\nschema: provider_document/v1\n---\n")
    positions = [body.index(h) for h in HEADINGS]
    assert positions == sorted(positions)
    assert "## Dependencies" not in body and "## Risks" not in body
    assert doc["target_hints"] == {"root": "/r", "path": "docs/work-units/UNIT-1.md"}
    assert doc["metadata"]["work_unit"] == "UNIT-1"
    assert doc["content_hash"] == content_hash(body)
    assert doc == build_provider_document("local", PACKAGE, {"root": "/r"})


def test_optional_sections_render_in_order():
    body = build_provider_document("local", {**PACKAGE, "dependencies": ["U-0"], "risks": "r"}, {})["body"]
    assert body.index("## Verification") < body.index("## Dependencies") < body.index("## Risks")


def test_hash_normalization_only():
    assert content_hash("a  \r\nb\n\n") == content_hash("a\nb\n")
    assert content_hash("a\nb\n") != content_hash("b\na\n")
    assert content_hash("a b\n") != content_hash("a  b\n")


def test_rejections():
    raises(lambda: build_provider_document("nope", PACKAGE, {}), "unknown provider")
    raises(lambda: build_provider_document("local", {**PACKAGE, "plan": " "}, {}), "plan")
    raises(lambda: build_provider_document("local", {**PACKAGE, "key": "../x"}, {}), "invalid work unit key")


def test_local_adapter_write_adopt_block():
    doc = build_provider_document("local", PACKAGE, {})
    with tempfile.TemporaryDirectory() as root:
        assert write_local_document(doc, root)["status"] == "written"
        path = Path(root) / doc["target_hints"]["path"]
        assert path.read_text() == doc["body"]
        assert write_local_document(doc, root)["status"] == "adopted"
        path.write_text(doc["body"] + "edited\n")
        blocked = write_local_document(doc, root)
        assert blocked["status"] == "blocked"
        assert path.read_text().endswith("edited\n")


if __name__ == "__main__":
    test_builder_sections_metadata_and_hash()
    test_optional_sections_render_in_order()
    test_hash_normalization_only()
    test_rejections()
    test_local_adapter_write_adopt_block()
    print("provider document tests passed")
