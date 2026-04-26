"""CLI entry point — cad-eval command."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from src.config import get_settings

console = Console()


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def main(verbose: bool) -> None:
    """CAD AI Evaluation Pipeline — evaluate Gemini-generated CAD drawings."""
    _setup_logging("DEBUG" if verbose else get_settings().log_level)


# ---------------------------------------------------------------------------
# dataset
# ---------------------------------------------------------------------------

@main.group()
def dataset() -> None:
    """Manage the DXF sample dataset."""


@dataset.command("generate")
def dataset_generate() -> None:
    """Generate 20 sample DXF drawings (10 manufacturing + 10 construction)."""
    from src.dataset.generator import generate_dataset

    settings = get_settings()
    settings.ensure_dirs()
    files = generate_dataset(settings.data_dir)
    console.print(f"[green]Generated {len(files)} DXF files.[/green]")
    for f in files:
        console.print(f"  {f}")


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------

@main.command()
@click.option("--input", "-i", "input_dir", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--output", "-o", "output_dir", type=click.Path(path_type=Path), default=None)
@click.option("--dpi", type=int, default=None)
def convert(input_dir: Path | None, output_dir: Path | None, dpi: int | None) -> None:
    """Convert DXF files to PNG images."""
    from src.converter.dxf_to_image import batch_convert

    settings = get_settings()
    input_dir = input_dir or settings.dxf_dir
    output_dir = output_dir or settings.images_dir
    dpi = dpi or settings.image_dpi

    images = batch_convert(input_dir, output_dir, dpi=dpi, image_format=settings.image_format)
    console.print(f"[green]Converted {len(images)} images.[/green]")


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

@main.command()
@click.option("--prompt-pattern", "-p", "pattern", type=click.Choice(["1", "2", "3", "all"]), default="all")
@click.option("--skip-dataset", is_flag=True, help="Skip dataset generation.")
@click.option("--skip-convert", is_flag=True, help="Skip DXF→image conversion.")
def evaluate(pattern: str, skip_dataset: bool, skip_convert: bool) -> None:
    """Run Gemini generation + DXF comparison evaluation."""
    from src.pipeline import run_full_pipeline

    pattern_ids = None if pattern == "all" else [int(pattern)]
    run_full_pipeline(pattern_ids=pattern_ids, skip_dataset=skip_dataset, skip_convert=skip_convert)


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

@main.command()
@click.argument("reference", type=click.Path(exists=True, path_type=Path))
@click.argument("generated", type=click.Path(exists=True, path_type=Path))
@click.option("--tolerance", "-t", type=float, default=None)
def compare(reference: Path, generated: Path, tolerance: float | None) -> None:
    """Compare two DXF files and display scores."""
    from src.evaluator.comparator import compare_dxf

    settings = get_settings()
    tol = tolerance or settings.dxf_tolerance

    result = compare_dxf(reference, generated, tolerance=tol)

    table = Table(title="DXF Comparison Result")
    table.add_column("Metric", style="bold")
    table.add_column("Score", justify="right")
    table.add_row("Geometry (40%)", f"{result.geometry_score:.1f}")
    table.add_row("Structure (30%)", f"{result.structure_score:.1f}")
    table.add_row("Dimensions (20%)", f"{result.dimension_score:.1f}")
    table.add_row("Metadata (10%)", f"{result.metadata_score:.1f}")
    table.add_row("─" * 20, "─" * 8)
    table.add_row("[bold]Overall[/bold]", f"[bold]{result.overall_score:.1f}[/bold]")
    console.print(table)

    console.print(f"\nRef entities: {result.details.get('ref_entities')}")
    console.print(f"Gen entities: {result.details.get('gen_entities')}")
    console.print(f"Ref layers: {result.details.get('ref_layers')}")
    console.print(f"Gen layers: {result.details.get('gen_layers')}")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@main.command()
@click.option("--input", "-i", "input_json", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--output", "-o", "output_path", type=click.Path(path_type=Path), default=None)
@click.option("--format", "-f", "fmt", type=click.Choice(["html", "json", "both"]), default="both")
def report(input_json: Path | None, output_path: Path | None, fmt: str) -> None:
    """Generate evaluation reports from existing JSON results."""
    import json
    from src.reports.report_gen import generate_html_report, generate_json_report

    settings = get_settings()
    input_json = input_json or settings.reports_dir / "evaluation_report.json"

    if not input_json.exists():
        console.print("[red]No evaluation results found. Run 'evaluate' first.[/red]")
        sys.exit(1)

    data = json.loads(input_json.read_text())
    results = data.get("results", [])

    if fmt in ("json", "both"):
        out = output_path or settings.reports_dir / "evaluation_report.json"
        generate_json_report(results, out)
        console.print(f"[green]JSON report: {out}[/green]")

    if fmt in ("html", "both"):
        out = output_path or settings.reports_dir / "evaluation_report.html"
        generate_html_report(results, out)
        console.print(f"[green]HTML report: {out}[/green]")


# ---------------------------------------------------------------------------
# run (full pipeline shortcut)
# ---------------------------------------------------------------------------

@main.command()
@click.option("--prompt-pattern", "-p", "pattern", type=click.Choice(["1", "2", "3", "all"]), default="all")
@click.option("--skip-dataset", is_flag=True, help="Skip dataset generation (reuse existing DXF files).")
@click.option("--skip-convert", is_flag=True, help="Skip DXF-to-image conversion (reuse existing images).")
def run(pattern: str, skip_dataset: bool, skip_convert: bool) -> None:
    """Run the full pipeline end-to-end."""
    from src.pipeline import run_full_pipeline

    pattern_ids = None if pattern == "all" else [int(pattern)]
    run_full_pipeline(pattern_ids=pattern_ids, skip_dataset=skip_dataset, skip_convert=skip_convert)


@main.command("ui")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host interface to bind.")
@click.option("--port", default=8080, show_default=True, type=int, help="Port to serve the UI on.")
def ui(host: str, port: int) -> None:
    """Start one-click browser UI for the full pipeline."""
    from src.web_ui import run_server

    run_server(host=host, port=port)


@main.command("api")
@click.option("--host", default="0.0.0.0", show_default=True, help="Host interface to bind.")
@click.option("--port", default=8000, show_default=True, type=int, help="Port to serve the API on.")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development.")
def api_server(host: str, port: int, reload: bool) -> None:
    """Start the FastAPI REST backend (for separate frontend hosting)."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is not installed.[/red]")
        console.print("Run: [bold]pip install 'cad-ai-eval[api]'[/bold]")
        sys.exit(1)

    uvicorn.run("src.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
