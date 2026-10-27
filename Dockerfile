# Optional future single-origin deployment. No deploy is performed by this file.
FROM node:22-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
COPY apps/frontend/package.json apps/frontend/package.json
RUN npm ci
COPY apps/frontend apps/frontend
COPY apps/backend/app/data/category_icons.json apps/backend/app/data/category_icons.json
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-liberation fonts-dejavu-core curl ca-certificates \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl --fail --silent --show-error https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY apps/backend/requirements.txt apps/backend/constraints-local.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints-local.txt
COPY apps/backend /app/apps/backend
COPY --from=frontend /build/apps/frontend/dist /app/apps/frontend/dist
ENV FRONTEND_DIST=/app/apps/frontend/dist STORAGE_PATH=/data PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN mkdir -p /data/images /data/voice /data/pdfs /data/passports
WORKDIR /app/apps/backend
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
