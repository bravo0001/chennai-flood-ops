# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app.py hydraulics.py router.py drainage_manager.py drainage_service.py ./
COPY static/ ./static/

# Copy data files (GeoJSON - tracked via Git LFS)
COPY chennai_roads_elevated.geojson .
COPY chennai_hospitals.geojson .
COPY chennai_drainage.geojson .
COPY manhole_incidents.json .

# Cloud Run injects PORT env variable
ENV PORT=8080
EXPOSE 8080

# Start server
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
