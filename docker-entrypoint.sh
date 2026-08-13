#!/bin/sh
set -eu

mkdir -p /data

AUTH_ENABLED=$(printf '%s' "${WEB_AUTH_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')
if [ "$AUTH_ENABLED" = "true" ] || [ "$AUTH_ENABLED" = "1" ] || [ "$AUTH_ENABLED" = "yes" ]; then
    if [ -z "${WEB_AUTH_USERNAME:-}" ] || [ -z "${WEB_AUTH_PASSWORD:-}" ]; then
        echo "ERROR: WEB_AUTH_ENABLED is true but WEB_AUTH_USERNAME or WEB_AUTH_PASSWORD is missing." >&2
        exit 1
    fi
    htpasswd -bc /etc/nginx/.htpasswd "$WEB_AUTH_USERNAME" "$WEB_AUTH_PASSWORD" >/dev/null
    cat > /etc/nginx/conf.d/auth.inc <<'EOF'
auth_basic "EV Efficiency Tracker";
auth_basic_user_file /etc/nginx/.htpasswd;
EOF
else
    echo 'auth_basic off;' > /etc/nginx/conf.d/auth.inc
fi

uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

nginx -g 'daemon off;' &
NGINX_PID=$!

trap 'kill $BACKEND_PID $NGINX_PID 2>/dev/null || true' TERM INT
wait $NGINX_PID
