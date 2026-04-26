FROM python:3.12-slim AS base

# Prevent bytecode and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for matplotlib rendering
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "." 2>/dev/null || \
    pip install --no-cache-dir \
        "ezdxf>=1.3.0" "Pillow>=10.0" "matplotlib>=3.8" "numpy>=1.26" \
        "google-genai>=1.0.0" "scipy>=1.12" "jinja2>=3.1" \
        "pydantic>=2.5" "pydantic-settings>=2.1" "click>=8.1" \
        "rich>=13.7" "python-dotenv>=1.0"

# Copy source
COPY src/ src/
COPY data/dxf/ data/dxf/
COPY pyproject.toml README.md ./

# Install the package
RUN pip install --no-cache-dir -e .

# Create output directories
RUN mkdir -p data/images data/generated output/reports output/comparisons

# Non-root user for security
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["cad-eval"]
CMD ["--help"]
