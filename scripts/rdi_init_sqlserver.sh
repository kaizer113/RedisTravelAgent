#!/usr/bin/env bash
# Initialize the existing GKE SQL Server database, CDC, and source accounts.
# Usage: bash scripts/rdi_init_sqlserver.sh [--no-seed]
set -euo pipefail
set +x
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
seed=true
if [[ "${1:-}" == --no-seed ]]; then seed=false; shift; fi
if [[ $# -ne 0 ]]; then echo 'Usage: rdi_init_sqlserver.sh [--no-seed]' >&2; exit 2; fi
# This file contains locally generated shell-safe secrets. Never commit it.
source "${SQLSERVER_ENV_FILE:-$repo_dir/.env.sqlserver}"
for secret_name in SQLSERVER_CDC_PASSWORD SQLSERVER_EDITOR_PASSWORD; do
  if [[ ! ${!secret_name:-} =~ ^[a-zA-Z0-9_-]{16,128}$ ]]; then
    echo "$secret_name must contain 16–128 shell-safe letters, digits, underscores or hyphens." >&2
    exit 1
  fi
done
gke_context=${GKE_CONTEXT:-gke_central-beach-194106_us-east4_lionel-iris-peered}
kubectl --context "$gke_context" --namespace demo-access rollout status deployment/sqlserver --timeout=180s
run_sql() {
  kubectl --context "$gke_context" --namespace demo-access exec -i deployment/sqlserver -- sh -c \
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
echo 'VALUE TRAVEL database and CDC ready on GKE SQL Server.'
