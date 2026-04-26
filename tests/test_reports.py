"""Tests for report generation."""

import json

from src.reports.report_gen import generate_json_report, generate_html_report


def _sample_results() -> list[dict]:
    return [
        {
            "success": True,
            "drawing_name": "mfg_01_shaft",
            "pattern_name": "Structured Blueprint",
            "pattern_id": 1,
            "overall_score": 72.5,
            "geometry_score": 80.0,
            "structure_score": 65.0,
            "dimension_score": 70.0,
            "metadata_score": 50.0,
        },
        {
            "success": True,
            "drawing_name": "con_01_floor_plan",
            "pattern_name": "Step-by-Step Construction",
            "pattern_id": 2,
            "overall_score": 55.0,
            "geometry_score": 60.0,
            "structure_score": 50.0,
            "dimension_score": 55.0,
            "metadata_score": 40.0,
        },
        {
            "success": False,
            "drawing_name": "mfg_02_flange",
            "pattern_name": "Reference-Based Recreation",
            "pattern_id": 3,
            "error": "Code execution failed",
        },
    ]


class TestJsonReport:
    def test_creates_file(self, tmp_path):
        out = tmp_path / "report.json"
        generate_json_report(_sample_results(), out)
        assert out.exists()

    def test_valid_json(self, tmp_path):
        out = tmp_path / "report.json"
        generate_json_report(_sample_results(), out)
        data = json.loads(out.read_text())
        assert data["total_evaluations"] == 3
        assert "summary" in data
        assert "results" in data


class TestHtmlReport:
    def test_creates_file(self, tmp_path):
        out = tmp_path / "report.html"
        generate_html_report(_sample_results(), out)
        assert out.exists()

    def test_contains_scores(self, tmp_path):
        out = tmp_path / "report.html"
        generate_html_report(_sample_results(), out)
        html = out.read_text()
        assert "72.5" in html
        assert "Structured Blueprint" in html
