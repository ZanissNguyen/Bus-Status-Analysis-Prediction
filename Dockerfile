# =============================================================================
# Dockerfile: Bus Status Analysis & Prediction
# Multi-stage: installs deps, copies code, auto-runs pipeline if assets missing
# =============================================================================
FROM python:3.10-slim

# --- System dependencies ---
# Install bash (for entrypoint) and git (some pip packages may need it)
RUN apt-get update && \
    apt-get install -y --no-install-recommends bash && \
    rm -rf /var/lib/apt/lists/*

# --- Working directory ---
WORKDIR /app

# --- Python environment ---
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# --- Install Python dependencies (cached layer) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy project source code ---
COPY . .

# --- Make entrypoint executable ---
RUN chmod +x /app/entrypoint.sh

# --- Expose Streamlit port ---
EXPOSE 8501

# --- Entrypoint: check assets → run pipeline if needed → launch Streamlit ---
ENTRYPOINT ["/app/entrypoint.sh"]