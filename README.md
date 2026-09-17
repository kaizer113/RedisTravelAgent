# VALUE TRAVEL

A fictional travel concierge adapted from [Value Wholesale](https://github.com/kaizer113/RedisIrisXadk), preserving its Redis services dashboard, live trace and top prompt shortcuts.

## Capabilities

- RedisVL filtered vector search over 18 synthetic packages, using a shared local embedding model and RedisVL EmbeddingsCache.
- RedisVL Semantic Router and LangCache for approved general policy questions only. Personalized requests, prices, availability and reservations bypass the response cache.
- Redis Agent Memory for member/namespace-scoped preferences and session conversations.
- Context Retriever surface `ValueTravelLio` with 20 read-only tools over Traveler, Offer and Reservation entities.
- Persistent member shortlists and trip notes in Redis.
- Gemini on Vertex AI with a bounded function-calling loop. No Vertex AI Sessions or Memory Bank.
- MySQL source with 18 offers streamed through RDI 2.0.0 on `lg-rdi` into Redis JSON and Context Retriever. Live price-change propagation verified; see [RDI setup](docs/RDI.md).

## Demo

Presenter materials: [recommended workflow](docs/demo.md), [continuous member story](docs/demo2.md), [presenter notes and comments](docs/presenter-notes.md), and [architecture](docs/architecture.md) with [SVG](docs/architecture.svg) / [Mermaid source](docs/architecture.mmd).

Open http://34.21.122.27:8080 after deployment. Choose Alex, click Family escape, save a shortlist, then Remember me. New visit preserves preferences and the shortlist. Pick up my trip resumes planning; Just us two overrides household defaults. Advisor handoff drafts a summary without sending anything.

Ask Package inclusions twice, or use “What do vacation packages include?” to show semantic caching. Repeating search demonstrates embedding reuse. The service cards and trace show measured client-side timing, not estimated server timing.

All travelers, offers, prices, benefits and reservations are fictional. Package totals apply only to the stated dates, party size and airport. Future Shop Cards and modeled Executive rewards are separate from the payable total. No real booking, payment or cancellation is supported. The public demo has selectable synthetic personas, not customer authentication.

## Development

Copy `.env.example` to `.env`, configure service credentials and Google ADC, then run:

```
uv sync --extra dev
uv run python -m scripts.setup_context
uv run python -m scripts.seed
uv run uvicorn valuetravel.api:app --port 8080
uv run pytest -q
```

Context setup writes credentials into `.env.context`; merge its scoped key and surface ID into runtime `.env`. After RDI takes ownership of offers, use `--skip-offers` during Context setup. Never overwrite live CDC prices with seed records.

## Deployment

The VM container reuses Value Wholesale's existing CPU embedding runtime. Copy source to `/opt/value-travel`, preserve its mode-600 `.env`, and run `scripts/deploy.sh`. Only `value-travel-agent` on port 8080 is replaced. Value Wholesale remains on port 80. MySQL has its own container, volume and network.

Credentials are excluded from Git and Docker contexts. The Context admin key is not deployed to the application. Cache reset rotates only this application's scope; member reset targets only the selected owner and VALUE TRAVEL namespace.
