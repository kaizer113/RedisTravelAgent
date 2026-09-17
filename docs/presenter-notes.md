# VALUE TRAVEL presenter notes for a member travel conversation

These notes describe this implementation and its fictional dataset. They describe a fictional travel business, without implying that any real travel provider uses this architecture or applies these modeled benefits. Use [demo.md](demo.md) for the main run and [demo2.md](demo2.md) for a continuous member story.

## Opening talk track

> “VALUE TRAVEL explores a member experience where the concierge remembers useful preferences, helps compare the full package, and preserves the trip decisions between visits. The offers and members are fictional. The Redis services behind the experience are real integrations, and we can inspect the calls as they happen.”

Start with the customer experience. Reveal the trace after a package recommendation, so the architecture answers a question the audience has already seen.

## Comments to use at each moment

| Moment | Presenter comment | Evidence to show |
| --- | --- | --- |
| Family recommendation | “The member shouldn't need to restate every established travel preference.” | Retrieved Redis long-term memory facts, then a grounded package result |
| Package comparison | “Value includes what is in the package and which benefits arrive later.” | Total price, inclusions, Shop Card, modeled reward and cancellation details |
| Couples pivot | “A household profile is a default, not a restriction on today's trip.” | Two-person adults-only search and returned package fields |
| Saved shortlist | “The decision survives the conversation.” | Saved package in **Your trip workspace**, retained after **+ New visit** |
| Trip notes | “A temporary budget is a trip decision, not a permanent personal preference.” | **Save Trip Note** trace and workspace note |
| Advisor draft | “The next person can start with the decisions and unresolved questions.” | Draft response; no external send action exists |
| Source price update | “The recommendation consults current offer data, even when the earlier conversation contains an older price.” | MySQL change, RDI verification, subsequent Context Retriever offer lookup |
| Repeated policy question | “We can reuse approved general answers while keeping personalized and volatile answers out of the cache.” | Router decision, LangCache hit or miss, generation present or absent |

## What each service actually does here

**Redis Agent Memory** stores session conversation events and durable member preferences. The app retrieves both for personalized turns. Changing **Travel as** or clicking **+ New visit** creates a new session; the member's long-term memories remain. There is no VertexAISession or Memory Bank implementation.

**Redis database** stores the vector catalog, embedding cache, routing data, current offer documents, and member workspace. The workspace contains shortlist IDs, notes, and last search-result IDs and has a 30-day expiry renewed when saved. It is separate from managed Agent Memory.

**RedisVL** provides vector search with structured filters for destination, style, party size, and departure airport. Hawaii is explicitly expanded to the seeded Hawaiian destinations. Budget filtering happens after current offers are retrieved. The local CPU embedding model uses RedisVL's embedding cache. A cache hit means the query embedding was reused; it does not mean the entire personalized answer was cached.

**Context Retriever** exposes generated traveler, offer, and reservation tools. Package search first finds catalog candidates, then calls `get_offer_by_id` to check current offer fields. Disabling the Context Retriever checkbox prevents the chat tools from substituting stale offers or reading reservations. The workspace endpoint still reads offer JSON directly from Redis; avoid describing every visible price read as a Context Retriever call.

**LangCache** is used only for approved standalone policy questions that also pass the semantic route check. The allowlist is deliberately conservative. Price searches, comparisons, personal preferences, and reservation questions bypass it. Cache scopes include the application policy version, reset epoch, and model. **Reset demo cache** rotates the application's scope; old entries expire separately.

**Redis Data Integration** streams the MySQL `offers` table into Redis JSON for Context Retriever. MySQL holds mutable price, availability, eligible-reward base, cancellation, and offer metadata. The static travel catalog and policy text are not all sourced from MySQL. The deployed configuration and dated validation evidence are in [RDI.md](RDI.md).

**Gemini** interprets the request, calls bounded application tools, and writes the answer. A LangCache hit skips generation. Use the configured model shown in the UI; do not promise a particular model is available without checking the current environment.

## Explain the benefit math carefully

Every offer is fictional, with modeled total prices and mandatory fees. All seeded offers depart April 10, 2027; length and party size are fixed per offer. There is no live flight fare engine or repricing for arbitrary dates.

For seeded `VT-011`, the modeled amount payable is $4,590. The separate future Shop Card is $250. The synthetic eligible base is $3,672, producing a modeled Executive reward of $73.44 after travel. Neither future benefit reduces the amount payable. Gold Star members do not receive this modeled Executive reward.

These formulas demonstrate transparent presentation, not a real provider’s membership terms. The story uses only the fictional policies in this demo.

## Read the dashboard honestly

- Service configuration and warm-up probes are useful readiness signals, not proof of every downstream result.
- Highlight a service's measured call after it completes. Do not quote a latency target from an empty or warm-up-only panel.
- The p95 view summarizes recorded process-local samples. It is not a load test or a production SLA.
- A LangCache miss can also occur after a scope reset or model change. Similar wording does not guarantee a hit.
- Semantic routing in this implementation decides policy-cache eligibility; it does not block all off-topic requests.
- The inherited dashboard layout can accommodate a tool-call-cache row, but the current backend does not implement or emit tool-call-cache results. Do not claim that product feature from the panel layout.
- Card match text summarizes actual offer fields; there is no calibrated personalization score or verified resort-quality rating.

## State, boundaries, and recovery

This is a shared demo with selectable synthetic members, not a signed-in customer application. Backend member IDs scope the memory and workspace; the UI selector is not production authentication or authorization.

**+ New visit** preserves the shortlist and notes. **Reset member memory** restores seeded long-term facts only. **Remove** changes one saved package. There is no clear-all-trip-notes button, multi-trip selector, or live advisor console. Notes append; to change direction, explicitly save a new note that supersedes the old plan and verify the generated response uses it.

A text acknowledgment alone is not proof that something was saved. Check the memory tool trace, workspace update, or memory inventory. If a required service fails, the app reports an error; do not narrate the expected response as if it completed. Use **Package inclusions** as a narrower alternative only when the current service path is healthy enough to answer it.

The advisor handoff is a generated draft. No email, CRM ticket, contact-center queue, payment, reservation, or cancellation is created. The synthetic reservation view is a read-only example.

## Questions to ask the audience

- Where do members currently repeat information: a later web visit, a phone call, or a different traveler in the household?
- Which preferences should persist, and which should expire with a trip?
- Which package fields can change during a planning session, and which system should remain authoritative?
- What must an advisor see before continuing a conversation?
- Which general answers are safe to reuse, and who owns those policy changes?
- Which measurable outcome would justify a pilot: reduced repeated questions, useful shortlist completion, or less advisor time reconstructing context?

These are discovery questions, not claims about a particular travel provider's systems or problems. Suggested business outcomes remain hypotheses until measured with a suitable baseline and customer-approved data.

## Verification language

Say “the code supports” or “we expect” before a step has run. Say “this request returned” after inspecting the actual output. The RDI deployment document records specific dated checks; that is narrower than claiming the entire member journey passed end to end. This document itself is not a test report.
