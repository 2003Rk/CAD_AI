"""Tests for the DXF comparator."""

import pytest
from pathlib import Path

import ezdxf

from src.evaluator.comparator import compare_dxf, extract_profile


@pytest.fixture
def ref_dxf(tmp_path) -> Path:
    """Create a reference DXF with known entities."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((100, 0), (100, 50), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((100, 50), (0, 50), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((0, 50), (0, 0), dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((50, 25), 10, dxfattribs={"layer": "HOLE"})
    msp.add_text("TEST", dxfattribs={"layer": "TEXT", "insert": (20, 30)})
    fp = tmp_path / "reference.dxf"
    doc.saveas(fp)
    return fp


@pytest.fixture
def identical_dxf(tmp_path) -> Path:
    """Same as ref but different file."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((100, 0), (100, 50), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((100, 50), (0, 50), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((0, 50), (0, 0), dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((50, 25), 10, dxfattribs={"layer": "HOLE"})
    msp.add_text("TEST", dxfattribs={"layer": "TEXT", "insert": (20, 30)})
    fp = tmp_path / "identical.dxf"
    doc.saveas(fp)
    return fp


@pytest.fixture
def different_dxf(tmp_path) -> Path:
    """Completely different drawing."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_circle((200, 200), 50, dxfattribs={"layer": "MISC"})
    fp = tmp_path / "different.dxf"
    doc.saveas(fp)
    return fp


class TestExtractProfile:
    def test_entity_count(self, ref_dxf):
        profile = extract_profile(ref_dxf)
        assert profile.total_entities == 6  # 4 lines + 1 circle + 1 text

    def test_layers(self, ref_dxf):
        profile = extract_profile(ref_dxf)
        assert "OUTLINE" in profile.layers
        assert "HOLE" in profile.layers
        assert "TEXT" in profile.layers

    def test_bounding_box(self, ref_dxf):
        profile = extract_profile(ref_dxf)
        assert profile.bounding_box is not None
        (minx, miny), (maxx, maxy) = profile.bounding_box
        assert minx == pytest.approx(0, abs=1)
        assert maxx == pytest.approx(100, abs=1)


class TestCompareDXF:
    def test_identical_files_high_score(self, ref_dxf, identical_dxf):
        result = compare_dxf(ref_dxf, identical_dxf)
        assert result.overall_score >= 90

    def test_different_files_low_score(self, ref_dxf, different_dxf):
        result = compare_dxf(ref_dxf, different_dxf)
        assert result.overall_score < 50

    def test_self_comparison_perfect(self, ref_dxf):
        result = compare_dxf(ref_dxf, ref_dxf)
        assert result.overall_score >= 95

    def test_score_components(self, ref_dxf, identical_dxf):
        result = compare_dxf(ref_dxf, identical_dxf)
        assert 0 <= result.geometry_score <= 100
        assert 0 <= result.structure_score <= 100
        assert 0 <= result.dimension_score <= 100
        assert 0 <= result.metadata_score <= 100
