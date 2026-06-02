# Dockerfile for DEAL Dashboard
# Multi‑stage build: backend (Python) + frontend (Vite/React)

# ---------- Base image with runtime dependencies ----------
FROM python:3.11-slim-bookworm AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 libgomp1 ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Copy backend source and install Python deps
COPY backend/ ./backend
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Frontend build stage ----------
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---------- Final image ----------
FROM base AS final
WORKDIR /app
# Copy compiled frontend assets into the FastAPI static folder
COPY --from=frontend-builder /frontend/dist ./backend/app/static
# Copy backend code (already in /app from base stage)
COPY --from=base /app .

EXPOSE 8000
ENV PYTHONUNBUFFERED=1
ENV CATR_OFFLINE=1
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
