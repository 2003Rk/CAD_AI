"""Convert DXF files to PNG images for Gemini vision input."""

from __future__ import annotations

import logging
from pathlib import Path

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib

# Use a non-GUI backend so conversion works in worker threads (e.g., web UI on macOS).
matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)


def dxf_to_image(
    dxf_path: Path,
    output_path: Path,
    *,
    dpi: int = 300,
    image_format: str = "png",
    bg_color: str = "#FFFFFF",
    line_color: str = "#000000",
) -> Path:
    """Render a DXF file to a raster image.

    Args:
        dxf_path: Path to input DXF file.
        output_path: Path for the output image (directory or file).
        dpi: Image resolution.
        image_format: Output format (png, jpg, etc.).
        bg_color: Background color.
        line_color: Default line color.

    Returns:
        Path to the created image file.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    fig: Figure = plt.figure(dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(bg_color)

    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp)

    ax.set_axis_off()
    ax.autoscale(True)
    ax.set_aspect("equal")

    if output_path.is_dir():
        out_file = output_path / f"{dxf_path.stem}.{image_format}"
    else:
        out_file = output_path

    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_file), dpi=dpi, bbox_inches="tight", pad_inches=0.1, facecolor=bg_color)
    plt.close(fig)

    logger.info("Converted %s → %s", dxf_path.name, out_file)
    return out_file


def batch_convert(
    input_dir: Path,
    output_dir: Path,
    *,
    dpi: int = 300,
    image_format: str = "png",
    recursive: bool = True,
) -> list[Path]:
    """Convert all DXF files in a directory to images.

    Preserves subdirectory structure (manufacturing/, construction/).
    """
    pattern = "**/*.dxf" if recursive else "*.dxf"
    dxf_files = sorted(input_dir.glob(pattern))

    if not dxf_files:
        logger.warning("No DXF files found in %s", input_dir)
        return []

    created: list[Path] = []
    for dxf_path in dxf_files:
        rel = dxf_path.relative_to(input_dir)
        out_subdir = output_dir / rel.parent
        out_subdir.mkdir(parents=True, exist_ok=True)

        try:
            img_path = dxf_to_image(dxf_path, out_subdir, dpi=dpi, image_format=image_format)
            created.append(img_path)
        except Exception:
            logger.exception("Failed to convert %s", dxf_path)

    logger.info("Converted %d / %d DXF files to images.", len(created), len(dxf_files))
    return created
