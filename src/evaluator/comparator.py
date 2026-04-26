"""DXF comparison engine — extracts and compares geometric entities between two DXF files."""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf
from scipy.optimize import linear_sum_assignment
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EntityInfo:
    """Normalized representation of a DXF entity."""
    entity_type: str  # LINE, CIRCLE, ARC, LWPOLYLINE, TEXT, etc.
    layer: str = ""
    points: list[tuple[float, float]] = field(default_factory=list)  # key coordinates
    radius: float = 0.0
    text: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class DXFProfile:
    """Extracted profile of a DXF file for comparison."""
    path: Path
    entities: list[EntityInfo] = field(default_factory=list)
    entity_counts: Counter = field(default_factory=Counter)
    layers: set[str] = field(default_factory=set)
    bounding_box: tuple[tuple[float, float], tuple[float, float]] | None = None
    total_entities: int = 0


@dataclass
class ComparisonResult:
    """Detailed comparison between two DXF files."""
    reference_path: Path
    generated_path: Path
    geometry_score: float = 0.0      # 0–100
    structure_score: float = 0.0     # 0–100
    dimension_score: float = 0.0     # 0–100
    metadata_score: float = 0.0      # 0–100
    overall_score: float = 0.0       # weighted 0–100
    details: dict = field(default_factory=dict)

    # Weights
    GEOMETRY_WEIGHT: float = 0.40
    STRUCTURE_WEIGHT: float = 0.30
    DIMENSION_WEIGHT: float = 0.20
    METADATA_WEIGHT: float = 0.10

    def compute_overall(self) -> float:
        self.overall_score = (
            self.geometry_score * self.GEOMETRY_WEIGHT
            + self.structure_score * self.STRUCTURE_WEIGHT
            + self.dimension_score * self.DIMENSION_WEIGHT
            + self.metadata_score * self.METADATA_WEIGHT
        )
        return self.overall_score

    def to_dict(self) -> dict:
        return {
            "reference": str(self.reference_path),
            "generated": str(self.generated_path),
            "geometry_score": round(self.geometry_score, 2),
            "structure_score": round(self.structure_score, 2),
            "dimension_score": round(self.dimension_score, 2),
            "metadata_score": round(self.metadata_score, 2),
            "overall_score": round(self.overall_score, 2),
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# DXF extraction
# ---------------------------------------------------------------------------

def extract_profile(dxf_path: Path) -> DXFProfile:
    """Extract a normalized profile from a DXF file."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    profile = DXFProfile(path=dxf_path)

    all_x: list[float] = []
    all_y: list[float] = []

    for entity in msp:
        info = _extract_entity(entity)
        if info is None:
            continue
        profile.entities.append(info)
        profile.entity_counts[info.entity_type] += 1
        profile.layers.add(info.layer)

        for px, py in info.points:
            all_x.append(px)
            all_y.append(py)

    profile.total_entities = len(profile.entities)

    if all_x and all_y:
        profile.bounding_box = ((min(all_x), min(all_y)), (max(all_x), max(all_y)))

    return profile


def _extract_entity(entity) -> EntityInfo | None:
    """Convert an ezdxf entity to an EntityInfo."""
    dxf_type = entity.dxftype()
    layer = entity.dxf.get("layer", "0")

    if dxf_type == "LINE":
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end = (entity.dxf.end.x, entity.dxf.end.y)
        return EntityInfo(entity_type="LINE", layer=layer, points=[start, end])

    elif dxf_type == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in entity.get_points(format="xy")]
        return EntityInfo(entity_type="LWPOLYLINE", layer=layer, points=pts,
                          extra={"closed": entity.closed, "point_count": len(pts)})

    elif dxf_type == "CIRCLE":
        center = (entity.dxf.center.x, entity.dxf.center.y)
        return EntityInfo(entity_type="CIRCLE", layer=layer, points=[center],
                          radius=entity.dxf.radius)

    elif dxf_type == "ARC":
        center = (entity.dxf.center.x, entity.dxf.center.y)
        return EntityInfo(entity_type="ARC", layer=layer, points=[center],
                          radius=entity.dxf.radius,
                          extra={"start_angle": entity.dxf.start_angle,
                                 "end_angle": entity.dxf.end_angle})

    elif dxf_type == "TEXT":
        insert = (entity.dxf.insert.x, entity.dxf.insert.y)
        return EntityInfo(entity_type="TEXT", layer=layer, points=[insert],
                          text=entity.dxf.text)

    elif dxf_type == "MTEXT":
        insert = (entity.dxf.insert.x, entity.dxf.insert.y)
        return EntityInfo(entity_type="MTEXT", layer=layer, points=[insert],
                          text=entity.text)

    else:
        # Generic fallback
        return EntityInfo(entity_type=dxf_type, layer=layer)


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def compare_dxf(
    reference_path: Path,
    generated_path: Path,
    tolerance: float = 0.5,
) -> ComparisonResult:
    """Compare a generated DXF against a reference DXF.

    Args:
        reference_path: Ground-truth DXF file.
        generated_path: AI-generated DXF file.
        tolerance: Coordinate matching tolerance in drawing units.

    Returns:
        ComparisonResult with sub-scores and overall weighted score.
    """
    ref = extract_profile(reference_path)
    gen = extract_profile(generated_path)

    result = ComparisonResult(reference_path=reference_path, generated_path=generated_path)

    result.geometry_score = _score_geometry(ref, gen, tolerance)
    result.structure_score = _score_structure(ref, gen)
    result.dimension_score = _score_dimensions(ref, gen, tolerance)
    result.metadata_score = _score_metadata(ref, gen)
    result.compute_overall()

    result.details = {
        "ref_entities": ref.total_entities,
        "gen_entities": gen.total_entities,
        "ref_layers": sorted(ref.layers),
        "gen_layers": sorted(gen.layers),
        "ref_entity_counts": dict(ref.entity_counts),
        "gen_entity_counts": dict(gen.entity_counts),
        "ref_bbox": ref.bounding_box,
        "gen_bbox": gen.bounding_box,
    }

    return result


def _score_geometry(ref: DXFProfile, gen: DXFProfile, tolerance: float) -> float:
    """Score based on entity count matching and coordinate proximity."""
    if ref.total_entities == 0:
        return 100.0 if gen.total_entities == 0 else 0.0

    # Entity count similarity
    count_score = _count_similarity(ref.entity_counts, gen.entity_counts)

    # Coordinate matching via optimal assignment
    coord_score = _coordinate_matching_score(ref, gen, tolerance)

    return 0.5 * count_score + 0.5 * coord_score


def _score_structure(ref: DXFProfile, gen: DXFProfile) -> float:
    """Score based on layer names and entity type distribution."""
    if not ref.layers:
        return 100.0

    # Layer name overlap
    common_layers = ref.layers & gen.layers
    layer_score = (len(common_layers) / max(len(ref.layers), 1)) * 100

    # Entity type distribution
    type_score = _count_similarity(ref.entity_counts, gen.entity_counts)

    return 0.6 * layer_score + 0.4 * type_score


def _score_dimensions(ref: DXFProfile, gen: DXFProfile, tolerance: float) -> float:
    """Score based on bounding box and overall dimension accuracy."""
    if ref.bounding_box is None:
        return 100.0 if gen.bounding_box is None else 0.0
    if gen.bounding_box is None:
        return 0.0

    ref_w = ref.bounding_box[1][0] - ref.bounding_box[0][0]
    ref_h = ref.bounding_box[1][1] - ref.bounding_box[0][1]
    gen_w = gen.bounding_box[1][0] - gen.bounding_box[0][0]
    gen_h = gen.bounding_box[1][1] - gen.bounding_box[0][1]

    if ref_w == 0 and ref_h == 0:
        return 100.0

    # Width and height ratio similarity
    w_ratio = min(ref_w, gen_w) / max(ref_w, gen_w) if max(ref_w, gen_w) > 0 else 1.0
    h_ratio = min(ref_h, gen_h) / max(ref_h, gen_h) if max(ref_h, gen_h) > 0 else 1.0

    # Aspect ratio similarity
    ref_aspect = ref_w / ref_h if ref_h > 0 else 1.0
    gen_aspect = gen_w / gen_h if gen_h > 0 else 1.0
    aspect_sim = min(ref_aspect, gen_aspect) / max(ref_aspect, gen_aspect) if max(ref_aspect, gen_aspect) > 0 else 1.0

    # Entity-level dimension matching (circles, lines)
    entity_dim_score = _entity_dimension_score(ref, gen, tolerance)

    return (0.3 * w_ratio + 0.3 * h_ratio + 0.15 * aspect_sim + 0.25 * entity_dim_score) * 100


def _score_metadata(ref: DXFProfile, gen: DXFProfile) -> float:
    """Score based on text content matching."""
    ref_texts = {e.text.strip().upper() for e in ref.entities if e.text.strip()}
    gen_texts = {e.text.strip().upper() for e in gen.entities if e.text.strip()}

    if not ref_texts:
        return 100.0

    common = ref_texts & gen_texts
    return (len(common) / len(ref_texts)) * 100


# ---------------------------------------------------------------------------
# Utility scoring functions
# ---------------------------------------------------------------------------

def _count_similarity(ref_counts: Counter, gen_counts: Counter) -> float:
    """Compute similarity between two entity-type count distributions (0–100)."""
    all_types = set(ref_counts) | set(gen_counts)
    if not all_types:
        return 100.0

    total_ref = sum(ref_counts.values())
    total_gen = sum(gen_counts.values())
    if total_ref == 0:
        return 100.0 if total_gen == 0 else 0.0

    matched = 0
    total = 0
    for t in all_types:
        r = ref_counts.get(t, 0)
        g = gen_counts.get(t, 0)
        matched += min(r, g)
        total += max(r, g)

    return (matched / total) * 100 if total > 0 else 100.0


def _coordinate_matching_score(ref: DXFProfile, gen: DXFProfile, tolerance: float) -> float:
    """Match reference entities to generated entities using optimal assignment."""
    ref_pts = _collect_key_points(ref)
    gen_pts = _collect_key_points(gen)

    if not ref_pts:
        return 100.0 if not gen_pts else 0.0
    if not gen_pts:
        return 0.0

    n = len(ref_pts)
    m = len(gen_pts)

    # Build cost matrix
    max_dist = 1000.0  # penalty for unmatched
    size = max(n, m)
    cost = np.full((size, size), max_dist, dtype=np.float64)

    for i in range(n):
        for j in range(m):
            cost[i, j] = math.dist(ref_pts[i], gen_pts[j])

    row_ind, col_ind = linear_sum_assignment(cost)

    matched = 0
    for r, c in zip(row_ind[:n], col_ind[:n]):
        if cost[r, c] <= tolerance * 10:  # generous tolerance for overall scoring
            matched += 1
        elif cost[r, c] <= tolerance * 50:
            matched += 0.5

    return (matched / n) * 100


def _collect_key_points(profile: DXFProfile) -> list[tuple[float, float]]:
    """Collect representative points from all entities."""
    pts: list[tuple[float, float]] = []
    for e in profile.entities:
        if e.entity_type in ("LINE",):
            pts.extend(e.points)
        elif e.entity_type in ("CIRCLE", "ARC"):
            pts.extend(e.points)  # center point
        elif e.entity_type == "LWPOLYLINE":
            pts.extend(e.points)
        elif e.entity_type in ("TEXT", "MTEXT"):
            pts.extend(e.points)
    return pts


def _entity_dimension_score(ref: DXFProfile, gen: DXFProfile, tolerance: float) -> float:
    """Compare radii of circles/arcs and lengths of lines."""
    ref_radii = sorted(e.radius for e in ref.entities if e.entity_type in ("CIRCLE", "ARC") and e.radius > 0)
    gen_radii = sorted(e.radius for e in gen.entities if e.entity_type in ("CIRCLE", "ARC") and e.radius > 0)

    ref_lengths = sorted(_entity_length(e) for e in ref.entities if e.entity_type == "LINE")
    gen_lengths = sorted(_entity_length(e) for e in gen.entities if e.entity_type == "LINE")

    scores = []
    if ref_radii:
        scores.append(_sorted_list_similarity(ref_radii, gen_radii, tolerance))
    if ref_lengths:
        scores.append(_sorted_list_similarity(ref_lengths, gen_lengths, tolerance * 5))

    return sum(scores) / len(scores) if scores else 1.0


def _entity_length(entity: EntityInfo) -> float:
    if len(entity.points) >= 2:
        return math.dist(entity.points[0], entity.points[1])
    return 0.0


def _sorted_list_similarity(ref: list[float], gen: list[float], tol: float) -> float:
    """Compare two sorted lists of measurements."""
    if not ref:
        return 1.0 if not gen else 0.0
    if not gen:
        return 0.0

    n, m = len(ref), len(gen)
    size = max(n, m)
    cost = np.full((size, size), 1e6, dtype=np.float64)
    for i in range(n):
        for j in range(m):
            cost[i, j] = abs(ref[i] - gen[j])

    row_ind, col_ind = linear_sum_assignment(cost)
    matched = sum(1 for r, c in zip(row_ind[:n], col_ind[:n]) if cost[r, c] <= tol)
    return matched / n
