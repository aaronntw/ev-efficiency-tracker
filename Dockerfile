# Build frontend
FROM node:26.12.1-alpine@sha256:40cd011b55415bc894e45b02fdd5a5dfde056921b7d23a64c74f80497af48797 AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN apk upgrade --no-cache && npm ci
COPY frontend/ .
RUN npm run build

# Production image
FROM python:3.12.15-slim-trixie@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app

ARG APP_VERSION=1.4.4
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
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends nginx apache2-utils ca-certificates \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' nginx)" ge '1.26.3-3+deb13u10' \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data

COPY backend/requirements.txt /app/backend/requirements.txt
# Bootstrap pip's independent CA bundle with the hash published by Python's
# security team before contacting an index with the inherited installer.
RUN python -m pip install --no-cache-dir --no-deps \
    'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70' \
    && python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /app/backend/requirements.txt \
    && python -m pip check
COPY backend /app/backend
COPY scripts/verify_runtime.py /tmp/verify_runtime.py
RUN python /tmp/verify_runtime.py && rm /tmp/verify_runtime.py
COPY --from=frontend-build /frontend/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /entrypoint.sh
RUN rm -f /etc/nginx/sites-enabled/default \
    && sed -i 's/\r$//' /entrypoint.sh \
    && chmod +x /entrypoint.sh
EXPOSE 80
VOLUME ["/data"]
ENTRYPOINT ["/entrypoint.sh"]

