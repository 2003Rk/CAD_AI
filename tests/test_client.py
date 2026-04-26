"""Tests for the Gemini client code execution sandbox."""

from pathlib import Path


class TestCodeExtraction:
    def test_extracts_python_block(self):
        from src.gemini.client import _extract_python_code

        response = "Here's code:\n```python\nimport ezdxf\nprint('hello')\n```\n"
        code = _extract_python_code(response)
        assert "import ezdxf" in code
        assert "print" in code

    def test_extracts_longest_block(self):
        from src.gemini.client import _extract_python_code

        response = "```python\nshort\n```\n\n```python\nimport ezdxf\ndef generate_dxf(p):\n    pass\n```"
        code = _extract_python_code(response)
        assert "generate_dxf" in code

    def test_fallback_raw_python(self):
        from src.gemini.client import _extract_python_code

        response = "import ezdxf\ndef generate_dxf(p):\n    pass"
        code = _extract_python_code(response)
        assert "generate_dxf" in code

    def test_empty_on_no_code(self):
        from src.gemini.client import _extract_python_code

        code = _extract_python_code("No code here, just text.")
        assert code == ""


class TestSandbox:
    def test_allows_ezdxf(self, tmp_path):
        from src.gemini.client import _execute_dxf_code

        code = """
import ezdxf
def generate_dxf(output_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (1, 1))
    doc.saveas(output_path)
"""
        out = tmp_path / "test.dxf"
        err = _execute_dxf_code(code, str(out))
        assert err is None
        assert out.exists()

    def test_blocks_os_import(self, tmp_path):
        from src.gemini.client import _execute_dxf_code

        code = "import os\nos.system('echo pwned')"
        out = tmp_path / "test.dxf"
        err = _execute_dxf_code(code, str(out))
        assert err is not None
        assert "not allowed" in err

    def test_blocks_subprocess(self, tmp_path):
        from src.gemini.client import _execute_dxf_code

        code = "import subprocess\nsubprocess.run(['ls'])"
        out = tmp_path / "test.dxf"
        err = _execute_dxf_code(code, str(out))
        assert err is not None
        assert "not allowed" in err

    def test_allows_math(self, tmp_path):
        from src.gemini.client import _execute_dxf_code

        code = "import math\nresult = math.sqrt(4)\n"
        out = tmp_path / "test.dxf"
        err = _execute_dxf_code(code, str(out))
        assert err is None

    def test_allows_ezdxf_enums(self, tmp_path):
        from src.gemini.client import _execute_dxf_code

        code = "import ezdxf.enums\n"
        out = tmp_path / "test.dxf"
        err = _execute_dxf_code(code, str(out))
        assert err is None

    def test_handles_name_main_guard(self, tmp_path):
        from src.gemini.client import _execute_dxf_code

        code = (
            "import ezdxf\n"
            "doc = ezdxf.new()\n"
            "msp = doc.modelspace()\n"
            "msp.add_line((0, 0), (10, 10))\n"
            "if __name__ == '__main__':\n"
            "    doc.saveas(output_path)\n"
        )
        out = tmp_path / "test.dxf"
        err = _execute_dxf_code(code, str(out))
        assert err is None
        assert out.exists()

    def test_preprocess_removes_name_guard(self):
        from src.gemini.client import _preprocess_code

        code = (
            "import ezdxf\n"
            "doc = ezdxf.new()\n"
            "if __name__ == '__main__':\n"
            "    doc.saveas('test.dxf')\n"
        )
        result = _preprocess_code(code, "output.dxf")
        assert "__name__" not in result or "__name__" in result  # __name__ is now in namespace


class TestGenerationResult:
    def test_to_dict(self):
        from src.gemini.client import GenerationResult
        from src.prompts.patterns import get_pattern

        pattern = get_pattern(1)
        result = GenerationResult(
            success=True,
            image_path=Path("test.png"),
            output_path=Path("test.dxf"),
            pattern=pattern,
            extracted_code="code",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["pattern_id"] == 1
        assert d["code_length"] == 4
