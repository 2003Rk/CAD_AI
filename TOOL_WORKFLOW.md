# CAD AI Eval Tool Working Flow

This file explains how the tool works from input data to final reports.

## 1. Entry Point

You run the tool using the CLI command:

```bash
cad-eval <command>
```

Main command groups are:

- `dataset generate`
- `convert`
- `evaluate`
- `compare`
- `report`
- `run`
- `ui`

## 2. High-Level Flow

The full workflow (`cad-eval run`) executes these stages:

1. Generate DXF dataset (optional skip)
2. Convert DXF files to images (optional skip)
3. Send each image to Gemini with selected prompt pattern(s)
4. Save generated DXF output
5. Compare generated DXF vs reference DXF
6. Build final reports (JSON, HTML, Excel, optional Google Sheets)

## 3. Detailed Step-by-Step

### Step 1: Dataset Generation

Command:

```bash
cad-eval dataset generate
```

What happens:

- Creates sample CAD DXF drawings
- Stores files under the configured DXF data directories

### Step 2: DXF to Image Conversion

Command:

```bash
cad-eval convert --input data/dxf --output data/images
```

What happens:

- Reads `.dxf` files
- Renders them to image files (configured format and DPI)
- Writes images to `data/images`

### Step 3: AI CAD Generation

Command:

```bash
cad-eval evaluate --prompt-pattern all
```

What happens:

- Loads prompt pattern(s): `1`, `2`, `3`, or `all`
- For each pattern and each image:
- Sends input image + prompt to Gemini client
- Receives generated CAD response
- Saves output DXF to `data/generated`

### Step 4: Evaluation and Scoring

What happens after generation:

- Finds matching reference DXF by drawing name
- Compares generated DXF against reference DXF
- Computes category scores:
- Geometry score (40%)
- Structure score (30%)
- Dimension score (20%)
- Metadata score (10%)
- Computes overall weighted score

### Step 5: Report Generation

What happens:

- Writes JSON summary report
- Writes HTML report
- Writes Excel report
- Optionally updates Google Sheets if configured

Default output location:

- `output/reports/`

## 4. Command-Level Workflows

### A. Full End-to-End (Recommended)

```bash
cad-eval run --prompt-pattern all
```

Runs everything in one command.

### B. Reuse Existing Data

```bash
cad-eval run --skip-dataset --skip-convert --prompt-pattern 1
```

Useful when dataset and images already exist.

### C. Compare Two Files Directly

```bash
cad-eval compare reference.dxf generated.dxf
```

Shows category-wise and overall score in terminal.

### D. Generate Report from Existing JSON

```bash
cad-eval report --format both
```

Rebuilds report files without rerunning generation.

## 5. Simple Flow Diagram

```text
DXF dataset
   -> image conversion
      -> Gemini CAD generation
         -> generated DXF
            -> DXF comparator
               -> scoring
                  -> JSON/HTML/Excel/Sheets reports
```

## 6. Key Folders in Workflow

- `data/dxf/` -> reference DXF files
- `data/images/` -> converted images used as model input
- `data/generated/` -> Gemini-generated DXF outputs
- `output/reports/` -> final reports

## 7. Typical Usage Sequence

```bash
cad-eval dataset generate
cad-eval convert
cad-eval run --prompt-pattern all
```

Or just one command:

```bash
cad-eval run --prompt-pattern all
```
