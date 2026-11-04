# SQL evidence: Postgres-wire tools and LLM query correctness

Status: pre-registration. Written before anything ran. Nothing in this directory has been executed yet.

Purpose: ArcadeData may be asked to add an ANSI SQL core (JOINs, `information_schema`) next to Cypher. This experiment collects the numbers such a proposal needs. Evidence for and against counts equally, and every arm below is reported whatever it shows. The results are posted when collected, as input for a future plan. No release gate applies.

ArcadeDB version: the latest stable release, 26.10.2 (released 2026-10-15; the official `arcadedata/arcadedb:26.10.2` image for part B, `dbbench:arcadedb-26.10.2`, the campaign's embedded image of that release, for part C). Client images are the latest releases on 2026-11-04. `ARCADEDB_VERSION` selects the tag and every output records the engine version it read from the running engine.

## Questions

- B. Which Postgres-wire clients and tools work against ArcadeDB's Postgres plugin, step by step: connect, list tables, list columns, simple SELECT, parameterized WHERE, JOIN, GROUP BY?
- C1. How often does an LLM, given the schema and one question, write a query that returns the correct result, in four languages: ANSI SQL, openCypher (ArcadeDB), SQL/PGQ (DuckDB with DuckPGQ) and ArcadeDB SQL? And does a short reference card for ArcadeDB SQL in the prompt change the ArcadeDB SQL rate (the fifth arm)?
- C2. How does that rate move with question category (single type, one join, multi join, graph pattern)?

## Part B: Postgres-wire tool matrix (`tool_matrix.sh`)

One ArcadeDB server with the Postgres plugin (`-Darcadedb.server.plugins=Postgres:com.arcadedb.postgres.PostgresProtocolPlugin`), loaded with a tiny dataset: vertex types `Person` (300) and `City` (20), edge type `LIVES_IN` (300), and `Person.city_id` repeated as a plain property so a relational JOIN has something to join on. Clients, one at a time, all images pinned by tag (the tags are defaults, overridable by environment variable, and are recorded with their digests in `images.txt`):

| client | how | pin |
|---|---|---|
| psql | `postgres` image, scripts on stdin; `\dt` and `\d` are the list steps, `\bind` the parameter step | `postgres:18.6` |
| psycopg 3 | `uv run --with` | `psycopg[binary]==3.2.9` |
| SQLAlchemy 2 | Inspector reflection, Core select, bound parameter, join, group by | `sqlalchemy==2.0.41` (on psycopg 3) |
| pgJDBC | `DatabaseMetaData.getTables` and `getColumns`, then statements, in a JDK container | `postgresql-42.7.14.jar` on `eclipse-temurin:25-jdk`, jar sha256 recorded |
| Grafana | provisioned Postgres datasource, `/api/datasources/uid/<uid>/health`, then `/api/ds/query` | `grafana/grafana:13.3.0` |
| Metabase | setup API, add database, `sync_schema`, native queries through `/api/dataset` | `metabase/metabase:v0.65.2` |

Output: one JSON line per step, `{client, client_version, step, ok, error}` (an optional `note` marks a step that cannot use a server-side parameter, which is Grafana's parameter step). A step is `ok` only when it returns the expected content: the table list must contain `Person`, every query must return at least one row. A failing step does not stop the matrix; the error text is recorded as the evidence. The tag defaults were chosen as versions known to exist and are not claimed to be the newest; a bump is a new run reported next to this one.

Memory: `NEED_GB=6`, `JOB_MEM_GB=5` (server 2 GB, Grafana 1 GB, Metabase 3 GB, pgJDBC 1 GB, never more than the server plus one client at a time). Cores 14 and 15. Every container has a unique name and a cleanup trap; ports are drawn at random on loopback and checked free.

## Part C: LLM query generation

### Dataset

The campaign's LDBC SNB sf1 corpus (`~/bench-data/ldbc/sf1`, CsvCompositeMergeForeign, LongDateFormatter; see `ldbc_snb.py`), the smallest scale. A subset is loaded by `ldbc_subset.py`: 9,892 persons, cities, countries, forums (with moderator), tags, tag classes, the KNOWS projection (180,623 friendships, stored once from the smaller to the larger person id) and person interests. Years are derived from the epoch-millisecond fields. The messages (posts, comments) are not loaded.

Every engine loads the same rows. ArcadeDB gets vertex types per entity and six edge types (graph arms); DuckDB gets eight tables (SQL arm) and, for the SQL/PGQ arm, four more edge tables (`LocatedIn`, `PartOf`, `HasModerator`, `HasType`) and a property graph `g` over all of them. Property naming differs by paradigm on purpose (snake_case columns, camelCase graph properties); the schema text each arm sees is in `prompts/`.

### Arms

| arm | language | engine |
|---|---|---|
| `sql` | ANSI SQL | DuckDB 1.5.6 (`dbbench:duckdb`), a stand-in for an ANSI SQL core |
| `cypher` | openCypher | ArcadeDB 26.10.2 embedded |
| `pgq` | SQL/PGQ, `GRAPH_TABLE ... MATCH` | DuckDB 1.5.6 + DuckPGQ community extension (DECISIONS #103) |
| `arcadedb_sql` | ArcadeDB SQL | ArcadeDB 26.10.2 embedded |
| `arcadedb_sql_docs` | ArcadeDB SQL, prompt with a reference card | ArcadeDB 26.10.2 embedded (same engine, same reference rows as `arcadedb_sql`) |

The `arcadedb_sql_docs` arm exists because of the obvious objection that agents can simply read the docs. It uses the same questions, models, samples and request parameters as `arcadedb_sql`; only its prompt differs, by one added section: a reference card of about 1,000 words (`prompts/arcadedb_sql_docs.txt`, the `arcadedb_sql` text with the card placed before the question). The card is written in original wording on a toy schema (employees, departments, projects) that shares no names with the study's schema, and covers general syntax only: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT, aggregates, parameters, `LET` and subqueries, the traversal functions (`out()`, `in()`, `both()`, `outE()`, `inE()`, `expand()`), `MATCH` with `as:`, `where:` and `while:`, `TRAVERSE`, and the absence of `JOIN` with its usual substitutes. No example mirrors a question in `questions.yaml`. Every query on the card is executed against the pinned engine, on a toy dataset of 16 vertices and 22 edges, before the freeze (`card_check.py` with `card_examples.yaml`, run first in the gold smoke), and a failing example is fixed in the card and logged in `GOLD-LOG.md` before the first generation. It is a fair cheat sheet, not an answer key, and it is still a single prompt: no retrieval, no tool use, no repair loop, so it measures what a card in context buys, not what an agent with live access to the docs would do. This arm has no gold of its own: `score.py` runs its generations on the ArcadeDB engine as ArcadeDB SQL statements and scores them against the same reference rows as `arcadedb_sql`. It is reported next to `arcadedb_sql`, whatever it shows, including no difference or a worse rate.

The `sql` arm measures how well a model writes ANSI SQL, not what ArcadeDB would do with it. That is the point of the proposal's question, and also its limit: DuckDB's dialect is not the dialect an ArcadeDB SQL core would implement.

### Questions and gold

`questions.yaml`: 40 questions, 10 each of single type filter and aggregate (A01 to A10), one join (B01 to B10), multi join (C01 to C10) and graph pattern or traversal (D01 to D10). Each has a gold query per arm. Where the author could not write one the gold is `null` with a reason and a kind: `language` (the language cannot express it) or `author` (the author could not write it with confidence; not a claim about the language). Five ArcadeDB SQL golds are null, all of kind `author` (C03, C08, D04, D05, D08); none is of kind `language`. Those questions are still asked in that arm and scored against the language-independent reference rows, so a model that answers them is evidence that the language can.

Provenance: the SQL/PGQ triangle (D04) and 2-hop (D02) shapes and the Cypher triangle follow the campaign's graph lane (`l2_graph.py` `DuckpgqGraph`, `graph_common.py`). The campaign loads a persons-and-KNOWS projection and the LSQB message half, which have no names, tags or places, so every other gold is new. The campaign's cross-engine habit is kept: `gold_check.py` runs every gold on its engine and requires all golds of a question to return the same result as the ANSI SQL gold (columns by position, order-insensitive unless the question asks for an order, floats equal within 0.01 absolute or 1e-6 relative). A gold that errors or disagrees blocks the question. Golds may be corrected after `gold_check` and before the first generation; each correction is logged in `GOLD-LOG.md` with the check output that caused it. Questions whose reference is empty or a single zero are flagged as weak and may be replaced by the same rule, before the first generation only.

Known semantic traps, handled in the golds and stated in every schema text: KNOWS is stored once per friendship and is symmetric; Cypher applies relationship uniqueness inside one `MATCH` only, so golds that need one edge twice use separate `MATCH` clauses; SQL/PGQ walks may reuse an edge.

### Prompts

`prompts/<arm>.txt`: one zero-shot template per arm, schema description plus the question, ending with "Answer with the query only." No examples, no syntax hints beyond what the schema text states (the graph name `g` and the edge labels for SQL/PGQ). The one exception is `arcadedb_sql_docs`, which adds the reference card described under Arms. `{question}` is the only placeholder. The frozen set is `questions.yaml` and every file in `prompts/` (`sql.txt`, `cypher.txt`, `pgq.txt`, `arcadedb_sql.txt`, `arcadedb_sql_docs.txt`); `generate.py` records their sha256 in the run manifest and `score.py` refuses a run whose files no longer match.

### Models and sampling

Claude Sonnet 5.5 (`claude-sonnet-5-5`) and Claude Haiku 5.5 (`claude-haiku-5-5`), exact model IDs. 40 questions x 5 arms x 3 samples = 600 requests per model, 1,200 in all, sent as one Message Batch by `generate.py submit`. Pre-registered request parameters, identical for both models:

- `max_tokens=16000`
- `output_config={"effort": "medium"}`
- no `temperature`, `top_p` or `top_k` (non-default values are refused by these models, so the three samples differ through default sampling)
- no assistant prefill (refused)
- thinking left at the model default (adaptive)
- no server-side fallbacks: a fallback would answer with a different model and contaminate the measurement. A `stop_reason` of `refusal` or `max_tokens` is recorded and scored as a failed generation.

Auth is `anthropic.Anthropic()` reading `ANTHROPIC_API_KEY` from the environment only; set `ANTHROPIC_API_KEY` before `submit`. `generate.py collect <batch_id>` prints the status and exits when the batch has not ended, so it is run again later; results are keyed by `custom_id` (`r0000` to `r1199`, mapped to model, arm, question and sample in the manifest), never by position.

Cost estimate (not a measurement): about 450 input tokens per request (about 1,950 for the `arcadedb_sql_docs` arm, whose card adds roughly 1,500) and 1,500 to 3,000 output tokens including adaptive thinking, at list prices of 2 and 10 USD per million tokens for Sonnet 5.5 and 0.10 and 0.50 for Haiku 5.5, both halved by the Batches API: roughly 5 USD (1,500 output tokens) to 10 USD (3,000), the same method as before applied to 600 requests per model. The card adds about 0.2 USD. `collect` prints the actual cost from the returned usage.

Generations format, one JSON object per line in `generations.jsonl`: `{model, arm, question_id, sample, query, stop_reason, usage, result_type, error}`. `query` is the concatenated text blocks exactly as returned.

### Extraction and scoring

Extraction (pre-registered, nothing else is done to the text): take the text blocks, strip one surrounding markdown code fence if present, trim whitespace.

`score.py` runs each extracted query on its arm's engine (one read-only statement per query; anything else is rejected before running; 60 s timeout) and records per generation:

- `parse_ok`: no parse or syntax failure reported by the engine (a heuristic on the error text, applied identically to every arm), and the statement was accepted for running;
- `exec_ok`: the query ran to completion;
- `correct`: `exec_ok` and the result equals the reference rows under the comparison rule above. Columns are compared by position, so a model that returns the columns in another order than the question states is wrong.

A failed generation (not succeeded, `refusal`, `max_tokens`, empty text) has all three false. A question enters the scored set only when every non-null gold of that question verified in `gold_check`; the others are listed as unscored.

Report: per model, per arm, per category and overall: `n`, parse rate, execution rate and correct rate with a 95% Wilson interval. The three samples of one question are not independent, so the table also gives pass@3 (a question counts when any sample is correct) with its own Wilson interval over questions. The first table shows every arm for both models, including arms that did badly.

### Reporting rule

Every arm and both models are reported. Prompts and questions are frozen before the first generation. Any change after that, to a prompt, a question, a parameter or a model, is a new run in a new run directory, reported next to the first and never replacing it. A re-run of unchanged inputs is also reported next to the first.

### Threats to validity

- The author wrote all four golds for each question; a gold error that all engines share would pass the cross-check. The differential catches disagreement, not shared misreading.
- The `sql` arm runs on DuckDB. DuckPGQ is a research-grade extension and its parser limits (for example no parameters, DECISIONS #103) bound what the `pgq` arm can be asked.
- Schema text and naming differ by paradigm (column names, edge-table names in the PGQ arm), so an arm difference mixes language and schema presentation.
- Zero-shot only; no retrieval, no repair loop, no examples. Questions are English paraphrases of the gold, written by the same author.
- A model that has seen LDBC SNB queries in training is helped on every arm, probably unevenly.
- sf1 is small; result correctness, not speed, is the measurement, and timeouts are rare but counted as execution failures.

## Files

| file | role |
|---|---|
| `questions.yaml` | the 40 questions and their golds (frozen) |
| `prompts/*.txt` | one template per arm, including `arcadedb_sql_docs.txt` (frozen) |
| `ldbc_subset.py`, `engine_runner.py`, `dockerrun.py` | loader, in-container runner for DuckDB and ArcadeDB, container launcher |
| `resultcmp.py` | comparison rule, extraction rule, Wilson interval, frozen hashes |
| `gold_check.py` | runs every gold, compares across languages, writes `gold_report.*` and `gold_rows.json` |
| `card_examples.yaml`, `card_check.py` | every query on the `arcadedb_sql_docs` card with its toy dataset and expected outcome; the checker runs them on the pinned engine and fails when the card and the examples differ |
| `generate.py` | `submit` and `collect` through the Batches API (`--dry-run` builds and writes the requests without calling the API) |
| `score.py` | executes and scores the generations, writes `scored.jsonl`, `table.json`, `table.md` |
| `tool_matrix.sh`, `pgsteps.py`, `seed_pgwire.py`, `probe_*.py`, `PgJdbcProbe.java`, `matrix_table.py` | part B |
| `MEASURE-LINES.txt` | queue lines for the first runs: gold smoke (card check, then gold check), gold check, tool matrix |

Outputs go under `/home/tk/build-scratch/sql-evidence/`. The scripts do not write elsewhere.
