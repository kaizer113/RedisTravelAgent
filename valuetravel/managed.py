from __future__ import annotations
import asyncio, hashlib, json, logging, re, threading, time
from datetime import UTC, datetime
from typing import Any
import httpx
from .config import Settings

log = logging.getLogger(__name__)
AGENT_MEMORY_MAX_CONNECTIONS = 20
AGENT_MEMORY_MAX_KEEPALIVE_CONNECTIONS = 10
MEMORY_INVENTORY_LIMIT = 99
REDIS_RECALL_MEMORY_TYPES = ("semantic", "episodic")


def safe_id(value, fallback):
    return re.sub(r"[^a-zA-Z0-9_-]", "-", str(value or fallback))[:128]


class MemoryService:
    """Official Redis Agent Memory SDK adapter, scoped by member and namespace."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Any | None = None
        self.models: Any | None = None
        self._http_client: httpx.Client | None = None
        self._async_http_client: httpx.AsyncClient | None = None
        if settings.memory_configured:
            try:
                from redis_agent_memory import AgentMemory, models

                def limits() -> httpx.Limits:
                    return httpx.Limits(
                        max_connections=AGENT_MEMORY_MAX_CONNECTIONS,
                        max_keepalive_connections=AGENT_MEMORY_MAX_KEEPALIVE_CONNECTIONS,
                        keepalive_expiry=settings.agent_memory_http_keepalive_seconds,
                    )

                self._http_client = httpx.Client(
                    follow_redirects=True,
                    limits=limits(),
                )
                self._async_http_client = httpx.AsyncClient(
                    follow_redirects=True,
                    limits=limits(),
                )
                self.client = AgentMemory(
                    settings.agent_memory_base_url,
                    store_id=settings.agent_memory_store_id,
                    api_key=settings.agent_memory_api_key,
                    client=self._http_client,
                    async_client=self._async_http_client,
                )
                self.models = models
            except Exception as exc:
                log.warning("Agent Memory SDK initialization failed: %s", exc)

    async def close(self) -> None:
        """Close the shared Agent Memory HTTP pools owned by this worker."""
        self.client = None
        async_client, self._async_http_client = self._async_http_client, None
        http_client, self._http_client = self._http_client, None
        if async_client is not None and not async_client.is_closed:
            await async_client.aclose()
        if http_client is not None and not http_client.is_closed:
            await asyncio.to_thread(http_client.close)

    def add_event(
        self,
        member_id: str,
        session_id: str,
        role: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if self.client is None or self.models is None:
            raise RuntimeError("Redis Agent Memory is not configured")
        role_enum = getattr(self.models.MessageRole, role.upper())
        actor_id = (
            member_id
            if role.upper() == "USER"
            else f"{self.settings.redis_namespace}-context"
            if role.upper() == "SYSTEM"
            else f"{self.settings.redis_namespace}-agent"
        )
        try:
            self.client.add_session_event(
                session_id=safe_id(session_id, "travel-session"),
                actor_id=safe_id(actor_id, "actor"),
                role=role_enum,
                content=[{"text": text}],
                created_at=datetime.now(UTC),
                metadata={
                    "channel": "web",
                    "agent": self.settings.effective_app_name,
                    **(metadata or {}),
                },
            )
            return True
        except Exception as exc:
            raise RuntimeError("Agent Memory event write failed") from exc

    async def ping(self) -> bool:
        """Use the managed Agent Memory health endpoint without reading member data."""
        if self.client is None:
            return False
        await self.client.health_async(timeout_ms=5_000)
        return True

    def short_term(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most recent Redis Agent Memory session events."""
        if self.client is None:
            return []
        try:
            response = self.client.get_session_memory(
                session_id=safe_id(session_id, "travel-session"),
                include_summarised_events=True,
            )
            events = list(getattr(response, "events", []) or [])[
                -max(1, min(limit, 20)) :
            ]
            return [
                event.model_dump(mode="json")
                if hasattr(event, "model_dump")
                else dict(event)
                for event in events
            ]
        except Exception as exc:
            # A new browser session has no server-side session record yet.
            if getattr(exc, "status_code", None) == 404 or "404" in str(exc):
                return []
            raise RuntimeError("Agent Memory session read failed") from exc

    def recall(
        self, member_id: str, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        if self.client is None or self.models is None:
            return []
        memory_filter: dict[str, Any] = {
            "owner_id": {"eq": safe_id(member_id, "anonymous")},
            "memory_type": {"in_": list(REDIS_RECALL_MEMORY_TYPES)},
        }
        namespace = self.settings.effective_agent_memory_namespace
        if namespace:
            memory_filter["namespace"] = {"eq": namespace}
        try:
            response = self.client.search_long_term_memory(
                request={
                    "text": query,
                    "similarity_threshold": self.settings.agent_memory_similarity_threshold,
                    "filter_op": self.models.FilterConjunction.ALL,
                    "filter_": memory_filter,
                    "limit": max(1, min(limit, 10)),
                },
            )
            return [
                item.model_dump(mode="json")
                if hasattr(item, "model_dump")
                else dict(item)
                for item in response.items
            ]
        except Exception as exc:
            raise RuntimeError("Agent Memory search failed") from exc

    def remember(
        self, member_id: str, fact: str, topics: list[str] | None = None
    ) -> bool:
        if self.client is None or self.models is None:
            raise RuntimeError("Redis Agent Memory is not configured")
        fact_digest = hashlib.sha256(fact.encode("utf-8")).hexdigest()[:16]
        memory_id = safe_id(f"{member_id}-{fact_digest}", "memory")
        memory = {
            "id": memory_id,
            "text": fact,
            "memory_type": "semantic",
            "owner_id": safe_id(member_id, "anonymous"),
            "topics": list(
                dict.fromkeys([*(topics or ["travel", "preference"]), "demo-created"])
            ),
        }
        namespace = self.settings.effective_agent_memory_namespace
        if namespace:
            memory["namespace"] = namespace
        try:
            response = self.client.bulk_create_long_term_memories(memories=[memory])
            if list(getattr(response, "errors", None) or []):
                raise RuntimeError("Agent Memory rejected the preference")
            return True
        except Exception as exc:
            raise RuntimeError("Agent Memory preference write failed") from exc

    def list_long_term(
        self,
        member_id: str,
        limit: int = MEMORY_INVENTORY_LIMIT,
    ) -> dict[str, Any]:
        """List a bounded member inventory without performing semantic retrieval."""
        if self.client is None or self.models is None:
            raise RuntimeError("Redis Agent Memory is not configured")

        display_limit = max(1, min(limit, MEMORY_INVENTORY_LIMIT))
        memory_filter: dict[str, Any] = {
            "owner_id": {"eq": safe_id(member_id, "anonymous")},
        }
        namespace = self.settings.effective_agent_memory_namespace
        if namespace:
            memory_filter["namespace"] = {"eq": namespace}
        response = self.client.search_long_term_memory(
            request={
                "filter_op": self.models.FilterConjunction.ALL,
                "filter_": memory_filter,
                "limit": display_limit + 1,
            }
        )
        records = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
            for item in response.items
        ]
        return {
            "count": min(len(records), display_limit),
            "truncated": len(records) > display_limit,
            "memories": records[:display_limit],
        }

    def reset_long_term(
        self,
        member_id: str,
        seeded_memories: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Preserve seeded records and remove other memories in one member scope."""
        if self.client is None or self.models is None:
            raise RuntimeError("Redis Agent Memory is not configured")

        owner_id = safe_id(member_id, "anonymous")
        namespace = self.settings.effective_agent_memory_namespace
        memory_filter: dict[str, Any] = {"owner_id": {"eq": owner_id}}
        if namespace:
            memory_filter["namespace"] = {"eq": namespace}
        existing_memory_ids: set[str] = set()
        page_token: str | None = None
        seen_page_tokens: set[str] = set()

        while True:
            response = self.client.search_long_term_memory(
                request={
                    "filter_op": self.models.FilterConjunction.ALL,
                    "filter_": memory_filter,
                    "limit": 100,
                    "page_token": page_token,
                }
            )
            existing_memory_ids.update(str(item.id) for item in response.items)
            next_page_token = getattr(response, "next_page_token", None)
            if not next_page_token:
                break
            if next_page_token in seen_page_tokens:
                raise RuntimeError("Agent Memory returned a repeated page token")
            seen_page_tokens.add(next_page_token)
            page_token = next_page_token

        seed_by_id = {str(memory["id"]): memory for memory in seeded_memories}
        memory_ids_to_delete = sorted(existing_memory_ids - seed_by_id.keys())
        deleted = 0
        for start in range(0, len(memory_ids_to_delete), 100):
            response = self.client.bulk_delete_long_term_memories(
                memory_ids=memory_ids_to_delete[start : start + 100]
            )
            errors = list(getattr(response, "errors", None) or [])
            if errors:
                raise RuntimeError(f"Failed to delete {len(errors)} long-term memories")
            deleted += len(response.deleted)

        missing_seed_ids = seed_by_id.keys() - existing_memory_ids
        records: list[dict[str, Any]] = []
        for memory in seeded_memories:
            if (
                memory["id"] not in missing_seed_ids
                or safe_id(str(memory.get("owner_id", "")), "anonymous") != owner_id
            ):
                continue
            record = {
                **memory,
                "owner_id": owner_id,
                "topics": list(
                    dict.fromkeys([*(memory.get("topics") or []), "demo-seed"])
                ),
            }
            if namespace:
                record["namespace"] = namespace
            else:
                record.pop("namespace", None)
            records.append(record)
        created = 0
        for start in range(0, len(records), 100):
            response = self.client.bulk_create_long_term_memories(
                memories=records[start : start + 100]
            )
            errors = list(getattr(response, "errors", None) or [])
            if errors:
                raise RuntimeError(f"Failed to restore {len(errors)} seeded memories")
            created += len(response.created)

        return {
            "deleted": deleted,
            "restored": created,
            "preserved": len(existing_memory_ids & seed_by_id.keys()),
        }


class ContextRetrieverService:
    def __init__(self, settings: Settings) -> None:
        self.agent_key = settings.mcp_agent_key
        self._tools_cache: list[dict[str, Any]] | None = None
        self._tools_lock = asyncio.Lock()
        self._client: Any | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> Any:
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    from context_surfaces import UnifiedClient

                    client = UnifiedClient()
                    await client.__aenter__()
                    self._client = client
        return self._client

    async def close(self) -> None:
        """Close the shared Context Retriever client owned by this worker."""
        client, self._client = self._client, None
        if client is not None:
            await client.__aexit__(None, None, None)

    @property
    def tools_cached(self) -> bool:
        return self._tools_cache is not None

    async def get_tools(
        self, *, force_refresh: bool = False
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return the governed catalog and whether it came from the server cache."""
        if not self.agent_key:
            return [], False
        if self._tools_cache is not None and not force_refresh:
            return self._tools_cache, True

        async with self._tools_lock:
            if self._tools_cache is not None and not force_refresh:
                return self._tools_cache, True
            try:
                client = await self._get_client()
                tools = await client.list_tools(self.agent_key)
                refreshed = [
                    tool if isinstance(tool, dict) else tool.model_dump()
                    for tool in tools
                ]
                self._tools_cache = refreshed
                return refreshed, False
            except Exception as exc:
                log.warning("Context Retriever tool listing failed open: %s", exc)
                if self._tools_cache is not None:
                    return self._tools_cache, True
                return [], False

    async def list_tools(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        tools, _ = await self.get_tools(force_refresh=force_refresh)
        return tools

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.agent_key:
            return {"ok": False, "error": "context_retriever_not_configured"}
        operation_started: float | None = None
        try:
            client = await self._get_client()
            operation_started = time.perf_counter()
            raw = await client.query_tool(
                agent_key=self.agent_key,
                tool_name=tool_name,
                arguments=arguments,
            )
            operation_duration_ms = round(
                (time.perf_counter() - operation_started) * 1000,
                2,
            )
            if isinstance(raw, dict):
                if raw.get("isError"):
                    return {
                        "ok": False,
                        "error": "context_retriever_tool_error",
                        "operation_duration_ms": operation_duration_ms,
                    }
                content = raw.get("content", [])
                if content and content[0].get("type") == "text":
                    result = json.loads(content[0].get("text", "{}"))
                else:
                    result = raw
                if isinstance(result, dict):
                    return {**result, "operation_duration_ms": operation_duration_ms}
                return {
                    "result": result,
                    "operation_duration_ms": operation_duration_ms,
                }
            return {
                "result": str(raw),
                "operation_duration_ms": operation_duration_ms,
            }
        except Exception as exc:
            log.warning("Context Retriever call failed open: %s", exc)
            result: dict[str, Any] = {"ok": False, "error": str(exc)}
            if operation_started is not None:
                result["operation_duration_ms"] = round(
                    (time.perf_counter() - operation_started) * 1000,
                    2,
                )
            return result
