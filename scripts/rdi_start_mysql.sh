#!/usr/bin/env bash
# Run from the VM's ~/value-travel-data directory after copying init.sql/.env.rdi.
set -euo pipefail
set +x
if sudo docker container inspect value-travel-mysql >/dev/null 2>&1; then
  sudo docker start value-travel-mysql >/dev/null
  echo 'Existing VALUE TRAVEL MySQL started; data and credentials retained.'
  exit 0
fi
sudo docker network inspect value-travel-data >/dev/null 2>&1 || sudo docker network create --label owner=lionel_giavelli --label skip_deletion=yes value-travel-data >/dev/null
sudo docker volume inspect value-travel-mysql-data >/dev/null 2>&1 || sudo docker volume create --label owner=lionel_giavelli --label skip_deletion=yes value-travel-mysql-data >/dev/null
# .env.rdi contains only locally generated shell-safe secrets.
set -a
source .env.rdi
set +a
# Transform the named CDC secret into MySQL's expected variable without printing it.
MYSQL_PASSWORD="$MYSQL_CDC_PASSWORD"
export MYSQL_PASSWORD
umask 077
mysql_env=$(mktemp)
trap 'rm -f "$mysql_env"' EXIT
printf 'MYSQL_ROOT_PASSWORD=%s\nMYSQL_PASSWORD=%s\nMYSQL_DATABASE=value_travel\nMYSQL_USER=value_travel_cdc\n' "$MYSQL_ROOT_PASSWORD" "$MYSQL_PASSWORD" > "$mysql_env"
sudo docker run -d --name value-travel-mysql --restart unless-stopped \
 --memory 768m --cpus 0.75 --env-file "$mysql_env" \
 --network value-travel-data --label owner=lionel_giavelli --label skip_deletion=yes \
 -p "${MYSQL_BIND_ADDRESS:-10.42.0.3}:3307:3306" \
 -v value-travel-mysql-data:/var/lib/mysql \
 -v "$PWD/init.sql:/docker-entrypoint-initdb.d/10-travel.sql:ro" \
 --health-cmd 'mysqladmin ping -h localhost --silent' --health-interval 10s --health-retries 30 \
 mysql:8.0.44 --server-id=782179 --log-bin=mysql-bin --binlog-format=ROW \
 --binlog-row-image=FULL --binlog-expire-logs-seconds=864000 --gtid-mode=ON \
 --enforce-gtid-consistency=ON --binlog-rows-query-log-events=ON --innodb-buffer-pool-size=128M >/dev/null
echo 'VALUE TRAVEL MySQL container created.'
