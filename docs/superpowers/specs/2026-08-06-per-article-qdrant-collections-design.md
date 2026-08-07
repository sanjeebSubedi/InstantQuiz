# Design: Per-Article Qdrant Collections with Reuse

Date: 2026-08-06

## Context

The pipeline embeds an article's chunks into a single hardcoded Qdrant
collection (`Quiz-App-Dev-Collection`) on every run. `store_embeddings` calls
`create_collection` unconditionally, and point IDs are the chunk index. On a
second run the collection already exists, so `create_collection` errors, and
distinct articles collide on the same IDs. The fix chosen is **Option B:
per-article collections with reuse**.

## Goal

Give each Wikipedia article its own Qdrant collection (`quiz_app-<slug>`).
When an article is already indexed, reuse its existing collection instead of
re-embedding. Re-fetches the article source on every run (no source caching).

## Decisions (confirmed with user)

- **Re-run behavior:** re-fetch + parse + chunk + build outline every run; skip
  embedding only when the article collection already exists.
- **Collection naming:** prefixed slug, `f"{QDRANT_COLLECTION_PREFIX}-{slug}"`
  (e.g. `quiz_app-linux`). The slug helper (`slugify_title`) lives next to the
  orchestration that derives the collection name (`agents/run_pipeline.py`).
- **Reuse gate:** `collection_exists(slug)` is the sole gate. No freshness /
  re-embed-if-missing guard.
- **Out of scope:** no migration or deletion of the legacy
  `Quiz-App-Dev-Collection`.
- Notes: the outline is built ephemerally for the planner only; it is not
  persisted (the SQLite outline store was removed from the codebase).

## Data flow

1. resolve topic -> article title; parse sections; build chunks (always).
2. compute collection name = `f"{PREFIX}-{slugify_title(article_title)}"`.
3. if `not qdrant.collection_exists(name)`: `store_embeddings(name, chunks)`.
   else: log reuse, skip embedding.
4. build outline for the planner (not persisted).
5. plan_quiz -> retrieve_chunks(name) -> generate_quiz (unchanged).

## Components / responsibilities

- **agent/** - orchestration: computes the slug collection name and gates
  embedding behind existence.
- **ingestion/embed.py** - `store_embeddings` becomes idempotent: returns early
  if the collection already exists, matching Qdrant's documented
  `if not exists: create` pattern.
- **retrieval/retriever.py** - guards a breadcrumb with no matching point:
  logs a warning and skips the item instead of raising on an empty scroll.

## Safety

Because reuse trusts collection existence only, a stale article could yield
mismatched context. `retrieve_chunks` therefore degrades gracefully (warn +
skip) instead of crashing. No re-embedding is performed to reconcile staleness.