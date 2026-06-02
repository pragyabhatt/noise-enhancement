FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent
COPY frontend/ .
RUN npm run build --silent

FROM python:3.11-slim-bookworm
# System packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    libgomp1 \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*
# Optional build-essential if needed for pip builds (installed conditionally later)
ENV PYTHONUNBUFFERED=1 \
    CATR_OFFLINE=1 \
    OMP_NUM_THREADS=4
WORKDIR /app
COPY backend/ ./backend/
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Copy built frontend assets
COPY --from=frontend-builder /frontend/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
