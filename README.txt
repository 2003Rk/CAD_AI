CAD AI Evaluation Pipeline
==========================

Production-ready pipeline to evaluate AI-generated CAD drawings against
ground-truth DXF files using Google Gemini.


ARCHITECTURE
------------

src/
  dataset/       - DXF sample generation (20 drawings)
  converter/     - DXF to PNG image conversion
  gemini/        - Gemini API integration
  prompts/       - 3 prompt patterns for CAD generation
  evaluator/     - DXF comparison engine + scoring
  reports/       - HTML/JSON report generation
  cli.py         - CLI entry point
  config.py      - Central configuration
  pipeline.py    - End-to-end orchestration


QUICK START
-----------

1. Install
   pip install -e ".[dev]"

2. Configure
   cp .env.example .env
   # Edit .env with your GEMINI_API_KEY

3. Generate sample dataset
   cad-eval dataset generate

4. Convert DXF to images
   cad-eval convert --input data/dxf --output data/images

5. Run full evaluation pipeline
   cad-eval run --prompt-pattern all

6. Generate report
   cad-eval report --output output/reports/report.html


CLI COMMANDS
------------

  cad-eval dataset generate            Generate 20 sample DXF drawings
  cad-eval convert                     Convert DXF files to PNG images
  cad-eval evaluate --prompt-pattern   Run Gemini + evaluate (1|2|3|all)
  cad-eval compare <file1> <file2>     Compare two DXF files directly
  cad-eval report                      Generate evaluation reports
  cad-eval run                         Full pipeline end-to-end


PROMPT PATTERNS
---------------

1. Structured Blueprint
   Detailed technical spec with layer/entity constraints.

2. Step-by-Step Construction
   Sequential drawing instructions.

3. Reference-Based Recreation
   "Recreate this drawing" with minimal guidance.


SCORING
-------

  Geometry Score  (40%)  - Line/arc/circle count and coordinate matching
  Structure Score (30%)  - Layer names, block definitions, entity types
  Dimension Score (20%)  - Measurement accuracy within tolerance
  Metadata Score  (10%)  - Text content, attributes, drawing properties


DATASET
-------

20 DXF drawings split across two domains:
  - 10 Manufacturing  (stepped shaft, flange, bracket, gasket, gear, etc.)
  - 10 Construction   (floor plan, wall section, foundation, roof truss, etc.)


RUNTIME CONFIGURATION (environment variables)
----------------------------------------------

  GEMINI_API_KEY              Required. Your Google Gemini API key.
  GEMINI_MODEL                Gemini model name (default: gemini-2.0-flash).
  REQUEST_TIMEOUT_MS          Per-request timeout in milliseconds.
  INTER_REQUEST_DELAY         Delay between API requests (seconds).
  MAX_QUOTA_BACKOFF_SECONDS   Max backoff time on quota errors.


WINDOWS DESKTOP BUILD
---------------------

Use the provided PowerShell script to package the local web UI as a Windows
desktop app:

  powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_exe.ps1

Produces an onedir build at dist\desktop_launcher\desktop_launcher.exe.


REQUIREMENTS
------------

  Python 3.12+
  ezdxf, matplotlib, Pillow, google-genai, scipy, jinja2, pydantic, click, rich
