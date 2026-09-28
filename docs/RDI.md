# VALUE TRAVEL: SQL Server to Redis Data Integration

The fictional offer table is `value_travel.dbo.offers`. Its ten source fields feed
`valuetravel/context_models.py`'s Offer. RDI is configured to write Redis JSON documents at keys
`value-travel:context:offer:VT-001` through `VT-018`. Context Retriever reads those
documents. The Redis JSON documents contain the ten source fields plus the RDI-calculated
`average_price_per_person`; there are no internal metadata fields to preserve. RDI adds `ROUND(total_price / room_capacity, 2)` with a SQL `add_field` transform
and replaces each document with the mapped source and calculated fields. Capacity
means people accommodated by the offer; it is independent of available room count. SQL Server remains authoritative for current prices and room availability.

## Current state

SQL Server Developer and RDI 2.0.0 run on the existing regional GKE cluster
`lionel-iris-peered`. The shared VM `valuewholesale-demo` continues to run the
concierge on port 8080 and the other demos, including the original port-80 demo.
SQL Server is no longer hosted in a container on that VM, and the dedicated
`lg-rdi` VM is retired after migration verification.

SQL Server has one replica, a hard container limit of 3,000,000,000 bytes (3 GB),
and `MSSQL_MEMORY_LIMIT_MB=2048`. Its 20 GiB persistent disk has a Retain reclaim
policy. SQL Server Agent is enabled, with native Change Data Capture on database
`value_travel` and table `dbo.offers`. RDI uses a dedicated CDC account; Studio
uses a separate table-scoped editor account.

| Resource | Configuration |
| --- | --- |
| Project / region | `central-beach-194106` / `us-east4` |
| GKE cluster | `lionel-iris-peered` |
| Kubernetes context | `gke_central-beach-194106_us-east4_lionel-iris-peered` |
| RDI namespace / API service | `rdi` / `rdi-api:8080` |
| SQL namespace / deployment | `demo-access` / `sqlserver` |
| SQL source for RDI | `sqlserver.demo-access.svc.cluster.local:1433` |
| SQL source for application | private gateway `10.42.0.9:1433` |
| Source database / schema / table | `value_travel` / `dbo` / `offers` |
| RDI API for administrator | `https://35.245.24.240` |
| SQL endpoint for administrator | `35.245.24.240:1433` |
| State database | `men-outstanding-mercurial-20861.db.redis.io:17168` |
| Application Redis target | `cantabile-consummate-micropolished-92484.db.redis.io:17518` |
| Pipeline / processor / job | `default` / `classic` / `value_travel_offers` |
| SQL persistent volume claim | `demo-access/sqlserver-data`, 20 GiB, Retain |

The private gateway permits source `10.42.0.3/32`; the public gateway permits the
configured administrator IP. Kubernetes network policy allows RDI-to-SQL traffic.
SQL requires TLS; the demo certificate covers both gateway IPs and the internal
SQL service DNS name. CA material and credentials come from the separate Iris
workspace's `CONNECTIONS.md` and private connection bundle. Credentials are never
committed. Supported resources carry `owner=lionel_giavelli,skip_deletion=yes`.

This migration changes only the SQL/RDI hosting. The application Redis target,
managed Agent Memory, LangCache, and Context Retriever services retain their
existing endpoints and data. The GKE RDI state database is separate from the
application Redis target; do not repoint offers at the state database.

## Files

- `deployment/rdi/sqlserver/init.sql`: database, offer schema and native CDC setup.
- `deployment/rdi/sqlserver/seed.sql`: 18 fictional baseline offers.
- `scripts/rdi_init_sqlserver.sh`: initialize the existing GKE SQL deployment and separate CDC/editor accounts.
- `scripts/rdi_generate_sqlserver_seed.py`: regenerate `seed.sql` from `valuetravel/data.py`.
- `deployment/rdi/config.yaml`: deployed collector/target configuration.
- `deployment/rdi/jobs/offers.yaml`: exact JSON Offer mapping for Context Retriever.
- `scripts/rdi_deploy.py`: configure scoped secrets, validate and deploy through the GKE RDI API.
- `scripts/rdi_offer.py`: update only SQL Server and optionally observe Redis propagation.

The seed inserts missing baseline offers without overwriting existing source edits.
Retain the SQL persistent volume when recreating a pod; do not delete its underlying disk.

## Install and operate

The existing cluster and its SQL persistent volume are managed from the Iris
workspace. Do not reinstall RDI on a VM or recreate the SQL persistent volume.
Connect to the cluster before running the Kubernetes operations:

```sh
export PATH="$PATH:/opt/homebrew/share/google-cloud-sdk/bin"
gcloud container clusters get-credentials lionel-iris-peered --region us-east4 --project central-beach-194106
kubectl -n demo-access get deployment sqlserver
kubectl -n rdi get deployments,pods
```

Initialize the existing SQL deployment using a private `.env.sqlserver` containing
`SQLSERVER_CDC_PASSWORD` and `SQLSERVER_EDITOR_PASSWORD`:

```sh
bash scripts/rdi_init_sqlserver.sh --no-seed
```

Omit `--no-seed` only to insert missing baseline offers into a fresh demo.
`GKE_CONTEXT` overrides the default context shown above. The script operates on
the existing deployment rather than creating another SQL container or disk.
The Studio uses its separate `STUDIO_SQLSERVER_*` configuration and never uses
`sa`. The application image includes the public CA and FreeTDS configuration for
encryption and hostname validation. Preserve current source rows when initializing
the database; seed fixtures are not a replacement for live source edits.

