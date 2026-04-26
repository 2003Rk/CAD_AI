"""Tests for DXF to image conversion."""

import pytest
from pathlib import Path

import ezdxf


@pytest.fixture
def sample_dxf(tmp_path) -> Path:
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 50))
    msp.add_circle((50, 25), 10)
    fp = tmp_path / "sample.dxf"
    doc.saveas(fp)
    return fp


class TestDxfToImage:
    def test_single_conversion(self, sample_dxf, tmp_path):
        from src.converter.dxf_to_image import dxf_to_image

        out = tmp_path / "output"
        out.mkdir()
        img = dxf_to_image(sample_dxf, out, dpi=72)
        assert img.exists()
        assert img.suffix == ".png"

    def test_batch_convert(self, tmp_path):
        from src.converter.dxf_to_image import batch_convert

        input_dir = tmp_path / "dxf"
        input_dir.mkdir()
        for name in ["a", "b"]:
            doc = ezdxf.new()
            msp = doc.modelspace()
            msp.add_line((0, 0), (10, 10))
            doc.saveas(input_dir / f"{name}.dxf")

        output_dir = tmp_path / "images"
        images = batch_convert(input_dir, output_dir, dpi=72)
        assert len(images) == 2

    def test_empty_dir_returns_empty(self, tmp_path):
        from src.converter.dxf_to_image import batch_convert

        images = batch_convert(tmp_path, tmp_path / "out", dpi=72)
        assert images == []
