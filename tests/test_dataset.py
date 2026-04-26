"""Tests for the dataset generator."""

import pytest

from src.dataset.generator import generate_dataset, MANUFACTURING_GENERATORS, CONSTRUCTION_GENERATORS


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path / "data"


class TestDatasetGeneration:
    def test_generator_counts(self):
        assert len(MANUFACTURING_GENERATORS) == 10
        assert len(CONSTRUCTION_GENERATORS) == 10

    def test_generate_all(self, tmp_data_dir):
        files = generate_dataset(tmp_data_dir)
        assert len(files) == 20
        for f in files:
            assert f.exists()
            assert f.suffix == ".dxf"

    def test_manufacturing_in_correct_dir(self, tmp_data_dir):
        files = generate_dataset(tmp_data_dir)
        mfg_files = [f for f in files if f.parent.name == "manufacturing"]
        assert len(mfg_files) == 10

    def test_construction_in_correct_dir(self, tmp_data_dir):
        files = generate_dataset(tmp_data_dir)
        con_files = [f for f in files if f.parent.name == "construction"]
        assert len(con_files) == 10

    def test_files_are_valid_dxf(self, tmp_data_dir):
        import ezdxf
        files = generate_dataset(tmp_data_dir)
        for f in files:
            doc = ezdxf.readfile(str(f))
            msp = doc.modelspace()
            entities = list(msp)
            assert len(entities) > 0, f"{f.name} has no entities"
