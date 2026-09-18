# VALUE TRAVEL: SQL Server to Redis Data Integration

The fictional offer table is `value_travel.dbo.offers`. Its ten source fields feed
`valuetravel/context_models.py`'s Offer. RDI is configured to write Redis JSON documents at keys
`value-travel:context:offer:VT-001` through `VT-018`. Context Retriever reads those
documents. The Redis JSON documents contain the ten source fields plus the RDI-calculated
`average_price_per_person`; there are no internal metadata fields to preserve. RDI adds `ROUND(total_price / room_capacity, 2)` with a SQL `add_field` transform
and replaces each document with the mapped source and calculated fields. Capacity
means people accommodated by the offer; it is independent of available room count. SQL Server remains authoritative for current prices and room availability.

## Current state

SQL Server Developer runs on the shared VM in the `value-travel-sqlserver`
container, with its own persistent volume on the `value-travel-data` Docker network.
Port 1433 binds only the private address `10.42.0.3`; the GCP firewall allows
connections from the `lg-rdi` collector VM. The application connects over Docker's
private network.

Docker enforces a 3 GiB memory ceiling with `--memory=3g --memory-swap=3g` (no
additional swap allowance). `MSSQL_MEMORY_LIMIT_MB=2048` leaves headroom within that
ceiling. SQL Server Agent is enabled, and native Change Data Capture is enabled on
both database `value_travel` and table `dbo.offers`. The collector reads SQL Server
CDC changes using a dedicated account. Developer edition is used for this demo.

Generated source credentials remain in ignored `.env.sqlserver` and private VM files
(mode 600). The container, network and volume carry `owner=lionel_giavelli` and
`skip_deletion=yes` labels. The separate RDI 2.0.0 installation on `lg-rdi` remains
in place; its collector configuration now selects the SQL Server source.

| Resource | Configuration |
| --- | --- |
| Project / zone | `central-beach-194106` / `us-east4-c` |
| RDI VM | `lg-rdi`, Ubuntu 24.04, e2-standard-4, 80 GB disk |
| RDI private IP | `10.42.0.4` |
| VPC / subnet | `lg-peering-demo-vpc` / `lg-peering-demo-us-east4` |
| SQL Server source | `10.42.0.3:1433`, database `value_travel`, schema `dbo`, table `offers` |
| State database | `juice-workable-receipt-96400.db.redis.io:11784` |
| State settings verified | noeviction, AOF enabled, cluster disabled |
| Pipeline / processor | `default` / `classic` |
| Job | `value_travel_offers` |
| K3s pod / service CIDRs | `10.244.0.0/16` / `10.245.0.0/16` |
| K3s cluster DNS | `10.245.0.10`, upstream `169.254.169.254` |

The RDI VM and disk have `owner=lionel_giavelli,skip_deletion=yes` labels.
SSH is restricted to the existing administrator IP. RDI's HTTPS API is used
locally over SSH; no public API firewall rule was added. SQL Server ingress is limited
to the RDI private IP. Credentials remain in mode-600 files and RDI secrets.

The shared demo VM disk was independently expanded from 30 to 80 GB online.
Its Debian 12 OS is not supported by the RDI installer, so RDI runs separately.
The original port-80 demo and VALUE TRAVEL on port 8080 remain available.

## Files

- `deployment/rdi/sqlserver/init.sql`: database, offer schema and native CDC setup.
- `deployment/rdi/sqlserver/seed.sql`: 18 fictional baseline offers.
- `scripts/rdi_start_sqlserver.sh`: Docker deployment, schema setup and separate CDC/editor accounts.
- `scripts/rdi_generate_sqlserver_seed.py`: regenerate `seed.sql` from `valuetravel/data.py`.
- `deployment/rdi/config.yaml`: deployed collector/target configuration.
- `deployment/rdi/jobs/offers.yaml`: exact JSON Offer mapping for Context Retriever.
- `scripts/rdi_offer.py`: update only SQL Server and optionally observe Redis propagation.

