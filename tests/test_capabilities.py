import pytest

from creative_capability_bridge.capabilities import all_manifests, manifest


def test_manifests_expose_transport_and_guarantees() -> None:
    manifests = all_manifests()
    assert [item["adapter"] for item in manifests] == ["blender", "inkscape", "gimp"]
    assert all("source-preserved" in item["guarantees"] for item in manifests)


def test_blender_has_3d_fields_and_inkscape_does_not() -> None:
    assert "z" in manifest("blender")["operations"]["transform.set"]
    assert "z" not in manifest("inkscape")["operations"]["transform.set"]


def test_unknown_manifest_is_rejected() -> None:
    with pytest.raises(KeyError):
        manifest("unknown")


def test_tested_versions_are_exact_evidence_not_ranges() -> None:
    assert manifest("blender")["tested_versions"] == ["Blender 4.0.2"]
    assert manifest("inkscape")["tested_versions"] == ["Inkscape 1.2.2"]
    assert all(
        "+" not in item and ".x" not in item
        for report in all_manifests()
        for item in report["tested_versions"]
    )
    assert manifest("gimp")["target_versions"] == ["GIMP 3.0+"]