The RDI API requires CA-validated HTTPS and a bearer token. Use the connection
bundle from the Iris workspace; `scripts/rdi-login.py` in that workspace refreshes
the token. The live API exposes these operations:

- `POST /api/v1/login`: username/password login, returning `access_token`.
- `GET /api/v2/pipelines/default`: configuration and current status.
- `PUT /api/v2/pipelines/default`: replace configuration using
  `{ "active": true, "config": { ... } }`.
- `POST /api/v2/pipelines/default/secrets?db=sqlserver`: create source secrets
  using `key: "USERNAME"` or `key: "PASSWORD"`, `value`, and `type: "simple"`.
  Use `db=target` for target secrets. Update with
  `PUT /api/v2/pipelines/default/secrets/{key}?db=sqlserver` (or `db=target`).
  The key is the short name, not `SQLSERVER_DB_USERNAME`; the API derives the
  configuration placeholder from the database scope.
- `GET /api/v2/pipelines/default/status`: deployment status.
- `GET /api/v2/pipelines/default/dlqs`: rejected-record queues.

The configuration combines `deployment/rdi/config.yaml` and the named job in
`deployment/rdi/jobs/offers.yaml`. Set source and target credentials as RDI secrets;
never embed them in committed YAML. SQL Server connection settings enable TLS.
The existing collector settings trust the demo server certificate; do not confuse
that with CA validation on the public RDI API connection.

Deploy the checked-in configuration with:

```sh
.venv/bin/python scripts/rdi_deploy.py --connection-env /path/to/private/rdi-connection.env
```

The private connection file must define `RDI_API_URL`, `RDI_USER`, `RDI_PASSWORD`,
and `RDI_CA_CERT_FILE`. CA paths can be absolute or relative to that connection
file; environment variables can override the file settings. The default secrets
file is ignored `.env.rdi-pipeline.json` with this structure:

```json
{
  "sqlserver": {"USERNAME": "value_travel_cdc", "PASSWORD": "<source password>"},
  "target": {"USERNAME": "default", "PASSWORD": "<target password>"}
}
```

The helper upserts those scoped secrets, validates, and deploys only after validation
passes. Immediately after secret updates, the collector may briefly see unresolved
placeholders until its Kubernetes reload completes. The helper retries that condition
and temporary gateway failures for up to 120 seconds (`--secret-wait`), without
printing service response bodies or credentials. Other validation failures stop
immediately. A successful deployment is not replication proof; verify live source
changes and target observations separately.

For a live demo, run from this repository with Kubernetes access to the SQL deployment:

```sh
.venv/bin/python scripts/rdi_offer.py VT-001 --price 5790 --verify
.venv/bin/python scripts/rdi_offer.py VT-001 --price 5890 --verify
```

The first command changes only SQL Server and waits for Redis to match. Show the
Context Retriever `get_offer_by_id` tool or refresh a package quote between
commands. The second command restores the baseline price. Record and restore the actual starting price instead when an offer has already been edited. Do not rerun the
bootstrap Redis seeding script as part of this demonstration: current prices
are maintained by SQL Server and RDI.

## Primary references

- [SQL Server container configuration](https://learn.microsoft.com/en-us/sql/linux/sql-server-linux-docker-container-configure?view=sql-server-ver17)
- [SQL Server memory configuration](https://learn.microsoft.com/en-us/sql/linux/configure/performance-best-practices-sql-server-memory?view=sql-server-ver17)
- [Prepare SQL Server for RDI](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/prepare-dbs/sql-server/)
- [Pipeline configuration](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/pipeline-config/)
- [Job definitions](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/transform-examples/)
- [Deployment and secrets](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/deploy/)

## Validation

On September 28, 2026, all 18 current offers migrated to GKE with every source
field and `updated_at` preserved. Live checks verified inserts, updates, and deletes
through Studio → GKE SQL Server → GKE RDI → the existing Redis database. The
calculated field matched 4321.20 / 4 = 1080.30 and 5678.40 / 4 = 1419.60;
Context Retriever returned the updated offer and calculation. The temporary test
record was deleted, leaving the original 18 offers. The Family escape prompt
returned a complete answer after migration. All 58 automated tests passed.

The dedicated `lg-rdi` VM and its boot disk were deleted after verification, along
with its two dedicated firewall rules. The old SQL Server container was removed
from the shared VM. Its stopped data volume remains as a rollback copy; the active
source is the GKE persistent volume. A private JSON export of the original rows is
stored locally in `.env.sqlserver-gke-migration-backup.json` (excluded from Git).

The optional `--validate-cdc` preflight in the installed RDI 2.0.0 build demands
database-wide UPDATE permission. This demo deliberately keeps the collector
read-only, matching the source preparation guidance; use standard validation
and the live replication checks instead. The CDC account has
`db_datareader`, CDC-schema read access, and state/performance-state permissions;
only the separate Studio editor account can modify offers.


Validate the deployed pipeline with the commands above, then exercise an update,
insert and delete from Studio. Verify both the source and independently read Redis
record, including RDI's calculated price per person, and use Context Retriever to
check the agent-facing value. Restore the starting values after the demonstration.
A successful source write alone is not proof of replication.

The pipeline uses the classic processor and JSON replacement to match Context
Retriever's Offer documents. The job name uses underscores because the RDI schema
forbids spaces. SQL Server Agent and its CDC capture job must remain running for
ongoing changes to reach the collector.
