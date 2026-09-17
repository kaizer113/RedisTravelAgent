# VALUE TRAVEL: MySQL to Redis Data Integration

The fictional offer table is `value_travel.offers`. Its nine business fields match
`valuetravel/context_models.py`'s Offer. RDI is configured to write Redis JSON documents at keys
`value-travel:context:offer:VT-001` through `VT-018`. Context Retriever reads those
documents. The imported JSON documents contain exactly the nine business fields; there are no
internal metadata fields to preserve. RDI replaces each document with the mapped
source fields. MySQL remains authoritative for current prices and room availability.

## Current state

MySQL deployment is isolated on the shared VM in the `value-travel-mysql` container,
with its own Docker network and persistent volume. Port 3307 binds only the VM private address `10.42.0.3`. The GCP firewall is scoped to the `lg-rdi` collector VM.
The generated root/CDC passwords live in ignored `.env.rdi` and in the VM's
`~/value-travel-data/.env.rdi` (mode 600). The container, network and volume have
`owner=lionel_giavelli` and `skip_deletion=yes` labels. Verified 18 source rows, binlog enabled, ROW/FULL format, GTIDs enabled, and a price change from 5890 to 5790 and back in MySQL. The source has row binlogs,
full row images, GTIDs and a CDC account with the documented replication grants.

**RDI 2.0.0 is installed and streaming on `lg-rdi`.** Verified September 17, 2026:
18 initial offers plus two price changes processed, zero pending or rejected records.
VT-001 was changed in MySQL from 5890 to 5790; both Redis JSON and Context
Retriever returned 5790. Restoring MySQL to 5890 propagated to both as well.
The verification script never writes Redis.

| Resource | Configuration |
| --- | --- |
| Project / zone | `central-beach-194106` / `us-east4-c` |
| RDI VM | `lg-rdi`, Ubuntu 24.04, e2-standard-4, 80 GB disk |
| RDI private IP | `10.42.0.4` |
| VPC / subnet | `lg-peering-demo-vpc` / `lg-peering-demo-us-east4` |
| MySQL source | `10.42.0.3:3307`, database `value_travel`, table `offers` |
| State database | `juice-workable-receipt-96400.db.redis.io:11784` |
| State settings verified | noeviction, AOF enabled, cluster disabled |
| Pipeline / processor | `default` / `classic` |
| Job | `value_travel_offers` |
| K3s pod / service CIDRs | `10.244.0.0/16` / `10.245.0.0/16` |
| K3s cluster DNS | `10.245.0.10`, upstream `169.254.169.254` |

The RDI VM and disk have `owner=lionel_giavelli,skip_deletion=yes` labels.
SSH is restricted to the existing administrator IP. RDI's HTTPS API is used
locally over SSH; no public API firewall rule was added. MySQL ingress is limited
to the RDI private IP. Credentials remain in mode-600 files and RDI secrets.

The shared demo VM disk was independently expanded from 30 to 80 GB online.
Its Debian 12 OS is not supported by the RDI installer, so RDI runs separately.
The original port-80 demo and VALUE TRAVEL on port 8080 remain available.

## Files

- `deployment/rdi/mysql/compose.yaml`: isolated source database.
- `deployment/rdi/mysql/init.sql`: 18 fictional offers and CDC grants.
- `scripts/rdi_start_mysql.sh`: equivalent Docker CLI deployment for the VM without Compose.
- `scripts/rdi_generate_mysql_seed.py`: regenerate SQL from `valuetravel/data.py`.
- `deployment/rdi/config.yaml`: deployed collector/target configuration.
- `deployment/rdi/jobs/offers.yaml`: exact JSON Offer mapping for Context Retriever.
- `scripts/rdi_offer.py`: update only MySQL and optionally observe Redis propagation.

The SQL uses INSERT IGNORE so restarting or reusing it does not overwrite later price
changes. Removing the Docker volume would destroy the source data; do not do that.

## Install and operate

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
redis-di deploy --dir ~/value-travel-pipeline --dry-run --validate-cdc
redis-di deploy --dir ~/value-travel-pipeline --validate-cdc
redis-di describe
redis-di list-dlqs
```

For a live demo, run from this repository:

```sh
.venv/bin/python scripts/rdi_offer.py VT-001 --price 5790 --verify
.venv/bin/python scripts/rdi_offer.py VT-001 --price 5890 --verify
```

The first command changes only MySQL and waits for Redis to match. Show the
Context Retriever `get_offer_by_id` tool or refresh a package quote between
commands. The second command restores the original price. Do not rerun the
bootstrap Redis seeding script as part of this demonstration: current prices
are maintained by MySQL and RDI.

## Primary references

- [RDI VM installation and state database requirements](https://redis.io/docs/latest/integrate/redis-data-integration/installation/install-vm/)
- [Prepare MySQL for RDI](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/prepare-dbs/my-sql-mariadb/)
- [Pipeline configuration](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/pipeline-config/)
- [Job definitions](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/transform-examples/)
- [Deployment and secrets](https://redis.io/docs/latest/integrate/redis-data-integration/data-pipelines/deploy/)

## Validation

The pipeline and job pass the JSON schemas bundled in RDI 2.0.0, CLI CDC validation,
and deployed-runtime verification. The job name uses underscores because the
schema forbids spaces. The installed collector is Debezium 3.5.0.Final-rdi.3.
Both classic and Flink processors are bundled; this pipeline uses classic with
JSON replacement to match Context Retriever's existing Offer documents.
