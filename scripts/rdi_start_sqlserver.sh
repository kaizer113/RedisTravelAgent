#!/usr/bin/env bash
# Start SQL Server, initialize CDC and source accounts, then seed missing offers.
# Usage: bash scripts/rdi_start_sqlserver.sh [--no-seed]
set -euo pipefail
set +x
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
seed=true
if [[ "${1:-}" == --no-seed ]]; then seed=false; shift; fi
if [[ $# -ne 0 ]]; then echo 'Usage: rdi_start_sqlserver.sh [--no-seed]' >&2; exit 2; fi
# This file contains locally generated shell-safe secrets. Never commit it.
source "${SQLSERVER_ENV_FILE:-$repo_dir/.env.sqlserver}"
for secret_name in MSSQL_SA_PASSWORD SQLSERVER_CDC_PASSWORD SQLSERVER_EDITOR_PASSWORD; do
  if [[ ! ${!secret_name:-} =~ ^[a-zA-Z0-9_-]{16,128}$ ]]; then
    echo "$secret_name must contain 16–128 shell-safe letters, digits, underscores or hyphens." >&2
    exit 1
  fi
done
umask 077
sqlserver_env=$(mktemp)
trap 'rm -f "$sqlserver_env"' EXIT
printf 'ACCEPT_EULA=Y\nMSSQL_PID=Developer\nMSSQL_AGENT_ENABLED=true\nMSSQL_MEMORY_LIMIT_MB=2048\nMSSQL_SA_PASSWORD=%s\n' "$MSSQL_SA_PASSWORD" > "$sqlserver_env"
sudo docker network inspect value-travel-data >/dev/null 2>&1 || sudo docker network create --label owner=lionel_giavelli --label skip_deletion=yes value-travel-data >/dev/null
sudo docker volume inspect value-travel-sqlserver-data >/dev/null 2>&1 || sudo docker volume create --label owner=lionel_giavelli --label skip_deletion=yes value-travel-sqlserver-data >/dev/null
if sudo docker container inspect value-travel-sqlserver >/dev/null 2>&1; then
  sudo docker start value-travel-sqlserver >/dev/null
else
  sudo docker run -d --name value-travel-sqlserver --restart unless-stopped \
    --memory 3g --memory-swap 3g --env-file "$sqlserver_env" \
    --network value-travel-data --label owner=lionel_giavelli --label skip_deletion=yes \
    -p "${SQLSERVER_BIND_ADDRESS:-10.42.0.3}:1433:1433" \
    -v value-travel-sqlserver-data:/var/opt/mssql \
    --health-cmd 'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -Q "SELECT 1" -o /dev/null' \
    --health-interval 10s --health-start-period 30s --health-retries 30 \
    mcr.microsoft.com/mssql/server:2022-latest >/dev/null
fi
run_sql() {
  sudo docker exec -i value-travel-sqlserver sh -c \
    'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" exec /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -r 1'
}
ready=false
for attempt in $(seq 1 90); do
  if printf 'SET NOCOUNT ON; SELECT 1;\nGO\n' | run_sql >/dev/null 2>&1; then ready=true; break; fi
  sleep 2
done
if [[ "$ready" != true ]]; then echo 'SQL Server did not become ready within 180 seconds.' >&2; exit 1; fi
run_sql < "$repo_dir/deployment/rdi/sqlserver/init.sql" >/dev/null
# The SQL is piped over stdin; credentials are absent from process arguments/logs.
{
  printf "USE master;\nIF SUSER_ID(N'value_travel_cdc') IS NULL CREATE LOGIN value_travel_cdc WITH PASSWORD=N'%s';\n" "$SQLSERVER_CDC_PASSWORD"
  printf "IF SUSER_ID(N'value_travel_editor') IS NULL CREATE LOGIN value_travel_editor WITH PASSWORD=N'%s';\n" "$SQLSERVER_EDITOR_PASSWORD"
  cat <<'SQL'
GRANT VIEW SERVER STATE TO value_travel_cdc;
GRANT VIEW SERVER PERFORMANCE STATE TO value_travel_cdc;
GO
USE value_travel;
IF USER_ID(N'value_travel_cdc') IS NULL CREATE USER value_travel_cdc FOR LOGIN value_travel_cdc;
IF USER_ID(N'value_travel_editor') IS NULL CREATE USER value_travel_editor FOR LOGIN value_travel_editor;
IF IS_ROLEMEMBER(N'value_travel_cdc_reader', N'value_travel_cdc') = 0
  ALTER ROLE value_travel_cdc_reader ADD MEMBER value_travel_cdc;
IF IS_ROLEMEMBER(N'db_datareader', N'value_travel_cdc') = 0
  ALTER ROLE db_datareader ADD MEMBER value_travel_cdc;
GRANT SELECT ON SCHEMA::cdc TO value_travel_cdc;
GRANT VIEW DATABASE STATE TO value_travel_cdc;
GRANT VIEW DATABASE PERFORMANCE STATE TO value_travel_cdc;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.offers TO value_travel_editor;
GO
SQL
} | run_sql >/dev/null
if [[ "$seed" == true ]]; then run_sql < "$repo_dir/deployment/rdi/sqlserver/seed.sql" >/dev/null; fi
echo 'VALUE TRAVEL SQL Server Developer ready: Docker cap 3 GiB, SQL Server target 2048 MiB, CDC polling 1 second.'
