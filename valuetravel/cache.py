import httpx


class LangCache:
    def __init__(self, settings, redis):
        self.settings = settings
        self.redis = redis
        self.base = f"{settings.langcache_host.rstrip('/')}/v1/caches/{settings.langcache_cache_id}"
        self.client = httpx.AsyncClient(
            timeout=10,
            headers={"Authorization": f"Bearer {settings.langcache_api_key}"},
        )

    def scope(self, model):
        epoch = self.redis.get("value-travel:cache-epoch") or b"0"
        return f"value-travel:policy-v1:{epoch.decode()}:{model}"

    async def search(self, prompt, scope):
        prefix = f"scope:{scope}\n"
        response = await self.client.post(
            f"{self.base}/entries/search",
            json={
                "prompt": prefix + prompt,
                "similarityThreshold": 0.9,
                "searchStrategies": ["semantic"],
            },
        )
        response.raise_for_status()
        # Verify exact scope even if the service returns a semantically close different scope.
        return next(
            (
                e
                for e in response.json().get("data", [])
                if e.get("prompt", "").startswith(prefix)
            ),
            None,
        )

    async def store(self, prompt, answer, scope):
        response = await self.client.post(
            f"{self.base}/entries",
            json={
                "prompt": f"scope:{scope}\n{prompt}",
                "response": answer,
                "ttlMillis": 86400000,
            },
        )
        response.raise_for_status()

    def reset(self):
        # Invalidate this application only; never flush the managed cache globally.
        return self.redis.incr("value-travel:cache-epoch")
