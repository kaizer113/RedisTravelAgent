# VALUE TRAVEL: a household, a change of plans, and a return visit

Use this continuous story when the audience cares most about the member journey. It follows Alex from family planning to a couples escape, then into a later visit and an advisor handoff draft. The feature-oriented path is in [demo.md](demo.md).

This is a presenter script grounded in the current implementation and synthetic dataset. **Expected** describes what the code and instructions support; it is not a claim that every generated response or this entire sequence has been verified live. Check the actual trace and returned offers during the presentation. Package ordering and wording can vary.

## Prepare the story

Open [VALUE TRAVEL](http://34.21.122.27:8080/). Select **Alex Rivera** under **Travel as** and keep that member selected. Use the configured default model. Leave **Context Retriever** enabled in the services dashboard.

Alex is the fictional Executive member `travel-alex`, based at SFO, with two adults and two children in the household. Seeded preferences favor nonstop flights, breakfast, and a pool. These are demo facts, not customer data.

Inspect **Your trip workspace** before presenting. Use **Remove** on any saved package you do not want in this story. **+ New visit** clears the visible conversation and starts a new session; it preserves the member's memories, shortlist, and trip notes. **Reset member memory** restores seeded long-term preferences but does not clear the workspace. Existing trip notes may remain, so do not promise a completely pristine account after either control.

Wait for warm-up to finish. The services panel reports configuration and probe results; an enabled card alone does not prove a later request succeeded. Expand trace results when showing evidence.

## 1. Begin with a household vacation

Click **Family escape**, which submits:

> Find a family vacation to Hawaii for four travelers departing SFO, under $6500. Compare the member value.

Expected: Redis Agent Memory retrieves Alex's preferences, RedisVL searches the package catalog, and Context Retriever checks the current offers. Hawaii expands to Maui, Oahu, and Hawaii Island in the search filter. All six seeded Hawaii family offers meet the initial budget, but breakfast and nonstop service differ.

Tell the audience:

> “Alex has supplied today's destination and budget. The concierge can also use established household preferences. The package record still decides what is actually included.”

Point to a real package card and its flight/inclusion labels. Open **Inclusions, terms & modeled benefits**. Explain that the amount payable is separate from a future Shop Card and the modeled Executive reward.

At the original seed values, Kaanapali Family Escape (`VT-001`) is $5,890 for four travelers, five nights, departing SFO on April 10, 2027. Its separate Shop Card is $250 and modeled future Executive reward is $94.24. These are baseline fictional values; use the current returned price if the RDI demonstration has changed it.

A lower-priced connecting-flight option is a trade-off, not automatically the best recommendation. Kihei Beachside Value (`VT-003`) has one connection and no included breakfast.

## 2. Save a decision, not a booking

On one family offer, click **+ Save to trip**. The package should appear in **Your trip workspace**. Then ask:

> For this trip, note that our budget ceiling is $6500 and we still need to decide between Maui and Oahu. Keep those as trip decisions, not permanent travel preferences.

Expected: the trace shows **Save Trip Note** if the model invokes the trip-note tool, and the saved note appears in the workspace. Verify this rather than treating a prose acknowledgment as proof of persistence.

Presenter comment:

> “The shortlist and current decisions are explicit trip state. Remembering a person's travel preferences serves a different purpose.”

The demo cannot reserve inventory, charge a card, or place a booking. Saving a package makes none of those commitments.

## 3. Change who is traveling

Click **Just us two**:

> This trip is just the two of us. Find a quiet adults-only Maui escape from SFO under $5000.

Expected: the current instruction overrides the four-person household default for this search. The synthetic catalog has two matching adults-only Maui offers:

| Offer | Seed package total | Separate future Shop Card | Breakfast |
| --- | ---: | ---: | --- |
| Wailea Couples Escape (`VT-011`) | $4,590 | $250 | Included |
| Kapalua Quiet Coast (`VT-012`) | $3,990 | $150 | Not included |

Both are five-night, two-person packages with nonstop SFO flights. Prices may differ after source updates. “Quiet” is present in the product descriptions; the catalog does not offer verified noise ratings. Do not present that preference as a quantitative guarantee.

Presenter comment:

> “The system remembers the household without forcing every trip to match it. Today's request wins.”

Use **Remove** in the workspace to remove the earlier family option, then save one or both couples offers. Shortlist entries do not automatically disappear when the traveler changes direction.

Ask:

> Update my trip notes: this is now a couples trip to Maui for two, with a $5000 ceiling. The earlier family plan is superseded. We still need to decide whether breakfast is worth the price difference.

The current tool appends notes; it does not edit or delete older ones. The new note should explicitly supersede the previous plan. Verify the resulting notes and the final interpretation rather than promising a rewritten history.

## 4. Make a durable preference explicit

Click **Remember me**:

> Remember that I prefer nonstop flights and hotels with breakfast included.

Expected: **Redis long-term memory · save preference** appears in the trace. Inspect **Redis** under the presenter's long-term-memory controls to view the selected member's records. This can overlap with Alex's seed preferences; do not claim deduplication unless the actual inventory shows it.

The current trip budget and party size belong in trip notes. The explicit recurring preference belongs in Agent Memory.

## 5. Return without starting over

Click **+ New visit**, then **Pick up my trip**:

> Continue my saved trip. What did I shortlist and what do you remember about my preferences?

Expected: the old visible chat is gone while the shortlist and notes remain. Vale retrieves the selected member's long-term preferences and reads the workspace. It should treat the newer couples-trip note as superseding the family plan.

If Alex's household reappears as this trip's party size, point out the mismatch and correct it; do not describe the intended behavior as a passed test. For a clear recovery prompt:

> Use the latest trip decision: this trip is for two adults to Maui. Read my saved shortlist and compare the current offers.

Presenter comment:

> “Continuity is useful only if it brings forward the right decisions. We can inspect the remembered facts, saved trip state, and current offer lookup separately.”

The new session does not replay the entire previous session automatically. The continuity being shown here comes from durable member memory and persisted workspace state.

## 6. Draft the advisor handoff

Click **Advisor handoff** at the top or the **Advisor handoff ↗** button in the workspace. Both submit a chat request; neither sends anything to another person.

Expected: a draft containing the traveler, shortlist, relevant preferences, trip decisions, trade-offs, and unresolved questions. If quoting current price or availability, confirm the trace contains **Context Retriever · current offers**. A workspace read alone reads current Redis offer records directly; it is not the same as a governed Context Retriever quote.

Presenter comment:

> “An advisor can begin with the decisions already made and the questions still open. This is a handoff draft, not a live contact-center integration.”

## Optional: a changing price without changing the conversation

Use the separately documented [MySQL → RDI procedure](RDI.md#install-and-operate) with a prepared operator. That procedure changes `VT-001`, a family offer, so use it before the couples pivot or quote that package explicitly as a separate example.

Ask for the current `VT-001` offer, have the operator update its price in MySQL and verify propagation, then ask for that offer again. The second quote should read the new Context Retriever value. The old chat card is a historical result and does not automatically update in place.

The deployment record in [RDI.md](RDI.md#current-state) documents a verified MySQL price change to $5,790 and restoration to $5,890, seen in Redis and Context Retriever. Rehearse the current environment before claiming a live result. Restore the starting price after the example; never substitute a direct Redis write for the MySQL/RDI path.

## Optional: reuse a safe policy answer

Click **Package inclusions**, then click it again after completion. If necessary, **Reset demo cache** first starts a new application cache scope; it does not flush the entire shared LangCache service.

Expected on an eligible routed request: the first answer uses LangCache lookup and Gemini policy generation, while a later successful hit reuses the response without a Gemini generation step. Show **HIT** and the actual trace. A repeated prompt is the reliable first demonstration; a paraphrase is subject to routing and similarity matching.

Personalized and current-offer requests bypass LangCache. The semantic router is a conservative cache-eligibility mechanism in this demo; it is not an out-of-domain safety blocker.

## Close with the member outcome

> “Alex explored value for the household, changed the trip, and came back without losing the shortlist or decisions. Preferences, trip state, and current commercial data each had a clear role. The advisor draft brings those together.”

Reduced repetition and better advisor continuity are the demonstrated experience goals. Conversion lift, handling-time savings, and ROI remain hypotheses for a customer pilot, not measured outcomes of this demo.
