import json, threading, time
import redis
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery
from redisvl.query.filter import Tag, Num
from redisvl.extensions.cache.embeddings import EmbeddingsCache
from redisvl.utils.vectorize import HFTextVectorizer
from redisvl.extensions.router import SemanticRouter, Route
from .data import PACKAGES, POLICIES


class Search:
    def __init__(self, settings):
        self.settings = settings
        self.redis = redis.Redis.from_url(
            settings.redis_url, socket_timeout=8, socket_connect_timeout=5
        )
        self.cache = EmbeddingsCache(
            name="value-travel:embeddings", ttl=86400, redis_client=self.redis
        )
        self._vectorizer = None
        self._lock = threading.RLock()
        self._router = None
        self.index = SearchIndex.from_dict(
            {
                "index": {
                    "name": "value-travel:catalog-v1",
                    "prefix": "value-travel:catalog",
                    "storage_type": "hash",
                },
                "fields": [
                    {"name": "package_id", "type": "tag"},
                    {"name": "destination", "type": "tag"},
                    {"name": "style", "type": "tag"},
                    {"name": "home_airport", "type": "tag"},
                    {"name": "travelers", "type": "numeric"},
                    {"name": "description", "type": "text"},
                    {"name": "record", "type": "text"},
                    {
                        "name": "embedding",
                        "type": "vector",
                        "attrs": {
                            "dims": 384,
                            "algorithm": "flat",
                            "datatype": "float32",
                            "distance_metric": "cosine",
                        },
                    },
                ],
            },
            redis_client=self.redis,
        )

    @property
    def vectorizer(self):
        with self._lock:
            if self._vectorizer is None:
                self._vectorizer = HFTextVectorizer(
                    model=self.settings.embedding_model,
                    dtype="float32",
                    cache=self.cache,
                    device="cpu",
                    model_kwargs={"dtype": "float32"},
                )
            return self._vectorizer

    def embed(self, text):
        start = time.perf_counter()
        hit = self.cache.exists(content=text, model_name=self.settings.embedding_model)
        with self._lock:
            vector = self.vectorizer.embed(text, as_buffer=True)
        return vector, round((time.perf_counter() - start) * 1000, 2), hit

    def seed(self):
        self.index.create(overwrite=False)
        records = []
        for p in PACKAGES:
            vector, _, _ = self.embed(p["description"])
            # Mutable commercial fields belong only in current Offer records.
            static = {
                k: v
                for k, v in p.items()
                if k
                not in (
                    "total_price",
                    "available_rooms",
                    "eligible_reward_base",
                    "cancellation",
                )
            }
            records.append(
                {
                    **{
                        k: static[k]
                        for k in (
                            "package_id",
                            "destination",
                            "style",
                            "home_airport",
                            "travelers",
                            "description",
                        )
                    },
                    "record": json.dumps(static),
                    "embedding": vector,
                }
            )
        self.index.load(records, id_field="package_id")
        return len(records)

    def search(self, query, destination="", style="", travelers=0, home_airport=""):
        vector, ms, hit = self.embed(query)
        filters = []
        if destination:
            if destination.lower() in ("hawaii", "hawaiian islands"):
                filters.append(Tag("destination") == ["Maui", "Oahu", "Hawaii"])
            else:
                filters.append(Tag("destination") == destination)
        if style:
            filters.append(Tag("style") == style)
        if travelers:
            filters.append(Num("travelers") == travelers)
        if home_airport:
            filters.append(Tag("home_airport") == home_airport.upper())
        expression = filters[0] if filters else "*"
        for item in filters[1:]:
            expression = expression & item
        start = time.perf_counter()
        rows = self.index.query(
            VectorQuery(
                vector=vector,
                vector_field_name="embedding",
                return_fields=["record"],
                num_results=len(PACKAGES),
                filter_expression=expression,
            )
        )
        return [json.loads(r["record"]) for r in rows], {
            "embedding_ms": ms,
            "embedding_hit": hit,
            "search_ms": round((time.perf_counter() - start) * 1000, 2),
        }

    def router(self):
        with self._lock:
            if self._router is None:
                self._router = SemanticRouter(
                    name="value-travel:router-v1",
                    vectorizer=self.vectorizer,
                    redis_client=self.redis,
                    overwrite=False,
                    routes=[
                        Route(
                            name="travel_policy",
                            distance_threshold=0.35,
                            references=[p["title"] for p in POLICIES]
                            + [
                                "Explain Executive membership travel rewards",
                                "What is included in vacation packages?",
                                "Explain package cancellation policies",
                            ],
                        ),
                        Route(
                            name="trip_planning",
                            distance_threshold=0.55,
                            references=[
                                "Find a family vacation to Hawaii",
                                "Compare these packages",
                                "Show current prices",
                                "Remember my travel preferences",
                                "What is my next reservation?",
                            ],
                        ),
                    ],
                )
            return self._router

    def route(self, message):
        # Only standalone generic policy questions qualify. All trip/member data bypasses.
        import re

        safe_questions = {
            "what is included in a vacation package",
            "what do vacation packages include",
            "explain vacation package inclusions",
            "what comes with a vacation package",
            "how do executive member benefits work",
            "explain executive membership travel rewards",
            "what are executive travel benefits",
            "how does cancellation work",
            "explain package cancellation policies",
            "what should i check when renting a car",
        }
        normalized = re.sub(r"[^a-z0-9 ]", "", message.lower()).strip()
        normalized = re.sub(r"\s+", " ", normalized)
        if normalized not in safe_questions:
            return {
                "cacheable": False,
                "reason": "Personalized, current-data, or unapproved reusable request",
            }
        start = time.perf_counter()
        hit = self.cache.exists(
            content=message, model_name=self.settings.embedding_model
        )
        result = self.router()(message)
        name = getattr(result, "name", None)
        return {
            "cacheable": name == "travel_policy",
            "reason": name or "No safe reusable route",
            "embedding_hit": hit,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        }
