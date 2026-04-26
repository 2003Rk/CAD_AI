# CAD AI Evaluation Pipeline

Production-ready pipeline to evaluate AI-generated CAD drawings against ground-truth DXF files.

## Architecture

```
src/
├── dataset/       # DXF sample generation (20 drawings)
├── converter/     # DXF → PNG image conversion
├── gemini/        # Gemini 3.1 Pro API integration
├── prompts/       # 3 prompt patterns for CAD generation
├── evaluator/     # DXF comparison engine + scoring
├── reports/       # HTML/JSON report generation
├── cli.py         # CLI entry point
├── config.py      # Central configuration
└── pipeline.py    # End-to-end orchestration
```

## Quick Start

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Edit .env with your GEMINI_API_KEY

# 3. Generate sample dataset
cad-eval dataset generate

# 4. Convert DXF to images
cad-eval convert --input data/dxf --output data/images

# 5. Run full evaluation pipeline
cad-eval run --prompt-pattern all

# 6. Generate report
cad-eval report --output output/reports/report.html
```

## Windows Desktop Build

Use the provided PowerShell script to package the local web UI as a Windows desktop app:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1
```

The script now produces an onedir build at `dist\desktop_launcher\desktop_launcher.exe`.
This avoids the common Defender false positive triggered by unsigned `--onefile` PyInstaller executables.

## CLI Commands

| Command | Description |
|---|---|
| `cad-eval dataset generate` | Generate 20 sample DXF drawings |
| `cad-eval convert` | Convert DXF files to PNG images |
| `cad-eval evaluate --prompt-pattern <1\|2\|3\|all>` | Run Gemini + evaluate |
| `cad-eval compare <file1.dxf> <file2.dxf>` | Compare two DXF files directly |
| `cad-eval report` | Generate evaluation reports |
| `cad-eval run` | Full pipeline end-to-end |

## Prompt Patterns

1. **Structured Blueprint** – Detailed technical spec with layer/entity constraints
2. **Step-by-Step Construction** – Sequential drawing instructions
3. **Reference-Based Recreation** – "Recreate this drawing" with minimal guidance

## Scoring

- **Geometry Score** (40%) – Line/arc/circle count and coordinate matching
- **Structure Score** (30%) – Layer names, block definitions, entity types
- **Dimension Score** (20%) – Measurement accuracy within tolerance
- **Metadata Score** (10%) – Text content, attributes, drawing properties
# CAD_AI
