"""Gemini API client for CAD generation from images."""

from __future__ import annotations

import logging
import re
import time
import traceback
from pathlib import Path
from typing import Callable

from google import genai
from google.genai import types

from src.config import get_settings
from src.prompts.patterns import PromptPattern

logger = logging.getLogger(__name__)


class GeminiCADClient:
    """Sends CAD images to Gemini and extracts generated DXF code."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self._api_key = api_key or settings.gemini_api_key
        self._model = model or settings.gemini_model
        # Stay on the configured model; do not auto-downgrade to 2.5 variants.
        self._model_fallbacks: list[str] = []
        self._max_retries = settings.max_retries
        self._retry_delay = settings.retry_delay
        self._max_quota_backoff_seconds = settings.max_quota_backoff_seconds
        self._request_timeout_ms = settings.request_timeout_ms
        self._request_timeout_backoff_multiplier = settings.request_timeout_backoff_multiplier
        self._inter_request_delay = settings.inter_request_delay
        self._last_request_ts = 0.0

        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Configure in .env or pass api_key= argument."
            )

        self._client = genai.Client(api_key=self._api_key)

    def generate_cad_from_image(
        self,
        image_path: Path,
        prompt_pattern: PromptPattern,
        output_dxf_path: Path,
        image_description: str = "",
        should_stop: Callable[[], bool] | None = None,
    ) -> "GenerationResult":
        """Send image to Gemini, extract code, execute it to produce DXF.

        Returns a GenerationResult with status details.
        """
        image_path = Path(image_path)
        output_dxf_path = Path(output_dxf_path)
        output_dxf_path.parent.mkdir(parents=True, exist_ok=True)
        # Avoid stale files from previous runs being mistaken as newly generated output.
        if output_dxf_path.exists():
            try:
                output_dxf_path.unlink()
            except Exception:
                pass

        self._throttle_requests()

        # Upload image with retries; transient 5xx can happen under load.
        uploaded_file = None
        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info("Uploading image: %s", image_path.name)
                uploaded_file = self._client.files.upload(file=image_path)
                break
            except Exception as exc:
                logger.warning("Upload attempt %d failed: %s", attempt, exc)
                if attempt < self._max_retries:
                    if should_stop and should_stop():
                        return GenerationResult(
                            success=False,
                            image_path=image_path,
                            output_path=output_dxf_path,
                            pattern=prompt_pattern,
                            raw_response="",
                            error="Stopped by user",
                        )
                    backoff = _compute_retry_backoff(
                        attempt=attempt,
                        exc=exc,
                        base_delay=self._retry_delay,
                        max_backoff=self._max_quota_backoff_seconds,
                    )
                    logger.info("Retrying upload in %.1fs", backoff)
                    time.sleep(backoff)
                else:
                    return GenerationResult(
                        success=False,
                        image_path=image_path,
                        output_path=output_dxf_path,
                        pattern=prompt_pattern,
                        raw_response="",
                        error=f"Image upload failed after {self._max_retries} attempts: {exc}",
                    )

        if uploaded_file is None:
            return GenerationResult(
                success=False,
                image_path=image_path,
                output_path=output_dxf_path,
                pattern=prompt_pattern,
                raw_response="",
                error="Image upload failed: unknown error",
            )

        user_prompt = prompt_pattern.format_user_prompt(image_description)

        raw_response = ""
        for attempt in range(1, self._max_retries + 1):
            attempt_timeout_ms = _compute_attempt_timeout_ms(
                base_timeout_ms=self._request_timeout_ms,
                attempt=attempt,
                multiplier=self._request_timeout_backoff_multiplier,
            )
            try:
                logger.info(
                    "Gemini request attempt %d/%d (pattern: %s, model: %s, timeout: %dms)",
                    attempt,
                    self._max_retries,
                    prompt_pattern.name,
                    self._model,
                    attempt_timeout_ms,
                )
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_uri(
                                    file_uri=uploaded_file.uri,
                                    mime_type=uploaded_file.mime_type,
                                ),
                                types.Part.from_text(text=user_prompt),
                            ],
                        ),
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=prompt_pattern.system_prompt,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                        http_options=types.HttpOptions(timeout=attempt_timeout_ms),
                        temperature=0.2,
                        max_output_tokens=65536,
                    ),
                )
                raw_response = _response_to_text(response)
                break
            except Exception as exc:
                if _is_model_not_found_error(exc):
                    fallback_model = _next_fallback_model(self._model, self._model_fallbacks)
                    if fallback_model:
                        logger.warning(
                            "Model '%s' unavailable; retrying with '%s'",
                            self._model,
                            fallback_model,
                        )
                        self._model = fallback_model
                        continue
                if _is_deadline_exceeded_error(exc) and attempt >= 2:
                    fallback_model = _next_fallback_model(self._model, self._model_fallbacks)
                    if fallback_model:
                        logger.warning(
                            "Request hit DEADLINE_EXCEEDED on '%s'; retrying with faster model '%s'",
                            self._model,
                            fallback_model,
                        )
                        self._model = fallback_model
                if _is_daily_quota_error(exc):
                    logger.error("Daily free-tier quota exhausted — aborting pipeline.")
                    raise RuntimeError(
                        "Daily Gemini API quota exhausted (free tier: 20 req/day for gemini-2.5-flash, "
                        "1500 req/day for gemini-1.5-flash). "
                        "Enable billing at https://console.cloud.google.com/billing or wait until midnight Pacific time."
                    ) from exc
                logger.warning("Attempt %d failed (timeout=%dms): %s", attempt, attempt_timeout_ms, exc)
                if attempt < self._max_retries:
                    if should_stop and should_stop():
                        return GenerationResult(
                            success=False,
                            image_path=image_path,
                            output_path=output_dxf_path,
                            pattern=prompt_pattern,
                            raw_response="",
                            error="Stopped by user",
                        )
                    backoff = _compute_retry_backoff(
                        attempt=attempt,
                        exc=exc,
                        base_delay=self._retry_delay,
                        max_backoff=self._max_quota_backoff_seconds,
                    )
                    logger.info("Retrying in %.1fs", backoff)
                    time.sleep(backoff)
                else:
                    return GenerationResult(
                        success=False,
                        image_path=image_path,
                        output_path=output_dxf_path,
                        pattern=prompt_pattern,
                        raw_response="",
                        error=f"All {self._max_retries} attempts failed: {exc}",
                    )

        # Extract and execute code
        code = _extract_python_code(raw_response)
        if not code:
            return GenerationResult(
                success=False,
                image_path=image_path,
                output_path=output_dxf_path,
                pattern=prompt_pattern,
                raw_response=raw_response,
                error="No Python code block found in Gemini response.",
            )

        exec_error = _execute_dxf_code(code, str(output_dxf_path))
        if exec_error:
            repaired_code = _repair_generated_code_once(code, exec_error)
            if repaired_code and repaired_code != code:
                logger.info("Auto-repair pass triggered for %s", image_path.name)
                # Remove any partial output before repair retry.
                if output_dxf_path.exists():
                    try:
                        output_dxf_path.unlink()
                    except Exception:
                        pass
                repaired_error = _execute_dxf_code(repaired_code, str(output_dxf_path))
                if not repaired_error and output_dxf_path.exists():
                    logger.info("Auto-repair succeeded for %s", output_dxf_path.name)
                    return GenerationResult(
                        success=True,
                        image_path=image_path,
                        output_path=output_dxf_path,
                        pattern=prompt_pattern,
                        raw_response=raw_response,
                        extracted_code=repaired_code,
                    )
                exec_error = f"{exec_error}\n[repair_retry_failed] {repaired_error}"

            return GenerationResult(
                success=False,
                image_path=image_path,
                output_path=output_dxf_path,
                pattern=prompt_pattern,
                raw_response=raw_response,
                extracted_code=code,
                error=f"Code execution failed: {exec_error}",
            )

        if not output_dxf_path.exists():
            # Give the repair one chance: the generated code may have used a hardcoded path.
            repaired_code = _repair_generated_code_once(code, "Code executed but no DXF file was created.")
            if repaired_code and repaired_code != code:
                logger.info("Auto-repair (no-file) triggered for %s", image_path.name)
                if output_dxf_path.exists():
                    try:
                        output_dxf_path.unlink()
                    except Exception:
                        pass
                repaired_error = _execute_dxf_code(repaired_code, str(output_dxf_path))
                if not repaired_error and output_dxf_path.exists():
                    logger.info("Auto-repair (no-file) succeeded for %s", output_dxf_path.name)
                    return GenerationResult(
                        success=True,
                        image_path=image_path,
                        output_path=output_dxf_path,
                        pattern=prompt_pattern,
                        raw_response=raw_response,
                        extracted_code=repaired_code,
                    )
            return GenerationResult(
                success=False,
                image_path=image_path,
                output_path=output_dxf_path,
                pattern=prompt_pattern,
                raw_response=raw_response,
                extracted_code=code,
                error="Code executed but no DXF file was created.",
            )

        logger.info("Successfully generated: %s", output_dxf_path.name)
        return GenerationResult(
            success=True,
            image_path=image_path,
            output_path=output_dxf_path,
            pattern=prompt_pattern,
            raw_response=raw_response,
            extracted_code=code,
        )

    def _throttle_requests(self) -> None:
        """Rate-limit requests to reduce chance of 429 quota errors."""
        if self._inter_request_delay <= 0:
            self._last_request_ts = time.monotonic()
            return

        now = time.monotonic()
        elapsed = now - self._last_request_ts
        if elapsed < self._inter_request_delay:
            time.sleep(self._inter_request_delay - elapsed)
        self._last_request_ts = time.monotonic()


class GenerationResult:
    """Captures the outcome of a single Gemini CAD generation attempt."""

    def __init__(
        self,
        *,
        success: bool,
        image_path: Path,
        output_path: Path,
        pattern: PromptPattern,
        raw_response: str = "",
        extracted_code: str = "",
        error: str = "",
    ):
        self.success = success
        self.image_path = image_path
        self.output_path = output_path
        self.pattern = pattern
        self.raw_response = raw_response
        self.extracted_code = extracted_code
        self.error = error

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "image": str(self.image_path),
            "output": str(self.output_path),
            "pattern_id": self.pattern.id,
            "pattern_name": self.pattern.name,
            "error": self.error,
            "code_length": len(self.extracted_code),
            "response_length": len(self.raw_response),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
# Also match single-backtick fenced blocks and bare code
_CODE_BLOCK_ALT_RE = re.compile(r"`(?:python)?\s*\n(.*?)`", re.DOTALL)


def _response_to_text(response) -> str:
    """Extract text from Gemini response with robust fallbacks.

    The SDK `response.text` can be empty for some responses even when candidates
    contain text parts, so we aggregate parts as a fallback.
    """
    text = getattr(response, "text", None)
    if text:
        return text

    chunks: list[str] = []
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                chunks.append(part_text)

    return "\n".join(chunks).strip()


def _compute_retry_backoff(
    *,
    attempt: int,
    exc: Exception,
    base_delay: float,
    max_backoff: int,
) -> float:
    """Compute retry backoff using API retry hints when available."""
    message = str(exc)
    retry_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
    if retry_match:
        hinted = float(retry_match.group(1))
        return min(max(hinted, base_delay), float(max_backoff))

    if _is_deadline_exceeded_error(exc):
        # 504 deadline errors often clear with slightly slower pacing.
        deadline_backoff = base_delay * (2 ** (attempt - 1)) * 1.5
        return min(deadline_backoff, float(max_backoff))

    return min(base_delay * (2 ** (attempt - 1)), float(max_backoff))


def _compute_attempt_timeout_ms(*, base_timeout_ms: int, attempt: int, multiplier: float) -> int:
    """Increase request timeout each attempt to absorb transient model latency."""
    timeout = int(base_timeout_ms * (multiplier ** (attempt - 1)))
    return min(timeout, 300000)


def _is_model_not_found_error(exc: Exception) -> bool:
    """Return True when API says selected model is unavailable for endpoint/method."""
    msg = str(exc).lower()
    return "404" in msg and "not found" in msg and "model" in msg


def _is_daily_quota_error(exc: Exception) -> bool:
    """Return True when the per-day free-tier quota is exhausted.

    Retrying will never succeed until midnight — abort immediately.
    """
    msg = str(exc)
    return "PerDayPer" in msg or "GenerateRequestsPerDay" in msg


def _is_deadline_exceeded_error(exc: Exception) -> bool:
    """Return True when upstream timed out before completion."""
    msg = str(exc).upper()
    return "DEADLINE_EXCEEDED" in msg or "504" in msg


def _next_fallback_model(current: str, fallback_models: list[str]) -> str | None:
    """Pick next fallback model different from current one."""
    for candidate in fallback_models:
        if candidate != current:
            return candidate
    return None


def _extract_python_code(response: str) -> str:
    """Extract Python code from a Gemini markdown response."""
    # Try triple-backtick fenced blocks first
    matches = _CODE_BLOCK_RE.findall(response)
    if matches:
        return max(matches, key=len).strip()

    # Fallback: if response looks like raw Python code
    stripped = response.strip()
    if stripped.startswith(("import ", "def ", "from ")):
        return stripped

    # Try to find code-like content: lines starting with import/def/from
    lines = response.split("\n")
    code_lines: list[str] = []
    in_code = False
    for line in lines:
        stripped_line = line.strip()
        if not in_code and stripped_line.startswith(("import ", "from ", "def ")):
            in_code = True
        if in_code:
            # Stop at obviously non-code prose lines
            if stripped_line and not any([
                stripped_line.startswith(("import ", "from ", "def ", "class ",
                    "#", "if ", "for ", "while ", "return ", "    ", "\t",
                    "msp.", "doc.", "doc ", ")", "(", "]", "[", "}", "{",
                    "output_path", "generate_", "main(",)),
                stripped_line[0].isspace(),
                stripped_line.startswith(tuple("=+-*/:,@")),
                len(stripped_line) > 0 and stripped_line[0].isalpha() and "=" in stripped_line,
                len(stripped_line) > 0 and stripped_line[0].isalpha() and "(" in stripped_line,
            ]):
                # Likely prose — stop
                break
            code_lines.append(line)

    if code_lines and len("\n".join(code_lines)) > 50:
        return "\n".join(code_lines).strip()

    return ""


def _preprocess_code(code: str, output_path: str) -> str:
    """Clean up common Gemini code patterns that break in our sandbox."""
    import re as _re

    # Remove `if __name__ == "__main__":` blocks — inline their body
    lines = code.split("\n")
    cleaned: list[str] = []
    skip_main = False
    main_indent = 0
    main_body: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("if __name__") and "__main__" in stripped:
            skip_main = True
            main_indent = len(line) - len(line.lstrip())
            continue
        if skip_main:
            if line.strip() == "" or (len(line) - len(line.lstrip()) > main_indent):
                # Dedent the body
                if line.strip():
                    dedented = line[main_indent + 4:] if len(line) > main_indent + 4 else line.lstrip()
                    main_body.append(dedented)
                else:
                    main_body.append("")
                continue
            else:
                skip_main = False
                cleaned.extend(main_body)
                main_body = []

    if main_body:
        cleaned.extend(main_body)

    if cleaned:
        code = "\n".join(lines[:len(lines) - len(main_body) - 1 - (1 if skip_main else 0)])
        # Re-parse: remove __name__ block and append dedented body
        result_lines = []
        in_main = False
        indent_size = 0
        body_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("if __name__") and "__main__" in stripped:
                in_main = True
                indent_size = len(line) - len(line.lstrip())
                continue
            if in_main:
                if stripped == "":
                    body_lines.append("")
                    continue
                current_indent = len(line) - len(line.lstrip())
                if current_indent > indent_size:
                    body_lines.append(line[indent_size + 4:] if len(line) > indent_size + 4 else line.lstrip())
                    continue
                else:
                    in_main = False
                    result_lines.extend(body_lines)
                    body_lines = []
            result_lines.append(line)
        if body_lines:
            result_lines.extend(body_lines)
        code = "\n".join(result_lines)

    # Fix hardcoded DXF output paths in saveas/save calls — replace with output_path variable.
    # Handles: doc.saveas("output.dxf"), doc.saveas('drawing.dxf'), doc.save("file.dxf"), etc.
    code = _re.sub(r'(\.saveas|\.save)\(\s*[\'"][^\'"]*\.dxf[\'"]\s*\)', r'\1(output_path)', code)

    # Replace deprecated set_pos → use dxf.insert
    code = code.replace(".set_pos(", ".dxf.__setattr__('insert', ")

    # Fix ezdxf.enums.new() → ezdxf.new() (Gemini confuses the submodule)
    code = _re.sub(r'ezdxf\.enums\.new\(', 'ezdxf.new(', code)
    code = _re.sub(r'ezdxf\.units\.new\(', 'ezdxf.new(', code)

    # Fix is_closed= → close= (wrong kwarg name; ezdxf uses close=)
    code = _re.sub(r'\bis_closed\s*=\s*(True|False)', lambda m: f'close={m.group(1)}', code)

    return code


def _validate_code(code: str) -> str | None:
    """Validate generated code before execution. Returns error string or None."""
    # Security: check for forbidden module imports before anything else.
    _ALLOWED_TOP_MODULES = frozenset({"ezdxf", "math"})
    for m in re.finditer(r"^\s*import\s+([\w.]+)", code, re.MULTILINE):
        top = m.group(1).split(".")[0]
        if top not in _ALLOWED_TOP_MODULES:
            return f"Import of '{top}' is not allowed"
    for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import", code, re.MULTILINE):
        top = m.group(1).split(".")[0]
        if top not in _ALLOWED_TOP_MODULES:
            return f"Import of '{top}' is not allowed"

    # Require either a runnable function entrypoint or script-style create+save flow,
    # but only when the code actually attempts to create a DXF document.
    if "ezdxf.new(" in code:
        has_entrypoint = ("def generate_dxf" in code) or ("def main" in code)
        has_script_flow = ".saveas(" in code
        if not has_entrypoint and not has_script_flow:
            return "Missing required function: def generate_dxf(output_path: str) or def main()"

    # Check for forbidden patterns
    forbidden = [
        ("if __name__", "Contains forbidden if __name__ == '__main__': block"),
        (".set_pos(", "Uses deprecated .set_pos() method"),
        ("ezdxf.enums.new(", "Uses forbidden ezdxf.enums.new()"),
        ("ezdxf.units.new(", "Uses forbidden ezdxf.units.new()"),
    ]
    for pattern, msg in forbidden:
        if pattern in code:
            return msg
    
    # Check syntax
    try:
        compile(code, "<validation>", "exec")
    except SyntaxError as e:
        return f"Syntax error: {e.msg} at line {e.lineno}"
    
    return None


def _repair_generated_code_once(code: str, exec_error: str) -> str | None:
    """Best-effort one-pass repair before giving up.

    This function intentionally applies only small, safe transformations.
    """
    repaired = code

    # Fix is_closed= → close= (wrong kwarg name; ezdxf uses close=)
    repaired = re.sub(r'\bis_closed\s*=\s*(True|False)', lambda m: f'close={m.group(1)}', repaired)

    # Fix hardcoded DXF paths in saveas/save calls (Gemini often ignores the output_path param)
    repaired = re.sub(r'(\.saveas|\.save)\(\s*[\'"][^\'"]*\.dxf[\'"]\s*\)', r'\1(output_path)', repaired)

    # Normalize mistaken save method variants.
    repaired = repaired.replace("doc.save(output_path)", "doc.saveas(output_path)")

    # If code doesn't save, inject saveas into known entrypoints.
    needs_save = ".saveas(" not in repaired
    if needs_save:
        for fn in ("generate_dxf", "main"):
            updated = _inject_saveas_call(repaired, fn)
            if updated != repaired:
                repaired = updated
                needs_save = False
                break

    # If generate_dxf is missing but main exists, add a tiny wrapper.
    if "def generate_dxf" not in repaired and "def main" in repaired:
        repaired += (
            "\n\n"
            "def generate_dxf(output_path: str):\n"
            "    main()\n"
            "    try:\n"
            "        doc.saveas(output_path)\n"
            "    except Exception:\n"
            "        pass\n"
        )

    return repaired if repaired != code else None


def _inject_saveas_call(code: str, function_name: str) -> str:
    """Insert doc.saveas(output_path) at the end of a function body if missing."""
    lines = code.split("\n")
    def_idx = None
    def_indent = 0

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith(f"def {function_name}("):
            def_idx = i
            def_indent = len(line) - len(stripped)
            break

    if def_idx is None:
        return code

    body_start = def_idx + 1
    body_indent = def_indent + 4
    end_idx = len(lines)
    for i in range(body_start, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= def_indent:
            end_idx = i
            break

    body = lines[body_start:end_idx]
    if any(".saveas(" in ln for ln in body):
        return code

    insert_line = " " * body_indent + "doc.saveas(output_path)"
    lines.insert(end_idx, insert_line)
    return "\n".join(lines)


def _execute_dxf_code(code: str, output_path: str) -> str | None:
    """Execute extracted ezdxf code in a restricted namespace.

    Returns None on success, or an error string on failure.
    """
    import builtins as _builtins
    import importlib
    import math

    import ezdxf

    _ALLOWED_MODULES = frozenset({
        "ezdxf", "math", "ezdxf.units", "ezdxf.enums",
        "ezdxf.document", "ezdxf.math", "ezdxf.entities",
        "ezdxf.lldxf", "ezdxf.lldxf.const",
    })

    def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name not in _ALLOWED_MODULES:
            raise ImportError(f"Import of '{name}' is not allowed. Permitted: {sorted(_ALLOWED_MODULES)}")
        mod = importlib.import_module(name)
        # For plain `import a.b.c` (empty fromlist), Python expects the
        # top-level package so it can bind `a` in the caller's namespace.
        # For `from a.b import X` (non-empty fromlist), return the submodule.
        if not fromlist and "." in name:
            return importlib.import_module(name.split(".")[0])
        return mod

    safe_builtins = {
        k: getattr(_builtins, k)
        for k in (
            "abs", "all", "any", "bool", "dict", "enumerate", "float",
            "int", "isinstance", "len", "list", "map", "max", "min",
            "print", "range", "round", "set", "sorted", "str", "sum",
            "tuple", "type", "zip", "True", "False", "None",
            "ValueError", "TypeError", "Exception",
        )
        if hasattr(_builtins, k)
    }
    safe_builtins["__import__"] = _restricted_import

    # Preprocess first to fix common Gemini patterns before validation.
    code = _preprocess_code(code, output_path)

    # Validate preprocessed code before execution.
    validation_error = _validate_code(code)
    if validation_error:
        return f"Code validation failed: {validation_error}"

    namespace: dict = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
        "output_path": output_path,
        "ezdxf": ezdxf,
        "math": math,
    }

    def _try_call(func, *args):
        """Call a generated function with light signature fallback."""
        try:
            return func(*args)
        except TypeError:
            # Some generated functions are defined without output_path args.
            if args:
                return func()
            raise

    def _autosave_from_namespace(ns: dict, out_path: str) -> bool:
        """Best-effort save when model created a doc but forgot to call saveas."""
        for value in ns.values():
            saveas = getattr(value, "saveas", None)
            if callable(saveas):
                try:
                    saveas(out_path)
                    return True
                except Exception:
                    continue
        return False

    try:
        exec(compile(code, "<gemini_generated>", "exec"), namespace)

        # Call generate_dxf if it exists
        if "generate_dxf" in namespace and callable(namespace["generate_dxf"]):
            _try_call(namespace["generate_dxf"], output_path)
        # Also try main() if generate_dxf wasn't found
        elif "main" in namespace and callable(namespace["main"]):
            _try_call(namespace["main"], output_path)

        # Some outputs define a document but forget to save it.
        if not Path(output_path).exists():
            _autosave_from_namespace(namespace, output_path)

        return None
    except Exception:
        return traceback.format_exc()
