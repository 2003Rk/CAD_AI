"""Three prompt patterns for CAD generation from images via Gemini."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptPattern:
    name: str
    id: int
    system_prompt: str
    user_prompt_template: str  # {image_description} placeholder

    def format_user_prompt(self, image_description: str = "") -> str:
        return self.user_prompt_template.format(image_description=image_description)


# ---------------------------------------------------------------------------
# Pattern 1: Structured Blueprint
# ---------------------------------------------------------------------------
PATTERN_STRUCTURED = PromptPattern(
    name="Structured Blueprint",
    id=1,
    system_prompt=(
        "You are an expert CAD engineer generating precise ezdxf Python code from engineering drawings.\n\n"
        "REQUIRED FUNCTION SIGNATURE:\n"
        "def generate_dxf(output_path: str):\n"
        "    doc = ezdxf.new(dxfversion='R2010')\n"
        "    msp = doc.modelspace()\n"
        "    # ... add entities ...\n"
        "    doc.saveas(output_path)\n\n"
        "CODE REQUIREMENTS:\n"
        "1. Imports ONLY: ezdxf, math. No other imports.\n"
        "2. Create doc: doc = ezdxf.new(dxfversion='R2010') — NEVER ezdxf.enums.new() or ezdxf.units.new()\n"
        "3. Get modelspace: msp = doc.modelspace()\n"
        "4. Add entities using ONLY: msp.add_line(), msp.add_circle(), msp.add_arc(), msp.add_lwpolyline(), msp.add_text()\n"
        "5. Text format: msp.add_text(text, dxfattribs={'insert': (x, y), 'height': h, 'layer': 'TEXT'})\n"
        "6. MUST end with: doc.saveas(output_path)\n\n"
        "ABSOLUTE PROHIBITIONS:\n"
        "- NO `if __name__ == '__main__':` blocks\n"
        "- NO try/except blocks\n"
        "- NO print() statements\n"
        "- NO ezdxf.enums for text alignment (use ints: halign=0, valign=0)\n"
        "- NO hardcoded file paths — ONLY use output_path\n"
        "- NO creating 'Standard' text style (exists by default)\n"
        "- NO undefined variables or undefined function calls\n\n"
        "Wrap code in ```python ... ``` block. Output ONLY code, no explanation."
    ),
    user_prompt_template=(
        "Analyze this 2D CAD engineering drawing image carefully.\n\n"
        "Identify ALL geometric entities:\n"
        "- Lines and polylines (coordinates, layer)\n"
        "- Circles and arcs (center, radius, angles)\n"
        "- Text and dimensions\n"
        "- Layer organization\n\n"
        "Generate Python code using ezdxf to recreate this drawing as accurately as possible.\n"
        "The drawing should match the original in:\n"
        "- Entity types and counts\n"
        "- Approximate coordinates and dimensions\n"
        "- Layer structure\n"
        "- Overall geometric layout\n\n"
        "{image_description}"
    ),
)

# ---------------------------------------------------------------------------
# Pattern 2: Step-by-Step Construction
# ---------------------------------------------------------------------------
PATTERN_STEPWISE = PromptPattern(
    name="Step-by-Step Construction",
    id=2,
    system_prompt=(
        "You are a CAD drafting assistant. Generate ezdxf code step-by-step to recreate 2D engineering drawings.\n\n"
        "REQUIRED FUNCTION STRUCTURE:\n"
        "def generate_dxf(output_path: str):\n"
        "    doc = ezdxf.new(dxfversion='R2010')\n"
        "    msp = doc.modelspace()\n"
        "    # Step 1: setup layers\n"
        "    # Step 2: draw border\n"
        "    # Step 3: draw outline\n"
        "    # ... more steps ...\n"
        "    doc.saveas(output_path)\n\n"
        "STEP-BY-STEP METHODOLOGY:\n"
        "1. Setup: Create doc, get msp, define layers\n"
        "2. Structural: Draw border, outline, main profile\n"
        "3. Features: Add holes, slots, internal geometry\n"
        "4. Details: Add center marks, construction lines\n"
        "5. Annotations: Add text, dimensions\n"
        "6. Finalize: Call doc.saveas(output_path)\n\n"
        "STRICT CODE RULES (SAME AS PATTERN 1):\n"
        "- Imports ONLY: ezdxf, math\n"
        "- doc = ezdxf.new(dxfversion='R2010') — NEVER ezdxf.enums.new()\n"
        "- NO if __name__ == '__main__':, NO try/except, NO print()\n"
        "- Text: msp.add_text(text, dxfattribs={'insert': (x, y), 'height': h, 'layer': 'TEXT'})\n"
        "- ALWAYS end with doc.saveas(output_path)\n\n"
        "Wrap code in ```python ... ``` block. Output ONLY code with step comments."
    ),
    user_prompt_template=(
        "Look at this engineering drawing image and recreate it using ezdxf Python code.\n\n"
        "Work through the drawing systematically:\n"
        "1. First identify the overall shape and bounding dimensions\n"
        "2. Then identify each feature (holes, slots, fillets, etc.)\n"
        "3. Note any dimensions or text visible\n"
        "4. Identify the layer structure\n\n"
        "Generate the code step by step with clear comments.\n\n"
        "{image_description}"
    ),
)

# ---------------------------------------------------------------------------
# Pattern 3: Reference-Based Recreation
# ---------------------------------------------------------------------------
PATTERN_REFERENCE = PromptPattern(
    name="Reference-Based Recreation",
    id=3,
    system_prompt=(
        "You are a precision CAD replication system. Replicate 2D technical drawings as ezdxf code.\n\n"
        "REQUIRED FUNCTION STRUCTURE:\n"
        "def generate_dxf(output_path: str):\n"
        "    doc = ezdxf.new(dxfversion='R2010')\n"
        "    msp = doc.modelspace()\n"
        "    # Estimate proportions and recreate geometry\n"
        "    msp.add_line(point1, point2)\n"
        "    # ... more entities ...\n"
        "    doc.saveas(output_path)\n\n"
        "REPLICATION FOCUS:\n"
        "- Prioritize geometric accuracy (entity types, spatial relationships)\n"
        "- Estimate coordinates from image proportions\n"
        "- Use standard CAD layer names and conventions\n"
        "- Match entity types (LINE, CIRCLE, ARC, LWPOLYLINE, TEXT)\n\n"
        "STRICT CODE RULES (MUST FOLLOW EXACTLY):\n"
        "- Imports ONLY: ezdxf, math\n"
        "- doc = ezdxf.new(dxfversion='R2010') — NEVER ezdxf.enums.new() or ezdxf.units.new()\n"
        "- msp = doc.modelspace()\n"
        "- Use ONLY msp.add_*() methods: add_line, add_circle, add_arc, add_lwpolyline, add_text\n"
        "- Text: msp.add_text(text, dxfattribs={'insert': (x, y), 'height': h, 'layer': 'TEXT'})\n"
        "- NO if __name__, NO try/except, NO print(), NO undefined variables\n"
        "- MUST end with doc.saveas(output_path)\n\n"
        "Wrap code in ```python ... ``` block. Output ONLY executable code."
    ),
    user_prompt_template=(
        "Replicate this 2D CAD drawing. Study the image and produce ezdxf Python code that "
        "generates a DXF file matching the drawing as closely as possible.\n\n"
        "Focus on:\n"
        "- Getting the proportions right\n"
        "- Matching entity types (lines, circles, arcs, polylines)\n"
        "- Reproducing the spatial relationships between features\n\n"
        "{image_description}"
    ),
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
ALL_PATTERNS: dict[int, PromptPattern] = {
    1: PATTERN_STRUCTURED,
    2: PATTERN_STEPWISE,
    3: PATTERN_REFERENCE,
}


def get_pattern(pattern_id: int) -> PromptPattern:
    if pattern_id not in ALL_PATTERNS:
        raise ValueError(f"Unknown prompt pattern ID: {pattern_id}. Valid: {list(ALL_PATTERNS)}")
    return ALL_PATTERNS[pattern_id]


def get_all_patterns() -> list[PromptPattern]:
    return list(ALL_PATTERNS.values())
