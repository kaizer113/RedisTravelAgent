"""Presenter-only MySQL CRUD. Redis and Context Retriever are strictly read-only here."""

from __future__ import annotations

import asyncio
import hmac
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

import pymysql
from fastapi import APIRouter, Depends, Header, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .data import PACKAGES

log = logging.getLogger(__name__)
FIELDS = (
    "package_id",
    "name",
    "destination",
    "total_price",
    "available_rooms",
    "eligible_reward_base",
    "cancellation",
    "departure_date",
    "data_label",
)
COLUMNS = ", ".join(FIELDS)
OfferID = Annotated[str, Path(pattern=r"^VT-[A-Z0-9-]{1,13}$", max_length=16)]


class Offer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package_id: str = Field(pattern=r"^VT-[A-Z0-9-]{1,13}$", max_length=16)
    name: str = Field(min_length=1, max_length=160)
    destination: str = Field(min_length=1, max_length=80)
    total_price: Decimal = Field(ge=0, le=99999999, max_digits=10, decimal_places=2)
    available_rooms: int = Field(ge=0, le=1000000, strict=True)
    eligible_reward_base: Decimal = Field(
        ge=0, le=99999999, max_digits=10, decimal_places=2
    )
    cancellation: str = Field(min_length=1, max_length=512)
    departure_date: date
    data_label: str = Field(min_length=1, max_length=80)

    @field_validator("name", "destination", "cancellation", "data_label")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()

    def values(self):
        d = self.model_dump()
        d["departure_date"] = self.departure_date.isoformat()
        return tuple(d[k] for k in FIELDS)


