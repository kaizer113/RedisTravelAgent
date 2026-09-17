# VALUE TRAVEL deployed architecture

![VALUE TRAVEL architecture](architecture.svg)

[Editable Mermaid source](architecture.mmd) · [Demo flow](demo.md) · [RDI operations](RDI.md)

This describes the deployed demo as verified September 17, 2026. All business data
is synthetic. Redis services and the MySQL CDC pipeline are real integrations.

## Request path

The browser talks to FastAPI on the shared VM's port 8080 and consumes streamed
NDJSON events for answers, packages, workspace changes and trace timings. The
application calls Gemini through the Google Gen AI SDK on Vertex AI with a bounded
function-calling loop. There is no ADK Runner, Vertex AI Session service or Memory Bank.

For approved standalone policy questions, an explicit allowlist and RedisVL Semantic
Router decide LangCache eligibility. A verified scope-matching hit returns an answer
without Gemini generation; the turn is still appended to Agent Memory. Cache misses
and ineligible requests proceed through the normal application path. This router is
a cache-eligibility mechanism, not the wholesale demo's out-of-domain blocking feature.

Personalized requests retrieve scoped session events and long-term preferences, plus
workspace context. Context Retriever supplies the traveler profile when enabled.
Gemini requests bounded application tools; the application executes them and returns
results for generation. Tool choice and order vary by request.

## Discovery and current offers

RedisVL searches a catalog vector index with destination, style, party-size and
airport filters. Embeddings are computed by the local
`redis/langcache-embed-v3-small` model and reused through RedisVL EmbeddingsCache.
The search returns candidate IDs, not authoritative current prices.

Search and comparison read each candidate's current Offer through Context Retriever.
The application removes unavailable offers and applies the budget filter to these
fresh values, then assembles cards with static catalog descriptions and modeled
member benefits. Context Retriever must be enabled for this recommendation path;
old catalog prices are not substituted when it is disabled.

Shortlist-card refreshes have a separate direct Redis JSON read path. Therefore,
not every UI read passes through Context Retriever. Its 20 tools govern reads over
Traveler, Offer and Reservation entities; they do not perform booking or payments.

## Data ownership

| Data | Owner and storage | Behavior |
| --- | --- | --- |
| Offer price, rooms and current terms | MySQL `value_travel.offers` → RDI → Redis Offer JSON | CDC maintains the current operational record |
| Package descriptions, flight flags, party size, Shop Cards | Synthetic fixtures / RedisVL catalog | Static seeded discovery data; not all catalog fields use CDC |
| Traveler and reservation records | Seeded Redis JSON, exposed through Context Retriever | Synthetic operational context; reservation is not a real booking |
| Session events | Redis Agent Memory | Selected member and session scope |
| Durable preferences | Redis Agent Memory | Selected owner and `value-travel` namespace; explicit preference tool |
| Shortlist, trip notes and last results | Redis workspace key per member | 30-day TTL renewed on writes; independent of conversation memory |
| Generic policy responses | LangCache | Model/app/policy-version/cache-epoch scope; one-day entry TTL |
| Embeddings and routing index | Application Redis with RedisVL | Reuses local embedding computation and supports semantic routing |
| RDI streams/checkpoints | Separate Redis state database | noeviction, AOF enabled, nonclustered |

The diagram treats Agent Memory and LangCache as managed services; it does not assert
that their internal storage shares the application database. API credentials stay on
the backend. The Context Retriever admin key is not deployed to the application.

## Continuous data path

`valuewholesale-demo` (`10.42.0.3`) hosts MySQL at private port 3307. Its binlogs use
ROW/FULL images with GTIDs enabled. The separate Ubuntu VM `lg-rdi` (`10.42.0.4`)
runs RDI 2.0.0, a Debezium collector and the classic processor on K3s. Both VMs are
on `lg-peering-demo-vpc` / `lg-peering-demo-us-east4`.

RDI replaces the nine business fields in `value-travel:context:offer:VT-001` through
`VT-018` with JSON from MySQL. Context Retriever reads those documents. RDI's state
database is separate from the target. Pod/service CIDRs avoid the VPC's 10.42 range.
MySQL ingress is restricted to the RDI VM; the RDI HTTPS API is accessed locally
through SSH. See [RDI.md](RDI.md) for deployment and verification commands.

The verified proof changed VT-001 in MySQL from $5,890 to $5,790, observed the new
value in Redis and Context Retriever, then restored $5,890 through the same path.
RDI reported 18 inserts and two updates with no rejected records. This is correctness
evidence for that test, not a production availability or latency guarantee.

## What the trace proves

The application dashboard and trace expose client-observed service/tool timings,
cache outcomes, memory operations and generation. Nested operations and concurrent
requests can overlap; do not sum rows into server processing time. A configured or
warm service card does not prove a particular quote succeeded. Inspect the tool result.
RDI is a continuous background path and has its own CLI status; it has no dedicated
service card in this UI.

## Demo boundaries

This is a single-instance demo, not a highly available production deployment. Personas
are selectable synthetic identities, not authenticated customers. A shortlist is not an
inventory hold; an advisor handoff is a chat draft, not a CRM submission. No real booking,
charge, cancellation or supplier repricing exists. Current trip instructions take priority
over remembered defaults, and modeled future benefits never reduce the payable price.
