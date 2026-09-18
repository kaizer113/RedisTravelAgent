"""Presenter CRUD trust boundaries, with no production app or external services."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pymssql
import pytest

from valuetravel import studio


@pytest.fixture
def harness(monkeypatch):
    settings = SimpleNamespace(
        studio_sqlserver_password="local-test-password"
    )
    store = MagicMock(spec=studio.OfferStore)
    store.list.return_value = []
    monkeypatch.setattr(studio, "OfferStore", lambda settings: store)
    redis = MagicMock()
    redis.scan_iter.return_value = iter([])
    context = SimpleNamespace(call=AsyncMock(return_value={}))
    app = FastAPI()
    app.include_router(studio.create_router(settings, redis, context))
    return SimpleNamespace(
        client=TestClient(app, raise_server_exceptions=False),
        settings=settings,
        store=store,
        redis=redis,
        context=context,
        headers={},
    )


@pytest.fixture
def offer():
    return {
        "package_id": "VT-001",
        "name": "Synthetic Maui Escape",
        "destination": "Maui",
        "total_price": "5890.00",
        "available_rooms": 4,
        "room_capacity": 4,
        "eligible_reward_base": "4712.00",
        "cancellation": "Fictional refundable hotel",
        "departure_date": "2027-04-10",
        "data_label": "Synthetic demo offer",
    }


def test_studio_can_be_read_without_authentication(harness):
    response = harness.client.get("/api/studio/offers")
    assert response.status_code == 200
    harness.store.list.assert_called_once()


def test_studio_disabled_without_database_configuration(harness):
    harness.settings.studio_sqlserver_password = ""
    response = harness.client.get("/api/studio/offers")
    assert response.status_code == 503
    harness.store.list.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("package_id", "VT-001'; DROP TABLE offers;--"),
        ("package_id", "VT-" + "A" * 14),
        ("total_price", "-0.01"),
        ("total_price", "1.001"),
        ("eligible_reward_base", "-1"),
        ("eligible_reward_base", "0.001"),
        ("room_capacity", 0),
        ("room_capacity", -1),
        ("room_capacity", 1.5),
        ("room_capacity", 21),
        ("available_rooms", -1),
        ("available_rooms", 1.5),
        ("name", "  "),
        ("departure_date", "not-a-date"),
    ],
)
def test_invalid_offer_never_reaches_sqlserver(harness, offer, field, value):
    offer[field] = value
    response = harness.client.post(
        "/api/studio/offers", headers=harness.headers, json=offer
    )
    assert response.status_code == 422
    harness.store.mutate.assert_not_called()
    assert not harness.redis.mock_calls


@pytest.mark.parametrize("package_id", ["VT-" + "A" * 14, "VT-001';DROP-TABLE"])
def test_path_ids_rejected_before_delete_or_context_access(harness, package_id):
    deleted = harness.client.request(
        "DELETE",
        "/api/studio/offers/" + package_id,
        headers=harness.headers,
        json={"expected_updated_at": "2026-09-17 12:00:00.000000"},
    )
    fetched = harness.client.get(
        "/api/studio/context/" + package_id, headers=harness.headers
    )
    assert deleted.status_code == 422
    assert fetched.status_code == 422
    harness.store.mutate.assert_not_called()
    harness.context.call.assert_not_awaited()


def test_optimistic_conflict_is_not_reported_as_success(harness, offer):
    harness.store.mutate.side_effect = HTTPException(
        409, "This row changed since you loaded it"
    )
    response = harness.client.put(
        "/api/studio/offers/VT-001",
        headers=harness.headers,
        json={"offer": offer, "expected_updated_at": "2026-09-17 12:00:00.000000"},
    )
    assert response.status_code == 409
    assert "changed" in response.json()["detail"]
    assert not harness.redis.mock_calls
    harness.context.call.assert_not_awaited()


def test_successful_insert_only_mutates_sqlserver(harness, offer):
    response = harness.client.post(
        "/api/studio/offers", headers=harness.headers, json=offer
    )
    assert response.status_code == 201
    assert harness.store.mutate.call_args.args == ("insert",)
    assert harness.store.mutate.call_args.kwargs["offer"].total_price == Decimal(
        "5890.00"
    )
    assert not harness.redis.mock_calls
    harness.context.call.assert_not_awaited()


def test_restore_requires_exact_confirmation(harness):
    for confirmation in ["", "restore", "RESTORE ALL"]:
        response = harness.client.post(
            "/api/studio/restore",
            headers=harness.headers,
            json={"confirm": confirmation},
        )
        assert response.status_code == 422
    harness.store.mutate.assert_not_called()
    response = harness.client.post(
        "/api/studio/restore", headers=harness.headers, json={"confirm": "RESTORE"}
    )
    assert response.status_code == 200
    harness.store.mutate.assert_called_once_with("restore")
    assert not harness.redis.mock_calls


def test_sqlserver_connection_error_does_not_confirm_a_change(harness, offer):
    harness.store.mutate.side_effect = pymssql.OperationalError(20002, "connection lost")
    response = harness.client.post(
        "/api/studio/offers", headers=harness.headers, json=offer
    )
    assert response.status_code == 503
    assert not response.json().get("ok")
    assert not harness.redis.mock_calls


def test_redis_read_failure_is_unknown_replication_not_empty_success(harness):
    harness.redis.scan_iter.side_effect = ConnectionError("Redis unavailable")
    response = harness.client.get("/api/studio/offers", headers=harness.headers)
    assert response.status_code == 503
    assert "unknown" in response.json()["detail"]
    assert "redis" not in response.json()


@pytest.mark.parametrize(
    "result",
    [
        {"error": "service unavailable"},
        {"ok": False},
        {},
        {"package_id": "VT-999"},
        {"found": False},
    ],
)
def test_context_error_cannot_be_called_missing(harness, result):
    harness.context.call.return_value = result
    response = harness.client.get("/api/studio/context/VT-001", headers=harness.headers)
    assert response.status_code == 502
    assert "found" not in response.json()


def test_context_transport_error_cannot_be_called_missing(harness):
    harness.context.call.side_effect = ConnectionError("service unavailable")
    response = harness.client.get("/api/studio/context/VT-001", headers=harness.headers)
    assert response.status_code == 502
    assert "found" not in response.json()


def test_context_existing_offer_is_distinct_from_missing(harness, offer):
    harness.context.call.return_value = offer
    response = harness.client.get("/api/studio/context/VT-001", headers=harness.headers)
    assert response.status_code == 200
    assert response.json()["found"] is True
    assert response.json()["offer"]["package_id"] == "VT-001"


def test_store_conflicting_version_locks_row_and_never_commits(monkeypatch):
    """Exercise SQL transaction guard itself, beyond mocked route behavior."""
    store = studio.OfferStore(SimpleNamespace())
    conn, cursor = MagicMock(), MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.return_value = {"updated_at": datetime(2026, 9, 17, 12, 0, 1)}
    monkeypatch.setattr(store, "connect", lambda: conn)
    with pytest.raises(HTTPException) as exc:
        store.mutate(
            "delete", package_id="VT-001", expected="2026-09-17 12:00:00.000000"
        )
    assert exc.value.status_code == 409
    cursor.execute.assert_called_once_with(
        "SELECT updated_at FROM dbo.offers WITH (UPDLOCK, HOLDLOCK) WHERE package_id=%s",
        ("VT-001",)
    )
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_rdi_calculated_field_cannot_be_written_to_sqlserver(harness, offer):
    offer["average_price_per_person"] = 1472.5
    response = harness.client.post(
        "/api/studio/offers", headers=harness.headers, json=offer
    )
    assert response.status_code == 422
    harness.store.mutate.assert_not_called()


def test_studio_returns_rdi_calculated_value_without_recomputing(harness, offer):
    # Use a deliberate mismatch: the page must expose what Redis actually contains.
    harness.redis.scan_iter.return_value = iter(["value-travel:context:offer:VT-001"])
    harness.redis.json.return_value.get.return_value = {
        **offer,
        "average_price_per_person": 123.45,
    }
    response = harness.client.get("/api/studio/offers", headers=harness.headers)
    assert response.status_code == 200
    assert response.json()["redis"][0]["room_capacity"] == 4
    assert response.json()["redis"][0]["average_price_per_person"] == 123.45
