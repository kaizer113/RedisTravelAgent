# VALUE TRAVEL Data Studio

Open [Data Studio](http://34.21.122.27:8080/studio), or use the **Data Studio** link
from the travel page. Enter the presenter key provided with the deployment. It is
kept in browser session storage and sent in a request header, never in the URL.
Use **Lock** when finished. This demo is currently served over HTTP; use a trusted
network or an SSH tunnel when presenting with the unlock key.

## Present the replication loop

1. Unlock the page and wait for MySQL and Redis to load.
2. Change a row's price or room count inline and save it. Other fields can be edited
   in the row details. The source change goes only to MySQL.
3. Watch the independently read Redis value converge. Polling is an observation of
   replication, not a measurement of RDI's internal latency; reads aren't atomic.
4. Check the offer through **Context Retriever** to show the agent's governed data path.
5. Insert a new demo offer, then verify its Redis copy. Delete that new offer and
   watch it disappear from Redis. Record absence is the delete evidence; a failed
   Context Retriever call alone does not prove a successful delete.
6. Restore the demo when finished. This replaces the table's contents with the 18
   baseline offers, including their original prices, and deletes inserted demo rows.
   Restore also writes only MySQL; RDI propagates the resulting changes.

New rows demonstrate CDC and Context Retriever ingestion. The chat's discovery
catalog is a separately seeded vector index, so inserting an arbitrary new offer
here does not automatically make a new package searchable in the travel assistant.
Deleting a catalog offer can make a chat quote unavailable until it is restored.
Earlier chat cards are historical results and do not update automatically.

## Access and operation

The backend uses a separate `value_travel_editor` MySQL account with SELECT, INSERT,
UPDATE and DELETE rights only on `value_travel.offers`. It does not use the root or
CDC account. `STUDIO_KEY` and `STUDIO_MYSQL_PASSWORD` are runtime secrets; no database
credential reaches the browser. Without configuration the API stays disabled.

All Studio API operations require the presenter key. Updates and deletes carry the
source row's `updated_at` version; conflicting edits return 409 instead of overwriting
someone else's change. Monetary values, IDs and other fields are validated, and all
SQL values use parameterized queries. Redis and Context Retriever access in this
module is read-only. The displayed table is capped at 500 rows for this small demo.

Configuration names are in `.env.example`. The app reaches the MySQL container over
the private Docker network; RDI reaches the separately published private VM port.
This is a shared synthetic demo editor, not customer identity or production RBAC.
