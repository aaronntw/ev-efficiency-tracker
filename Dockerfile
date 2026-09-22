# Build frontend
FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Production image
FROM python:3.12-slim
WORKDIR /app

ARG APP_VERSION=1.4.3
ARG APP_BUILD_SHA=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    APP_BUILD_SHA=${APP_BUILD_SHA} \
    TZ=UTC \
    DB_TYPE=sqlite \
    SQLITE_PATH=/data/ev_tracker.db \
    WEB_AUTH_ENABLED=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx apache2-utils \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY --from=frontend-build /frontend/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /entrypoint.sh
RUN rm -f /etc/nginx/sites-enabled/default \
    && sed -i 's/\r$//' /entrypoint.sh \
    && chmod +x /entrypoint.sh
EXPOSE 80
VOLUME ["/data"]
ENTRYPOINT ["/entrypoint.sh"]

