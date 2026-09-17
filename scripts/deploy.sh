#!/usr/bin/env bash
set -euo pipefail
cd /opt/value-travel
sudo docker build -t value-travel:local .
sudo docker rm -f value-travel-agent 2>/dev/null || true
sudo docker run -d --name value-travel-agent --restart unless-stopped \
 --label owner=lionel_giavelli --label skip_deletion=yes \
 --env-file .env --network value-travel-data -p 8080:8080 \
 --health-cmd='/app/.venv/bin/python /app/valuetravel/healthcheck.py' \
 --health-interval=30s --health-start-period=60s value-travel:local
