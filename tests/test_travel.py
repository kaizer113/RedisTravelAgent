"""Regression checks for member boundaries and mutable travel data.

External services are mocked; SDK request/response types stay real.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from redis_agent_memory import models
from google.genai import types
from valuetravel import api
from valuetravel.cache import LangCache
from valuetravel.managed import MemoryService, ContextRetrieverService
from valuetravel.search import Search
from valuetravel.data import PACKAGES


@pytest.fixture
def memory():
    service = MemoryService.__new__(MemoryService)
    service.models = models
    service.client = Mock()
    service.settings = SimpleNamespace(
        effective_agent_memory_namespace="value-travel",
        agent_memory_similarity_threshold=0.25,
        redis_namespace="value-travel",
        effective_app_name="value-travel",
    )
    return service


def test_session_identifiers_include_member():
    assert api.sid_for("travel-alex", "same-browser") != api.sid_for(
        "travel-maya", "same-browser"
    )
    assert api.sid_for("travel-alex", "same-browser") == api.sid_for(
        "travel-alex", "same-browser"
    )


def test_recall_intersects_member_and_namespace(memory):
    memory.client.search_long_term_memory.return_value = SimpleNamespace(items=[])
    memory.recall("travel-alex", "nonstop flights")
    request = memory.client.search_long_term_memory.call_args.kwargs["request"]
    assert request["filter_op"] == models.FilterConjunction.ALL
    assert request["filter_"]["owner_id"] == {"eq": "travel-alex"}
    assert request["filter_"]["namespace"] == {"eq": "value-travel"}


def test_remember_keeps_owner_namespace_and_checks_partial_failure(memory):
    memory.client.bulk_create_long_term_memories.return_value = SimpleNamespace(
        errors=[]
    )
    memory.remember("travel-maya", "Quiet resorts")
    record = memory.client.bulk_create_long_term_memories.call_args.kwargs["memories"][
        0
    ]
    assert record["owner_id"] == "travel-maya" and record["namespace"] == "value-travel"
    memory.client.bulk_create_long_term_memories.return_value = SimpleNamespace(
        errors=["rejected"]
    )
    with pytest.raises(RuntimeError):
        memory.remember("travel-maya", "Quiet resorts")


def test_unavailable_memory_cannot_claim_write_success(memory):
    memory.client = None
    with pytest.raises(RuntimeError):
        memory.remember("travel-alex", "Breakfast")
    with pytest.raises(RuntimeError):
        memory.add_event("travel-alex", "session", "USER", "Hello")


@pytest.mark.asyncio
async def test_context_sdk_envelope_and_errors():
    service = ContextRetrieverService(SimpleNamespace(mcp_agent_key="test-key"))
    client = SimpleNamespace(
        query_tool=AsyncMock(
            return_value={
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"package_id": "VT-001", "total_price": 5890}
                        ),
                    }
                ]
            }
        )
    )
    service._get_client = AsyncMock(return_value=client)
    result = await service.call("get_offer_by_id", {"id": "VT-001"})
    assert result["total_price"] == 5890
    client.query_tool.assert_awaited_once_with(
        agent_key="test-key", tool_name="get_offer_by_id", arguments={"id": "VT-001"}
    )
    client.query_tool.return_value = {
        "isError": True,
        "content": [{"type": "text", "text": "{}"}],
    }
    assert (await service.call("get_offer_by_id", {"id": "VT-001"}))["ok"] is False


def test_current_offer_controls_payable_and_future_reward(monkeypatch):
    current = {**PACKAGES[0], "total_price": 6000, "eligible_reward_base": 4500}
    monkeypatch.setattr(api, "raw_offer", lambda pid: current)
    executive = api.display_package("VT-001", "travel-alex")
    regular = api.display_package("VT-001", "travel-jordan")
    assert executive["total_price"] == 6000
    assert executive["executive_reward"] == 90
    assert executive["shop_card"] == 250
    assert regular["executive_reward"] == 0
    current["total_price"] = 5700
    assert api.display_package("VT-001", "travel-alex")["total_price"] == 5700


@pytest.mark.asyncio
async def test_live_offers_filter_budget_and_unavailable_rooms(monkeypatch):
    monkeypatch.setattr(
        api.search,
        "search",
        Mock(
            return_value=(
                [
                    {"package_id": "VT-001"},
                    {"package_id": "VT-002"},
                    {"package_id": "VT-003"},
                ],
                {},
            )
        ),
    )
    offers = {
        "VT-001": {**PACKAGES[0], "total_price": 4000},
        "VT-002": {**PACKAGES[1], "total_price": 4200, "available_rooms": 0},
        "VT-003": {**PACKAGES[2], "total_price": 6000},
    }

    async def context(tool, args):
        return offers[args["id"]]

    monkeypatch.setattr(api, "live_context", context)
    monkeypatch.setattr(api, "workspace", lambda mid: {"shortlist": [], "notes": []})
    monkeypatch.setattr(api, "save_workspace", Mock())
    result, packages, _ = await api.execute_tool(
        "search_packages", {"query": "family", "max_budget": 5000}, api.Request()
    )
    assert [p["package_id"] for p in packages] == ["VT-001"]
    assert result["packages"][0]["total_price"] == 4000


@pytest.mark.asyncio
async def test_context_disabled_does_not_substitute_catalog_price(monkeypatch):
    monkeypatch.setattr(
        api, "raw_offer", Mock(side_effect=AssertionError("Must not fall back"))
    )
    result, packages, _ = await api.execute_tool(
        "compare_packages",
        {"package_ids": ["VT-001"]},
        api.Request(context_retriever_enabled=False),
    )
    assert "error" in result and packages == []


@pytest.mark.asyncio
async def test_reservations_enforce_requested_member(monkeypatch):
    call = AsyncMock(
        return_value={
            "results": [{"member_id": "travel-alex"}, {"member_id": "travel-maya"}],
            "count": 2,
            "total_count": 2,
        }
    )
    monkeypatch.setattr(api, "live_context", call)
    result, _, _ = await api.execute_tool(
        "get_reservations", {}, api.Request(member_id="travel-alex")
    )
    assert result["results"] == [{"member_id": "travel-alex"}]
    assert result["count"] == result["total_count"] == 1
    call.assert_awaited_once_with(
        "filter_reservation",
        {"tag_conditions": [{"field": "member_id", "value": "travel-alex"}]},
    )


@pytest.mark.asyncio
async def test_cache_scope_rejects_other_application_and_epoch():
    cache = LangCache.__new__(LangCache)
    cache.base = "https://example.invalid/cache"
    response = Mock()
    response.json.return_value = {
        "data": [
            {"prompt": "scope:other-app\nQuestion", "response": "wrong"},
            {
                "prompt": "scope:value-travel:policy-v1:0:model\nQuestion",
                "response": "old",
            },
            {
                "prompt": "scope:value-travel:policy-v1:1:model\nQuestion",
                "response": "right",
            },
        ]
    }
    cache.client = SimpleNamespace(post=AsyncMock(return_value=response))
    assert (await cache.search("Question", "value-travel:policy-v1:1:model"))[
        "response"
    ] == "right"


@pytest.mark.parametrize(
    "message",
    [
        "What are my benefits?",
        "Compare these packages",
        "Show current prices",
        "What is availability in Maui?",
        "What is included for VT-001?",
        "What is included for Alex?",
    ],
)
def test_current_or_personal_questions_never_cache(message):
    search = Search.__new__(Search)
    search.settings = SimpleNamespace(embedding_model="test")
    search.cache = Mock()
    search.router = lambda: lambda _: SimpleNamespace(name="travel_policy")
    assert search.route(message)["cacheable"] is False


def test_gemini_tool_response_uses_real_sdk_shape():
    tool = types.Tool(function_declarations=api.TOOLS)
    assert len(tool.function_declarations) == 8
    part = types.Part.from_function_response(
        name="get_reservations", response={"results": []}
    )
    assert part.function_response.name == "get_reservations"
    assert part.function_response.response == {"results": []}


def test_search_considers_entire_catalog_before_current_budget_filter():
    search = Search.__new__(Search)
    search.embed = Mock(return_value=([0.0] * 384, 1.0, True))
    search.index = Mock()
    search.index.query.return_value = []
    search.search("vacation")
    query = search.index.query.call_args.args[0]
    assert f"KNN {len(PACKAGES)} " in query.get_args()[0]


@pytest.mark.asyncio
async def test_gemini_tool_loop_returns_response_with_real_content_shapes(monkeypatch):
    tool_content = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=types.FunctionCall(name="read_travel_policies", args={})
            )
        ],
    )
    final_content = types.Content(
        role="model",
        parts=[types.Part.from_text(text="Packages include hotel and flights.")],
    )
    responses = [
        types.GenerateContentResponse(
            candidates=[types.Candidate(content=tool_content)]
        ),
        types.GenerateContentResponse(
            candidates=[types.Candidate(content=final_content)]
        ),
    ]
    generate = AsyncMock(side_effect=responses)
    monkeypatch.setattr(
        api,
        "model_client",
        SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))
        ),
    )
    monkeypatch.setattr(
        api.search, "route", Mock(return_value={"cacheable": False, "reason": "Trip"})
    )
    monkeypatch.setattr(api.cache, "scope", lambda _: "test-scope")
    fake_memory = SimpleNamespace(
        short_term=Mock(return_value=[]),
        recall=Mock(return_value=[]),
        add_event=Mock(return_value=True),
    )
    monkeypatch.setattr(api, "memory", fake_memory)
    monkeypatch.setattr(api, "workspace", lambda mid: {"shortlist": [], "notes": []})
    req = api.Request(
        message="Explain travel details",
        context_retriever_enabled=False,
        session_id="test-tool-loop",
    )
    events = [event async for event in api.chat_events(req)]
    assert events[-2]["answer"] == "Packages include hotel and flights."
    assert generate.await_count == 2
    contents = generate.call_args.kwargs["contents"]
    function_responses = [
        p.function_response for c in contents for p in c.parts if p.function_response
    ]
    assert function_responses[0].name == "read_travel_policies"
    assert "policies" in function_responses[0].response
    assert fake_memory.add_event.call_count == 2


def test_function_enums_do_not_include_empty_values():
    from valuetravel.api import TOOLS

    def check(value):
        if isinstance(value, dict):
            if "enum" in value:
                assert "" not in value["enum"]
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(TOOLS)


def test_raw_offer_reads_context_retriever_json_document(monkeypatch):
    # Shape verified against JSON.GET on the provisioned Context Retriever data.
    document = {
        "available_rooms": 4,
        "room_capacity": 4,
        "average_price_per_person": 1472.5,
        "cancellation": "Refundable hotel until 30 days before departure; flight fare rules apply.",
        "data_label": "Synthetic demo offer",
        "departure_date": "2027-04-10",
        "destination": "Maui",
        "eligible_reward_base": 4712.0,
        "name": "Kaanapali Family Escape",
        "package_id": "VT-001",
        "total_price": 5890.0,
    }
    connection = Mock()
    connection.json.return_value.get.return_value = document
    connection.hgetall.side_effect = AssertionError(
        "Context Retriever offers are JSON, not hashes"
    )
    monkeypatch.setattr(api.search, "redis", connection)
    assert api.raw_offer("VT-001") == document
    connection.json.return_value.get.assert_called_once_with(
        "value-travel:context:offer:VT-001"
    )
