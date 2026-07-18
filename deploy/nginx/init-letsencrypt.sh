#!/usr/bin/env bash
# One-time bootstrap: obtains a Let's Encrypt certificate for DOMAIN using
# the certbot container defined in docker-compose.yml (profile "certbot").
#
# Prerequisites:
#   - DNS for DOMAIN already points at this host's public IP
#   - `docker compose up -d` is already running so nginx is serving :80
#     (the acme-challenge location in rag-chatbot.conf must be reachable)
#
# Usage: ./deploy/nginx/init-letsencrypt.sh api.example.com you@example.com
set -euo pipefail

DOMAIN="${1:?Usage: init-letsencrypt.sh <domain> <email>}"
EMAIL="${2:?Usage: init-letsencrypt.sh <domain> <email>}"

docker compose --profile certbot run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    -d $DOMAIN \
    --email $EMAIL \
    --agree-tos \
    --non-interactive" certbot

cat <<MSG

Certificate obtained for $DOMAIN.

Next steps:
  1. In deploy/nginx/rag-chatbot.conf, replace YOUR_DOMAIN with $DOMAIN and
     uncomment the HTTPS server block plus the HTTP->HTTPS redirect block.
  2. docker compose restart nginx
  3. Certs expire every 90 days; schedule renewal, e.g. a cron entry running:
     docker compose --profile certbot run --rm certbot renew && docker compose restart nginx
MSG