class Update(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offer: Offer
    expected_updated_at: str = Field(min_length=1, max_length=32)


class Delete(BaseModel):
    expected_updated_at: str = Field(min_length=1, max_length=32)


class Restore(BaseModel):
    confirm: str


def serialize(row):
    return {
        k: float(v)
        if isinstance(v, Decimal)
        else v.isoformat(sep=" ", timespec="microseconds")
        if isinstance(v, datetime)
        else v.isoformat()
        if isinstance(v, date)
        else v
        for k, v in row.items()
    }


class OfferStore:
    def __init__(self, settings):
        self.settings = settings

    def connect(self):
        s = self.settings
        return pymysql.connect(
            host=s.studio_mysql_host,
            port=s.studio_mysql_port,
            user=s.studio_mysql_user,
            password=s.studio_mysql_password,
            database="value_travel",
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
            autocommit=False,
        )

    def list(self):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {COLUMNS}, updated_at FROM offers ORDER BY package_id LIMIT 501"
            )
            rows = cur.fetchall()
            if len(rows) > 500:
                raise HTTPException(409, "Demo table exceeds the 500-row display limit")
            return [serialize(r) for r in rows]

    def mutate(self, operation, offer=None, package_id=None, expected=None):
        with self.connect() as conn, conn.cursor() as cur:
            if operation in ("update", "delete"):
                cur.execute(
                    "SELECT updated_at FROM offers WHERE package_id=%s FOR UPDATE",
                    (package_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(
                        404, "Offer no longer exists; refresh the table"
                    )
                if serialize(row)["updated_at"] != expected:
                    raise HTTPException(
                        409,
                        "This row changed since you loaded it. Refresh before saving.",
                    )
            if operation == "insert":
                cur.execute(
                    f"INSERT INTO offers ({COLUMNS}) VALUES ({', '.join(['%s'] * 9)})",
                    offer.values(),
                )
            elif operation == "update":
                cur.execute(
                    f"UPDATE offers SET {', '.join(k + '=%s' for k in FIELDS[1:])}, updated_at=CURRENT_TIMESTAMP(6) WHERE package_id=%s",
                    (*offer.values()[1:], package_id),
                )
            elif operation == "delete":
                cur.execute("DELETE FROM offers WHERE package_id=%s", (package_id,))
            elif operation == "restore":
                # Only the dedicated synthetic offers table; no Redis or other demo writes.
                ids = [p["package_id"] for p in PACKAGES]
                cur.execute(
                    f"DELETE FROM offers WHERE package_id NOT IN ({', '.join(['%s'] * len(ids))})",
                    ids,
                )
                for p in PACKAGES:
                    fixture = Offer(**{k: p[k] for k in FIELDS})
                    cur.execute(
                        f"INSERT INTO offers ({COLUMNS}) VALUES ({', '.join(['%s'] * 9)}) ON DUPLICATE KEY UPDATE {', '.join(k + '=VALUES(' + k + ')' for k in FIELDS[1:])}",
                        fixture.values(),
                    )
            else:
                raise ValueError("Unsupported operation")
            conn.commit()


def create_router(settings, redis_client, context):
    store = OfferStore(settings)

    async def authorize(x_studio_key: Annotated[str | None, Header()] = None):
        if not settings.studio_key or not settings.studio_mysql_password:
            raise HTTPException(503, "Data Studio is not configured")
        if not x_studio_key or not hmac.compare_digest(
            x_studio_key, settings.studio_key
        ):
            raise HTTPException(401, "Enter the presenter key to unlock Data Studio")

    router = APIRouter(prefix="/api/studio", dependencies=[Depends(authorize)])

    async def database_call(fn, *args, **kwargs):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except pymysql.IntegrityError as exc:
            raise HTTPException(409, "An offer with this ID already exists") from exc
        except pymysql.MySQLError as exc:
            log.warning("Data Studio MySQL failure: %s", type(exc).__name__)
            raise HTTPException(
                503, "MySQL is unavailable; no successful change was confirmed"
            ) from exc

    def target_rows():
        keys = []
        for key in redis_client.scan_iter(
            match="value-travel:context:offer:*", count=100
        ):
            keys.append(key)
            if len(keys) > 500:
                raise HTTPException(
                    409, "Redis offers exceed the 500-row display limit"
                )
        rows = []
        for key in keys:
            value = redis_client.json().get(key)
            if value is not None:
                rows.append({k: value.get(k) for k in FIELDS})
        return sorted(rows, key=lambda r: r["package_id"] or "")

    @router.get("/offers")
    async def offers():
        source = await database_call(store.list)
        try:
            target = await asyncio.to_thread(target_rows)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                503, "Redis verification unavailable; replication status is unknown"
            ) from exc
        return {
            "mysql": source,
            "redis": target,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @router.post("/offers", status_code=201)
    async def insert(offer: Offer):
        await database_call(store.mutate, "insert", offer=offer)
        return {"ok": True, "operation": "insert", "id": offer.package_id}

    @router.put("/offers/{package_id}")
    async def update(package_id: OfferID, body: Update):
        if body.offer.package_id != package_id:
            raise HTTPException(
                422, "Package ID cannot be changed; insert a new row instead"
            )
        await database_call(
            store.mutate,
            "update",
            offer=body.offer,
            package_id=package_id,
            expected=body.expected_updated_at,
        )
        return {"ok": True, "operation": "update", "id": package_id}

    @router.delete("/offers/{package_id}")
    async def delete(package_id: OfferID, body: Delete):
        await database_call(
            store.mutate,
            "delete",
            package_id=package_id,
            expected=body.expected_updated_at,
        )
        return {"ok": True, "operation": "delete", "id": package_id}

    @router.post("/restore")
    async def restore(body: Restore):
        if body.confirm != "RESTORE":
            raise HTTPException(422, "Restore confirmation is required")
        await database_call(store.mutate, "restore")
        return {"ok": True, "operation": "restore"}

    @router.get("/context/{package_id}")
    async def context_offer(package_id: OfferID):
        # Service errors and unknown response shapes are never deletion evidence.
        try:
            result = await context.call("get_offer_by_id", {"id": package_id})
        except Exception as exc:
            raise HTTPException(
                502, "Context Retriever verification unavailable"
            ) from exc
        if result.get("package_id") == package_id:
            return {"found": True, "offer": {k: result.get(k) for k in FIELDS}}
        raise HTTPException(
            502,
            "Context Retriever did not return an offer; inspect Redis separately for deletion evidence",
        )

    return router
