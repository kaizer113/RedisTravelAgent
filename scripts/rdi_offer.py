#!/usr/bin/env python3
"""Inspect/change a MySQL offer and optionally verify genuine CDC in Redis.

This tool never writes Redis. A changed source value requires working CDC to match.
Run from the repository: .venv/bin/python scripts/rdi_offer.py VT-001 --price 5790 --verify
"""

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("package_id")
parser.add_argument("--price", type=Decimal)
parser.add_argument("--verify", action="store_true")
parser.add_argument("--timeout", type=float, default=45)
args = parser.parse_args()
if not re.fullmatch(r"VT-\d{3}", args.package_id):
    parser.error("package_id must look like VT-001")
if args.price is not None and (
    not args.price.is_finite() or args.price < 0 or args.price > 99999999
):
    parser.error("price must be a finite amount between 0 and 99999999")
if args.price is not None and args.price != args.price.quantize(Decimal(".01")):
    parser.error("price must have at most two decimal places")

sql = ""
if args.price is not None:
    sql += f"UPDATE offers SET total_price={args.price}, eligible_reward_base=ROUND({args.price}*0.8,2) WHERE package_id='{args.package_id}'; "
sql += f"SELECT JSON_OBJECT('package_id', package_id, 'total_price', total_price, 'available_rooms', available_rooms, 'updated_at', updated_at) FROM offers WHERE package_id='{args.package_id}';"
remote = (
    "sudo docker exec -i value-travel-mysql sh -c "
    + "'MYSQL_PWD=\"$MYSQL_ROOT_PASSWORD\" mysql -uroot --batch --skip-column-names value_travel'"
)
started = time.monotonic()
result = subprocess.run(
    [
        "gcloud",
        "compute",
        "ssh",
        "valuewholesale-demo",
        "--project",
        "central-beach-194106",
        "--zone",
        "us-east4-c",
        "--command",
        remote,
    ],
    input=sql,
    text=True,
    capture_output=True,
    check=True,
)
if not result.stdout.strip():
    raise SystemExit("Offer not found in MySQL")
source = json.loads(result.stdout.strip())
print(json.dumps({"source": "MySQL", "offer": source}))
if args.verify:
    from dotenv import load_dotenv
    import redis

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    r = redis.Redis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
    )
    key = "value-travel:context:offer:" + args.package_id
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        document = r.json().get(key)
        actual = document.get("total_price") if isinstance(document, dict) else None
        if actual is not None and Decimal(str(actual)) == Decimal(
            str(source["total_price"])
        ):
            print(
                json.dumps(
                    {
                        "redis_key": key,
                        "price": actual,
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "note": "Redis matches MySQL. For CDC proof, change to a price different from the prior Redis value.",
                    }
                )
            )
            break
        time.sleep(0.25)
    else:
        raise SystemExit(
            "CDC NOT VERIFIED: Redis did not match MySQL before timeout. No Redis writes were performed."
        )
