# VALUE TRAVEL Data Studio

Open [Data Studio](http://34.21.122.27:8080/studio), or use the **Data Studio** link
from the travel page. Enter the presenter key provided with the deployment. It is
kept in browser session storage and sent in a request header, never in the URL.
Use **Lock** when finished. This demo is currently served over HTTP; use a trusted
network or an SSH tunnel when presenting with the unlock key.

## Present the replication loop

1. Unlock the page and wait for SQL Server and Redis to load. The table shows six offers
   per page; Previous/Next reaches the remaining offers. Summary counts cover all
   offers, which also supply live prices to the travel concierge.
2. Change a row's price or available room count inline and save it. Room capacity and other fields can be edited
   in the row details. The source change goes only to SQL Server.
3. Watch the independently read Redis value converge. Polling is an observation of
   replication, not a measurement of RDI's internal latency; reads aren't atomic.
4. Check the offer through **Context Retriever** to show the agent's governed data path.
5. Insert a new demo offer, then verify its Redis copy. Delete that new offer and
   watch it disappear from Redis. Record absence is the delete evidence; a failed
   Context Retriever call alone does not prove a successful delete.
6. Restore the demo when finished. This replaces the table's contents with the 18
   baseline offers, including their original prices, and deletes inserted demo rows.
   Restore also writes only SQL Server; RDI propagates the resulting changes.

New rows demonstrate CDC and Context Retriever ingestion. The chat's discovery
catalog is a separately seeded vector index, so inserting an arbitrary new offer
here does not automatically make a new package searchable in the travel assistant.
Deleting a catalog offer can make a chat quote unavailable until it is restored.
Earlier chat cards are historical results and do not update automatically.

## Capacity and the RDI calculation

**Room capacity** is the number of people accommodated by the offer (1–20), separate
from available room inventory. Inspect shows the source capacity and the read-only
**Average price per person**, stored as `average_price_per_person` in Redis.
RDI computes `ROUND(total_price / room_capacity, 2)`; the field does not exist in
SQL Server and cannot be submitted through the editor. The estimate divides the whole
package total by capacity, not by nights or available rooms.

The refresh bar above **Observed state** fills over one second between reads and
shows **Refreshing** while a request is in flight. It pauses when auto-refresh is
off, the tab is hidden, or the Studio is locked. Requests do not overlap. A match
compares all ten source fields and verifies the RDI-derived value; a missing or
incorrect derived value is not a match.

## Access and operation

The backend uses a separate `value_travel_editor` SQL Server account with SELECT, INSERT,
UPDATE and DELETE rights only on `value_travel.dbo.offers`. It does not use the `sa` or
CDC account. `STUDIO_KEY` and `STUDIO_SQLSERVER_PASSWORD` are runtime secrets; no database
credential reaches the browser. Without configuration the API stays disabled.

All Studio API operations require the presenter key. Updates and deletes carry the
source row's `updated_at` version; conflicting edits return 409 instead of overwriting
someone else's change. Studio maintains this timestamp with `SYSUTCDATETIME()`;
manual SQL updates must also advance `updated_at` to preserve that conflict guard.
Monetary values, IDs and other fields are validated, and all
SQL values use parameterized queries. Redis and Context Retriever access in this
module is read-only. The displayed table is capped at 500 rows for this small demo.

Configuration names are in `.env.example`. The app reaches the SQL Server container over
the private Docker network; RDI reaches the separately published private VM port.
This is a shared synthetic demo editor, not customer identity or production RBAC.
