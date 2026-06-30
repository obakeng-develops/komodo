# Combined Mino web image: the FastAPI backend serves the built SvelteKit SPA
# and /api on one origin. Used by fly.io and by docker-compose's `web` service.

# 1) Build the SPA (adapter-static -> /web/build)
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Backend + the built SPA
FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /web/build ./static
# GET /api/v1/agent/script serves this (ROOT.parent/agent/mino-agent.py -> /agent/...)
COPY agent /agent
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
