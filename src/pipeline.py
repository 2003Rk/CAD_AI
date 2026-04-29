"""End-to-end orchestration pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from src.config import get_settings
from src.converter.dxf_to_image import batch_convert
from src.dataset.generator import generate_dataset
from src.evaluator.comparator import compare_dxf
from src.gemini.client import GeminiCADClient
from src.prompts.patterns import get_all_patterns, get_pattern
from src.reports.report_gen import generate_html_report, generate_json_report, generate_excel_report, generate_sheets_report

logger = logging.getLogger(__name__)
console = Console()


def run_full_pipeline(
    pattern_ids: list[int] | None = None,
    skip_dataset: bool = False,
    skip_convert: bool = False,
    progress_callback: Callable[[dict], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Path:
    """Execute the complete evaluation pipeline.

    1. Generate dataset (if not skipped)
    2. Convert DXF → images (if not skipped)
    3. For each prompt pattern × each image → Gemini → DXF
    4. Compare generated DXF vs reference
    5. Generate reports

    Returns path to the HTML report.
    """
    settings = get_settings()
    settings.ensure_dirs()

    patterns = (
        [get_pattern(pid) for pid in pattern_ids]
        if pattern_ids
        else get_all_patterns()
    )

    # Progress model: dataset + convert + evaluations + reports
    eval_total = len(patterns) * len(sorted(settings.images_dir.rglob(f"*.{settings.image_format}")))
    total_units = eval_total + 3
    completed_units = 0

    def _emit(stage: str, detail: str = "", current: int | None = None, total: int | None = None) -> None:
        if not progress_callback:
            return
        progress_callback(
            {
                "stage": stage,
                "detail": detail,
                "completed": completed_units,
                "total": total_units,
                "current": current,
                "count_total": total,
                "percent": round((completed_units / total_units) * 100, 1) if total_units else 0.0,
            }
        )

    _emit("starting", "Preparing pipeline")

    # Step 1: Dataset
    if not skip_dataset:
        _emit("dataset", "Generating dataset")
        console.print("[bold blue]Step 1/5:[/] Generating dataset…")
        dxf_files = generate_dataset(settings.data_dir)
        console.print(f"  Created {len(dxf_files)} DXF files.")
    else:
        dxf_files = sorted(settings.dxf_dir.rglob("*.dxf"))
        console.print(f"[dim]Skipping dataset generation. Found {len(dxf_files)} existing DXF files.[/dim]")
    completed_units += 1
    _emit("dataset", f"Dataset ready ({len(dxf_files)} DXF files)")

    # Step 2: Convert to images
    if not skip_convert:
        _emit("convert", "Converting DXF to images")
        console.print("[bold blue]Step 2/5:[/] Converting DXF → images…")
        images = batch_convert(
            settings.dxf_dir, settings.images_dir,
            dpi=settings.image_dpi, image_format=settings.image_format,
        )
        console.print(f"  Converted {len(images)} images.")
    else:
        images = sorted(settings.images_dir.rglob(f"*.{settings.image_format}"))
        console.print(f"[dim]Skipping conversion. Found {len(images)} existing images.[/dim]")
    completed_units += 1
    _emit("convert", f"Images ready ({len(images)} files)")

    # Recompute totals now that image list is final.
    eval_total = len(patterns) * len(images)
    total_units = eval_total + 3

    # Build reference map: image stem → reference DXF path
    ref_map: dict[str, Path] = {}
    for dxf_path in sorted(settings.dxf_dir.rglob("*.dxf")):
        ref_map[dxf_path.stem] = dxf_path

    # Step 3+4: Generate and evaluate
    client = GeminiCADClient()
    all_results: list[dict] = []

    console.print(f"[bold blue]Step 3/5:[/] Running Gemini generation + evaluation ({len(patterns)} patterns × {len(images)} images)…")
    _emit("evaluate", "Starting generation and evaluation", 0, eval_total)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        total = len(patterns) * len(images)
        task = progress.add_task("Evaluating", total=total)

        for pattern in patterns:
            for img_path in images:
                if should_stop and should_stop():
                    raise InterruptedError("Pipeline stopped by user")
                stem = img_path.stem
                ref_dxf = ref_map.get(stem)

                progress.update(task, description=f"P{pattern.id} | {stem}")

                # Generate
                out_dxf = settings.generated_dir / f"{stem}_p{pattern.id}.dxf"
                try:
                    gen_result = client.generate_cad_from_image(
                        img_path, pattern, out_dxf,
                        should_stop=should_stop,
                    )
                except Exception as exc:
                    # Daily quota exhaustion is fatal — stop the entire pipeline
                    if "Daily Gemini API quota exhausted" in str(exc) or "PerDayPer" in str(exc):
                        raise
                    logger.exception("Generation crashed for %s P%s", stem, pattern.id)
                    all_results.append(
                        {
                            "success": False,
                            "image": str(img_path),
                            "output": str(out_dxf),
                            "pattern_id": pattern.id,
                            "pattern_name": pattern.name,
                            "drawing_name": stem,
                            "error": f"Unhandled generation exception: {exc}",
                            "code_length": 0,
                            "response_length": 0,
                        }
                    )
                    progress.advance(task)
                    completed_units += 1
                    _emit("evaluate", f"P{pattern.id} | {stem}", completed_units - 2, eval_total)
                    continue

                result_dict = gen_result.to_dict()
                result_dict["drawing_name"] = stem

                # Evaluate if generation succeeded and reference exists
                if gen_result.success and ref_dxf and ref_dxf.exists():
                    try:
                        cmp = compare_dxf(ref_dxf, out_dxf, tolerance=settings.dxf_tolerance)
                        result_dict.update(cmp.to_dict())
                    except Exception as exc:
                        logger.warning("Comparison failed for %s: %s", stem, exc)
                        result_dict["comparison_error"] = str(exc)

                all_results.append(result_dict)
                progress.advance(task)
                completed_units += 1
                _emit("evaluate", f"P{pattern.id} | {stem}", completed_units - 2, eval_total)

    # Step 5: Reports
    console.print("[bold blue]Step 5/5:[/] Generating reports…")
    _emit("reports", "Generating reports")
    json_path = generate_json_report(
        all_results,
        settings.reports_dir / "evaluation_report.json",
        metadata={"patterns": [p.name for p in patterns], "model": settings.gemini_model},
    )
    html_path = generate_html_report(
        all_results,
        settings.reports_dir / "evaluation_report.html",
        metadata={"patterns": [p.name for p in patterns], "model": settings.gemini_model},
    )
    excel_path = generate_excel_report(
        all_results,
        settings.reports_dir / "evaluation_report.xlsx",
    )

    sheets_url: str | None = None
    if settings.google_sheet_id:
        if settings.google_sheets_credentials.exists():
            try:
                sheets_url = generate_sheets_report(
                    all_results,
                    credentials_path=settings.google_sheets_credentials,
                    sheet_id=settings.google_sheet_id,
                    tab_name=settings.google_sheet_tab,
                    drive_folder_id=settings.google_drive_folder_id or None,
                )
            except Exception as exc:
                logger.warning("Google Sheets export failed: %s", exc)
        else:
            logger.warning(
                "Skipping Google Sheets export. Credentials file not found: %s",
                settings.google_sheets_credentials,
            )

    console.print("\n[bold green]\u2713 Pipeline complete![/]")
    console.print(f"  JSON report:  {json_path}")
    console.print(f"  HTML report:  {html_path}")
    console.print(f"  Excel report: {excel_path}")
    if sheets_url:
        console.print(f"  Google Sheet: {sheets_url}")

    completed_units += 1
    _emit("done", "Pipeline complete")

    return html_path
