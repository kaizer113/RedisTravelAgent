#!/usr/bin/env python3
"""Configure secrets, validate and deploy VALUE TRAVEL to an existing RDI API."""

import argparse
import json
import os
from pathlib import Path
import sys
import time

from dotenv import dotenv_values
import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]


def require_success(response, operation):
    if not response.is_success:
        # RDI errors may echo database credentials: never print response bodies.
        raise RuntimeError(f"{operation} failed (HTTP {response.status_code}); inspect private RDI logs.")


def deploy(client, config, secrets, wait_seconds=120, sleep=time.sleep, now=time.monotonic):
    if set(secrets) != {"sqlserver", "target"} or any(
        not isinstance(values, dict)
        or set(values) != {"USERNAME", "PASSWORD"}
        or not all(isinstance(value, str) and value for value in values.values())
        for values in secrets.values()
    ):
        raise ValueError("Secrets must contain sqlserver and target, each with nonempty USERNAME and PASSWORD.")
    base = "/api/v2/pipelines/default"
    for db, values in secrets.items():
        for key, value in values.items():
            response = client.post(
                base + "/secrets", params={"db": db},
                json={"key": key, "value": value, "type": "simple"},
            )
            if response.status_code == 409:
                response = client.put(
                    base + "/secrets/" + key, params={"db": db},
                    json={"value": value, "type": "simple"},
                )
            require_success(response, "Configure pipeline secret")
    print("Pipeline secrets configured; validating after collector reload.", flush=True)
    deadline = now() + wait_seconds
    body = {"active": True, "config": config}
    while True:
        response = client.put(base, params={"dry_run": "true"}, json=body)
        if response.is_success:
            break
        # Immediately after updating secrets, the collector can still see literal
        # placeholders until Kubernetes reloads its secret-backed configuration.
        unresolved = any(marker in response.text for marker in (
            "${SQLSERVER_DB_", "${TARGET_DB_", "${SOURCE_DB_",
        ))
        transient = response.status_code in (502, 503, 504) or unresolved
        remaining = deadline - now()
        if not transient or remaining <= 0:
            require_success(response, "Pipeline validation")
        sleep(min(5, remaining))
    print("Pipeline validation passed.", flush=True)
    response = client.put(base, params={"dry_run": "false"}, json=body)
    require_success(response, "Pipeline deployment")
    print("Pipeline configuration deployed. Verify streaming and source-to-Redis replication separately.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-env", required=True, type=Path,
                        help="Private env file with RDI_API_URL, RDI_USER, RDI_PASSWORD and RDI_CA_CERT_FILE")
    parser.add_argument("--secrets-file", type=Path, default=ROOT / ".env.rdi-pipeline.json")
    parser.add_argument("--secret-wait", type=float, default=120,
                        help="Maximum retry window for collector secret propagation, seconds")
    args = parser.parse_args()
    if not 0 <= args.secret_wait <= 600:
        parser.error("--secret-wait must be between 0 and 600")
    connection_file = args.connection_env.expanduser().resolve()
    values = {**dotenv_values(connection_file), **os.environ}
    required = ("RDI_API_URL", "RDI_USER", "RDI_PASSWORD", "RDI_CA_CERT_FILE")
    if any(not values.get(key) for key in required):
        parser.error("Connection settings require " + ", ".join(required))
    url = httpx.URL(values["RDI_API_URL"])
    if url.scheme != "https" or url.userinfo:
        parser.error("RDI_API_URL must use HTTPS without embedded credentials")
    ca = Path(values["RDI_CA_CERT_FILE"]).expanduser()
    if not ca.is_absolute():
        ca = connection_file.parent / ca
    if not ca.is_file():
        parser.error("RDI_CA_CERT_FILE must reference an existing CA certificate")
    config = yaml.safe_load((ROOT / "deployment/rdi/config.yaml").read_text())
    config["jobs"] = [yaml.safe_load((ROOT / "deployment/rdi/jobs/offers.yaml").read_text())]
    secrets = json.loads(args.secrets_file.read_text())
    with httpx.Client(base_url=url, verify=str(ca), timeout=120) as client:
        response = client.post("/api/v1/login", json={
            "username": values["RDI_USER"], "password": values["RDI_PASSWORD"],
        })
        require_success(response, "RDI login")
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        deploy(client, config, secrets, args.secret_wait)


if __name__ == "__main__":
    try:
        main()
    except (httpx.HTTPError, OSError, ValueError, KeyError, RuntimeError) as error:
        # Only our fixed messages are safe; network and parsing errors can include
        # URLs or response payloads. Keep credentials out of console diagnostics.
        message = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        print("RDI deployment failed: " + message, file=sys.stderr)
        sys.exit(1)
