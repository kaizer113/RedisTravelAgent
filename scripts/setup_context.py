"""Provision VALUE TRAVEL with ctxctl and bootstrap synthetic context records.

Offer bootstrap is optional: once RDI owns offers, use --skip-offers.
Credentials are written separately to .env.context, never printed.
"""

from __future__ import annotations
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlparse
from dotenv import dotenv_values
from context_surfaces import UnifiedClient
from valuetravel.context_models import Offer, Reservation, Traveler
from valuetravel.data import MEMBERS, PACKAGES, RESERVATIONS

ROOT = Path(__file__).resolve().parents[1]


def cli(*args: str, admin_key: str):
    result = subprocess.run(
        [
            "uv",
            "run",
            "ctxctl",
            "--no-color",
            "-o",
            "json",
            *args,
            "--admin-key",
            admin_key,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        # Avoid returning command strings containing admin or database credentials.
        raise RuntimeError(
            result.stderr.replace(admin_key, "[REDACTED]").strip() or "ctxctl failed"
        )
    return json.loads(result.stdout) if result.stdout.strip() else None


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-offers", action="store_true")
    args = parser.parse_args()
    env = {k: str(v or "") for k, v in dotenv_values(ROOT / ".env").items()}
    key = env["CTX_ADMIN_KEY"]
    previous = dotenv_values(ROOT / ".env.context")
    surfaces = cli("surface", "list", admin_key=key) or []
    surface = next((s for s in surfaces if s["name"] == "ValueTravelLio"), None)
    description = (
        "VALUE TRAVEL synthetic travel context. owner=lionel_giavelli,skip_deletion=yes"
    )
    if surface:
        sid = str(surface["id"])
        cli(
            "surface",
            "update",
            sid,
            "--name",
            "ValueTravelLio",
            "--description",
            description,
            "--models",
            str(ROOT / "valuetravel/context_models.py"),
            admin_key=key,
        )
    else:
        parsed = urlparse(env["REDIS_URL"])
        cmd = [
            "surface",
            "create",
            "--name",
            "ValueTravelLio",
            "--description",
            description,
            "--models",
            str(ROOT / "valuetravel/context_models.py"),
            "--redis-addr",
            f"{parsed.hostname}:{parsed.port}",
            "--redis-username",
            unquote(parsed.username or "default"),
            "--redis-password",
            unquote(parsed.password or ""),
        ]
        if parsed.scheme == "rediss":
            cmd.append("--redis-tls")
        surface = cli(*cmd, admin_key=key)
        sid = str(surface["id"])
    agent_key = (
        previous.get("MCP_AGENT_KEY") if previous.get("CTX_SURFACE_ID") == sid else None
    )
    if not agent_key:
        agent = cli(
            "agent",
            "create",
            "--surface-id",
            sid,
            "--name",
            "ValueTravelLio-readonly",
            "--description",
            "Read-only synthetic travel context; owner=lionel_giavelli,skip_deletion=yes",
            admin_key=key,
        )
        agent_key = agent["key"]
    secret_path = ROOT / ".env.context"
    secret_path.touch(mode=0o600, exist_ok=True)
    secret_path.chmod(0o600)
    secret_path.write_text(f"CTX_SURFACE_ID={sid}\nMCP_AGENT_KEY={agent_key}\n")
    print(f"Context Retriever surface: {sid}; credentials saved to .env.context")
    groups = [(Traveler, MEMBERS), (Reservation, RESERVATIONS)]
    if not args.skip_offers:
        groups.append((Offer, PACKAGES))
    async with UnifiedClient(timeout=60) as client:
        for model, rows in groups:
            fields = model.model_fields
            records = [
                model(**{k: v for k, v in row.items() if k in fields}) for row in rows
            ]
            result = await client.import_data(
                admin_key=key,
                context_surface_id=sid,
                records=records,
                on_conflict="overwrite",
                on_error="fail_fast",
            )
            print(
                f"{model.__name__}: imported={result.imported}, failed={result.failed}"
            )
        discovered = await client.list_tools(agent_key)
        (ROOT / "scripts/context_tools.json").write_text(
            json.dumps(discovered, indent=2)
        )
        print("Generated tools: " + ", ".join(t["name"] for t in discovered))


if __name__ == "__main__":
    asyncio.run(main())