The seed inserts missing baseline offers without overwriting existing source edits.
Removing the Docker volume destroys the source data.

## Install and operate

Create a private `.env.sqlserver` at the repository root with `MSSQL_SA_PASSWORD`,
`SQLSERVER_CDC_PASSWORD` and `SQLSERVER_EDITOR_PASSWORD`. The startup script accepts
16–128 characters using letters, digits, underscores and hyphens. It provisions
`value_travel_cdc` and the table-scoped `value_travel_editor` separately.

```sh
bash scripts/rdi_start_sqlserver.sh
```

The script reads `.env.sqlserver` (override with `SQLSERVER_ENV_FILE`), starts the
limited-memory container, enables CDC, then inserts any missing baseline rows.
Use `--no-seed` when loading an existing source dataset during migration. The Studio
uses its separate `STUDIO_SQLSERVER_*` configuration and never uses `sa`.


The installer is extracted at `~/rdi-installer/rdi_install/2.0.0` on `lg-rdi`.
The active pipeline files are at `~/value-travel-pipeline`.
`deployment/rdi/install/installer.example.toml` documents the installation input.
RDI 2.0.0 actually reads TOML for silent installation, although its help says YAML.
Keep the completed installer file private and run from the extracted directory:

```sh
sudo INSTALL_K3S_EXEC='--cluster-cidr=10.244.0.0/16 --service-cidr=10.245.0.0/16 --cluster-dns=10.245.0.10' ./install.sh -f ~/.rdi-install.toml
```

The CLI context is `default`, API URL `https://localhost`, user `default`.
Supply the state database password through `RDI_PASSWORD` when using the CLI;
never commit it. The self-signed local API uses the installer's insecure context.
Source and target credentials are already configured with `redis-di set-secret`.
When changing several secrets, use `--wait=false` for intermediate changes,
then wait for the final change and collector API rollout before validation.

```sh
redis-di deploy --dir ~/value-travel-pipeline --dry-run
redis-di deploy --dir ~/value-travel-pipeline
redis-di describe
redis-di list-dlqs
```

For a live demo, run from this repository:

```sh
.venv/bin/python scripts/rdi_offer.py VT-001 --price 5790 --verify
.venv/bin/python scripts/rdi_offer.py VT-001 --price 5890 --verify
```

The first command changes only SQL Server and waits for Redis to match. Show the
Context Retriever `get_offer_by_id` tool or refresh a package quote between
commands. The second command restores the original price. Do not rerun the
bootstrap Redis seeding script as part of this demonstration: current prices
are maintained by SQL Server and RDI.

## Primary references

- [RDI VM installation and state database requirements](https://redis.io/docs/latest/integrate/redis-data-integration/installation/install-vm/)
- [SQL Server container configuration](https://learn.microsoft.com/en-us/sql/linux/sql-server-linux-docker-container-configure?view=sql-server-ver17)
- [SQL Server memory configuration](https://learn.microsoft.com/en-us/sql/linux/configure/performance-best-practices-sql-server-memory?view=sql-server-ver17)
- [Prepare SQL Server for RDI](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/prepare-dbs/sql-server/)
- [Pipeline configuration](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/pipeline-config/)
- [Job definitions](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/transform-examples/)
- [Deployment and secrets](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/deploy/)

## Validation

The SQL Server migration preserved all 18 current offers. Live validation verified
insert → Redis, update → Redis, deletion from both stores, stale-update rejection,
and Context Retriever retrieval. The calculated field changed from 33.33 for
100 / 3 to 60 for 240 / 4. The temporary verification offer was deleted. RDI
reported SQL Server streaming with no pending or rejected records.

The optional `--validate-cdc` preflight in the installed RDI 2.0.0 build demands
database-wide UPDATE permission. This demo deliberately keeps the collector
read-only, matching the source preparation guidance; use standard validation
above and the live replication checks instead. The CDC account has
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
