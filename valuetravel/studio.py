"""Presenter-only SQL Server CRUD. Redis and Context Retriever are strictly read-only here."""

from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

import pymssql
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .data import PACKAGES

log = logging.getLogger(__name__)
FIELDS = (
    "package_id",
    "name",
    "destination",
    "total_price",
    "available_rooms",
    "room_capacity",
    "eligible_reward_base",
    "cancellation",
    "departure_date",
    "data_label",
)
REDIS_FIELDS = (*FIELDS, "average_price_per_person")
COLUMNS = ", ".join(FIELDS)
OfferID = Annotated[str, Path(pattern=r"^VT-[A-Z0-9-]{1,13}$", max_length=16)]


class Offer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package_id: str = Field(pattern=r"^VT-[A-Z0-9-]{1,13}$", max_length=16)
    name: str = Field(min_length=1, max_length=160)
    destination: str = Field(min_length=1, max_length=80)
    total_price: Decimal = Field(ge=0, le=99999999, max_digits=10, decimal_places=2)
    available_rooms: int = Field(ge=0, le=1000000, strict=True)
    room_capacity: int = Field(ge=1, le=20, strict=True)
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
        return pymssql.connect(
            server=s.studio_sqlserver_host,
            port=str(s.studio_sqlserver_port),
            user=s.studio_sqlserver_user,
            password=s.studio_sqlserver_password,
            database="value_travel",
            charset="UTF-8",
            as_dict=True,
            login_timeout=5,
            timeout=10,
            tds_version="7.4",
            autocommit=False,
        )

    @contextmanager
    def transaction(self):
        with self.connect() as conn:
            try:
                with conn.cursor() as cur:
                    yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def list(self):
        with self.transaction() as cur:
            cur.execute(
                f"SELECT TOP (501) {COLUMNS}, updated_at FROM dbo.offers ORDER BY package_id"
            )
            rows = cur.fetchall()
            if len(rows) > 500:
                raise HTTPException(409, "Demo table exceeds the 500-row display limit")
            return [serialize(r) for r in rows]

    def mutate(self, operation, offer=None, package_id=None, expected=None):
        with self.transaction() as cur:
            if operation in ("update", "delete"):
                cur.execute(
                    "SELECT updated_at FROM dbo.offers WITH (UPDLOCK, HOLDLOCK) WHERE package_id=%s",
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
                    f"INSERT INTO dbo.offers ({COLUMNS}) VALUES ({', '.join(['%s'] * len(FIELDS))})",
                    offer.values(),
                )
            elif operation == "update":
                cur.execute(
                    f"UPDATE dbo.offers SET {', '.join(k + '=%s' for k in FIELDS[1:])}, updated_at=SYSUTCDATETIME() WHERE package_id=%s",
                    (*offer.values()[1:], package_id),
                )
            elif operation == "delete":
                cur.execute("DELETE FROM dbo.offers WHERE package_id=%s", (package_id,))
            elif operation == "restore":
                # Only the dedicated synthetic offers table; no Redis or other demo writes.
                ids = [p["package_id"] for p in PACKAGES]
                cur.execute(
                    f"DELETE FROM dbo.offers WHERE package_id NOT IN ({', '.join(['%s'] * len(ids))})",
                    tuple(ids),
                )
                for p in PACKAGES:
                    fixture = Offer(**{k: p[k] for k in FIELDS})
                    cur.execute(
                        f"UPDATE dbo.offers WITH (UPDLOCK, HOLDLOCK) SET {', '.join(k + '=%s' for k in FIELDS[1:])}, updated_at=SYSUTCDATETIME() WHERE package_id=%s; "
                        f"IF @@ROWCOUNT = 0 INSERT INTO dbo.offers ({COLUMNS}) VALUES ({', '.join(['%s'] * len(FIELDS))})",
                        (*fixture.values()[1:], fixture.package_id, *fixture.values()),
                    )
            else:
                raise ValueError("Unsupported operation")


def create_router(settings, redis_client, context):
    store = OfferStore(settings)

    async def configured():
        if not settings.studio_sqlserver_password:
            raise HTTPException(503, "Data Studio is not configured")

    router = APIRouter(prefix="/api/studio", dependencies=[Depends(configured)])

    async def database_call(fn, *args, **kwargs):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except pymssql.IntegrityError as exc:
            if exc.args and exc.args[0] in (2601, 2627):
                detail = "An offer with this ID already exists"
            else:
                detail = "The offer violates a database constraint"
            raise HTTPException(409, detail) from exc
        except pymssql.Error as exc:
            log.warning("Data Studio SQL Server failure: %s", type(exc).__name__)
            raise HTTPException(
                503, "SQL Server is unavailable; no successful change was confirmed"
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
                rows.append({k: value.get(k) for k in REDIS_FIELDS})
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
            "sqlserver": source,
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
            return {"found": True, "offer": {k: result.get(k) for k in REDIS_FIELDS}}
        raise HTTPException(
            502,
            "Context Retriever did not return an offer; inspect Redis separately for deletion evidence",
        )

    return router
