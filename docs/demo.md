# VALUE TRAVEL recommended demo flow

An approximately 10–12 minute presenter flow for a member travel conversation.
Start with the traveler outcome, then use the service dashboard and live trace to
show the evidence. These are fictional offers and benefits, not real supplier prices or policies.

## Before the session

1. Open [VALUE TRAVEL](http://34.21.122.27:8080/). Select **Alex Rivera** and
   **Gemini 3.6 Flash**. Wait for the greeting.
2. Ensure **Context Retriever** is checked in the Redis services dashboard.
   Search and comparison require it to verify current offers.
3. Under **Presenter controls**, use **Reset demo cache** if you want to show a
   first miss. It rotates this application's LangCache scope, not the shared cache.
4. If needed, use **Reset member memory** to restore Alex's seeded preferences.
   This is a memory reset, not a MySQL-price or shortlist reset. Remove unwanted
   shortlist entries with their **Remove** controls.
5. For the optional RDI segment, have a terminal in this repository ready. Confirm
   VT-001 is at its baseline $5,890 and that RDI is streaming; see [RDI.md](RDI.md).
   Do not rerun bootstrap seeding over current offer records.

Alex (`travel-alex`) is a fictional Executive member departing SFO, with a
household of two adults and two children. Seeded preferences favor nonstop flights,
breakfast and a pool. Dates in the dataset begin **April 10, 2027**. All prices are
for the displayed party, airport and dates; changing these does not generate a new quote.

Responses and tool ordering vary with the model. Package values below are baseline
fixtures; MySQL changes can legitimately alter current prices. The deployed RDI
price-change sequence was verified; these instructions do not promise identical prose.

## 1. Find a family escape with clear trade-offs

Use this focused prompt for predictable Maui candidates:

> Find a five-night family vacation to Maui for four travelers departing SFO, under $6500. Compare the member value.

The **Family escape** shortcut is broader: it asks for Hawaii and can return offers
from several islands. Use it when you want broader discovery.

Baseline candidates:

| Offer | Payable total | Separate future Shop Card | Modeled future Executive reward | Trade-off |
| --- | ---: | ---: | ---: | --- |
| VT-001 Kaanapali Family Escape | $5,890 | $250 | $94.24 | Nonstop; breakfast included |
| VT-002 Wailea Ocean Retreat | $6,490 | $400 | $103.84 | Nonstop; breakfast included; higher total |
| VT-003 Kihei Beachside Value | $4,790 | $100 | $76.64 | Connection each way; breakfast not included |

Point to the trace: routing/cache bypass, Redis Agent Memory, RedisVL search and
embedding timing, governed offer retrieval, then Gemini. Offer retrieval can be
reported as an aggregate within the tool timing; do not promise one trace row per offer.

Say: “The cheaper package has different inclusions. The member sees what they pay
and the future benefits separately.” Never subtract a Shop Card or modeled reward
from the payable amount. These reward rules are synthetic.

## 2. Save a decision and compare current value

Prompt:

> Save VT-001 and VT-002 to my shortlist.

Then use **Compare value**:

> Compare the packages in my shortlist, including what I pay and the separate future benefits.

Expected behavior: the shortlist appears in the trip workspace. Comparison uses
fresh offer reads. Saving is a Redis workspace mutation, not a reservation,
payment or inventory hold. The baseline payable difference is $600.

## 3. Prove the price is sourced from MySQL

Optional live-data segment, approximately two minutes. The visual option is [Data Studio](data-studio.md): unlock it, edit VT-001’s price to 5790, save, and watch its Redis copy update. Use the Context Retriever check, then restore the original price. The same sequence is also available in a terminal at this repository:

```sh
.venv/bin/python scripts/rdi_offer.py VT-001 --price 5790 --verify
```

Wait for the script to report a Redis match. It writes only MySQL and observes Redis;
it does not copy the new price into Redis itself. Ask:

> Refresh the current quote for VT-001 and compare it with VT-002.

Expected current quote: **$5,790** for VT-001. Its modeled eligible base becomes
$4,632 and future Executive reward $92.64; the Shop Card stays $250. The price
comparison bypasses LangCache and retrieves current offers through Context Retriever.

Say: “A supplier-side price change travels through RDI into Redis. The next governed
read sees it, even though this conversation previously discussed another price.”

Restore the fixture immediately:

```sh
.venv/bin/python scripts/rdi_offer.py VT-001 --price 5890 --verify
```

Refresh the quote again. VT-001 must return to $5,890. RDI runs independently of chat
on `lg-rdi`; its CDC activity is not a dedicated row in the application dashboard.
The earlier deployment verification processed 18 initial rows plus both test updates
with zero rejections. That is a test observation, not a throughput benchmark.

## 4. Remember a preference and resume a visit

Prompt:

> Remember that I prefer a window seat on flights.

Use **New visit**, then **Pick up my trip**:

> Continue my saved trip. What did I shortlist and what do you remember about my preferences?

Expected behavior: the saved shortlist remains and the agent can retrieve the explicit
preference. Expand the memory trace to inspect actual returned facts. **New visit**
starts a new session; it does not clear the traveler workspace or long-term memory.

Explain the three roles: session events preserve conversation, long-term memory stores
preferences, and the Redis workspace stores explicit shortlist/notes. MySQL owns
current price and room counts. This demo has no Vertex AI Sessions or Memory Bank.

If a new preference is not returned immediately, inspect the trace and retry once;
do not claim that background memory extraction is synchronous. The seeded preferences
are a reliable fallback for showing existing long-term recall.

## 5. Let this trip override the household default

Use **Just us two**:

> This trip is just the two of us. Find a quiet adults-only Maui escape from SFO under $5000.

Baseline candidates are **VT-011 Wailea Couples Escape ($4,590)** and
**VT-012 Kapalua Quiet Coast ($3,990)**, each for two adults and five nights.
Both have nonstop flights; breakfast is included only with VT-011.

Say: “Alex often travels with children, but this request is explicitly for two adults.
Memory should help the member, not trap them in an old preference.” This is a current
trip instruction, not evidence that Alex's household permanently changed.

## 6. Show a safe semantic-cache hit

Use **Package inclusions**:

> What is included in a vacation package?

Then ask the approved paraphrase:

> What do vacation packages include?

After a cache reset, the first should miss and generate an answer from the fictional
policies. The second can hit LangCache and skip Gemini generation. Confirm the actual
hit in the trace; similarity matching is not a promise for arbitrary paraphrases.

The policy describes flights, hotel and transfers; other inclusions vary by offer.
The router first checks a small approved-question list, then semantic routing. Prices,
reservations, personal questions and unapproved wording bypass the response cache.
A cache hit still writes the user and assistant events to Agent Memory for continuity.
Do not claim that all memory activity disappears on a cache hit.

## 7. Draft an advisor handoff

Use **Advisor handoff**:

> Prepare an advisor handoff with my shortlist, preferences, decisions and unresolved questions.

Expected behavior: a draft summarizes the saved options, preferences and outstanding
choices. Any current price must come from a refreshed tool result. Because the story
changed from a family trip to a couples trip, the old family shortlist is a useful
unresolved choice to flag, not silently reinterpret.

Say: “The advisor gets the member's planning context and the remaining questions.”
The demo creates a draft in chat; it does not send anything to an advisor or a CRM.

## Close

Return to the member outcome: relevant options, transparent value, fresh prices and
continuity between visits. Use [presenter-notes.md](presenter-notes.md) for discovery
questions and claim boundaries, [demo2.md](demo2.md) for a continuous alternative
story, and [architecture.md](architecture.md) for the technical explanation.

## Reliable fallback

Use **Package inclusions** to demonstrate grounded generic guidance and cache behavior.
If Context Retriever is unavailable, say so; do not present an old price as current.
A warmup indicator is not evidence that a specific business transaction succeeded.
