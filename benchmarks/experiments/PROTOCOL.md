# PROTOCOL

How this benchmark harness must be operated. It is the single source for rules
that used to live in code comments, commit messages, task notes and one person's
head, and every rule carries a tag saying whether anything checks it (**GATE**
with the check name, or **REMEMBERED**). The tags exist because remembering has
failed here at least four separate times: 20 canonical rows were still on
26.8.1.dev0/.dev3 after a whole re-measure campaign that was supposed to put
everything on a stable release; three fairness defects were found in one
afternoon on 2026-07-31 and all three favored us; a queue script that omitted
`BENCH_SPARSE_SOURCE` wrote 94 sparse rows against a synthetic corpus with no
ground truth; and the paper asserted N=5 globally while printing rows built from
three and four passes. REMEMBERED means nothing will catch the next violation.

Companion documents: FAIRNESS.md (F1-F9 and their incident histories),
PUBLISHING.md (page policy), READING-RESULTS.md (how to read results/ without
repeating a stale note), CAMPAIGN.md (how a campaign is run; the July 2026
record it replaced is in git history). The canonical-row definition is section 1
below.

---

## 1. What may reach a table

The admission filter is `make_paper_tables.load_canonical()`. Every test below
runs **before** the dedupe, so a bad row can never shadow a good one by being
newer. A row that reaches a cell through an overlay directory never passes the
filter at all; the tags below say where that matters.

- `rc == 0`. **GATE** `load_canonical`
- Scale is in `PAPER_SCALES` for that lane. Retired and exploratory tiers cannot reach a cell. **GATE** `load_canonical`
- `cpuset` is `"0-11"` or unrecorded. A partial cpuset is a parallel sweep shard, and the dedupe keys on `ts_utc` with no idea what a cpuset is. **GATE** `load_canonical` + `fairness_check.check_cpuset` (F1/F2, vacuous downstream of the loader)
- `engine_version` matches no `dev\d|SNAPSHOT`. Policy is one stable release per number; 20 rows survived a campaign on dev builds. **GATE** `load_canonical._DEV_RE` for T2, T3 and the comparator rows, re-applied in `claims_check.ingest_ab` and `_e4_decomp`; **GATE (report only)** for T5's time-series row, which warns on stderr and writes the row anyway; **REMEMBERED** for T5 dense, which never passes through the loader
- l3s rows carry `recall_at_10`. The synthetic sparse generator ships no ground truth, and at tiny and small both corpora hold 100k/1M docs, so nothing else tells them apart. **GATE** `load_canonical`
- Elasticsearch rows carry `server_heap` equal to `heap`. `heap` records the request; ES ran a hardcoded 4g at tiny, small and medium while comparators scaled 4g/8g/16g. **GATE** `load_canonical` + `runner.observe_server`
- Elasticsearch rows carry `es_prune is False`. ES 9.1+ prunes by default on thresholds tuned for ELSERv2; on our SPLADE corpus that is recall 0.725-0.929 against 0.991-0.9985. **GATE** `load_canonical`
- A served row names a `d.d.d` version or carries an `@sha256` digest. `server:latest`, `server` and `unknown (PackageNotFoundError)` are not versions and the pre-release guard cannot see through them. **GATE** `load_canonical` for `runs.jsonl` rows; **REMEMBERED** for the dense overlay, which publishes `ArcadeDB (srv, fp32)` from records carrying `unknown (PackageNotFoundError)` and no `server_image_ref`
- A witness field must be present **and** equal. Three rows had `heap=None` and `server_heap=None`, which bare equality passes by matching nothing against nothing. **GATE** `load_canonical`
- Dedupe key is `(lane, scale, n_docs, workload, backend, gav is not False, rep)`, latest `ts_utc`, never `run_id`. Pre-2026-07-21 run_ids were not scale-qualified; without the `gav` term the no-view ablation overwrites T3 with numbers 2-7x worse. **GATE** `load_canonical`
- One released engine line per table. Delete preference cascades, never reorder them: T4's ArcadeDB row came from a six-deep dev-overlay cascade, and f8 divided a pre-fix 165 ms embedded number by a re-measured 13.3 ms server one and made the server look 12x faster. **GATE** T4 refusal in `make_paper_tables` and five of f8's six bars in `make_paper_figures`; **REMEMBERED** for f8's dense bar, whose `_dense_multipass` source reads no version field, and for every other table (F5)
- Lane scripts publish; bespoke drivers investigate. Both known protocol violations were bespoke-driver rows promoted to cells, and T5's dense half and native time-series row are bespoke-driver rows now. **GATE** `fairness_check.report_producers` (F6b) for `runs.jsonl` lanes, which sees no overlay record and knows neither `l3d_mp` nor `l4n`; **REMEMBERED** for every overlay-fed cell
- Every cell is N=5, or its shortfall is disclosed in `EXPECTED` and in the caption, and the disclosure is deleted when the shortfall is fixed. **GATE** `provenance_check.caption_n` for T2, T3, T4 and T5's time-series block; **REMEMBERED** for T5's dense half, which renders through a local `fmt()` the check never sees, and for the deletion half, which `if ns == {5}: continue` short-circuits before the `EXPECTED` lookup
- Never publish a scale where comparators have rows and we do not; print what was withheld and why at export time. **GATE** withheld-scale guard in `export_web`
- Every artifact a paper cites lives in this repository, and the superseded run is not left where it can be compared against. **GATE (report only)** `provenance_check.FEEDS`: an empty feed prints "(no result files)" and counts nothing, and the superseded overlays (`dense_mp_2681`, `e4decomp`, `e4decomp_2681`) are listed as unmapped and left in place
- Every overlay directory and top-level result file feeding a table records run conditions and a real version; "feeds a table" means "is opened by make_paper_tables". **GATE** `run_conditions`, `lane_files` and `_is_real_version` for the two lane files; **REMEMBERED** for the overlay directories T4 and T5 print, whose audit accepts any non-empty string (25 of 45 dense files carry only a placeholder)
- A SNAPSHOT build's commit date must not predate a landmark commit. **GATE** `provenance_check.LANDMARKS`

## 2. How a cell is measured

- Published latency, throughput, percentile and memory cells run serial, one at a time, on the full cpuset. Permutation protects a ratio; it cannot restore an absolute level or a tail that never happened. **GATE** `runner.py` paper tier refuses `workers != 1`
- Reps per build, warmup count, settle step and query set are properties of the lane, fixed before a driver is written. T5 dense gave ArcadeDB 1 build + 5 passes against comparators' 5 builds + 1 pass, worth 4.0-6.1x. **REMEMBERED**
- Never print one-build-many-passes beside per-rep-builds in one table: the two shapes price different work, and the table does not show which shape a row has. **GATE (report only)** `fairness_check.check_protocol_overlays` (F4)
- Warm queries must be disjoint from cold ones. Replaying one set cannot separate residency from recall of the same queries. **GATE** `sparse_multipass_driver` protocol for l3s, pinned in `claims_check` as the upper bound at small and both bounds at medium; **REMEMBERED** and knowingly violated for l3d, whose driver replays the `test` set on every pass after 20 untimed warmups drawn from it
- Each engine gets its own vendor-documented settle step, timed inside build so the build is timed to a queryable index, and none is skipped. **REMEMBERED**
- Ingest timers must stop on the same completion semantics across a lane, or the rates price different work. Currently violated in L4: QuestDB's WAL-apply poll is inside its timer, ArcadeDB's stops at `wait_completion()`, and the 4.3x headline rests on the difference. **REMEMBERED**
- Observe conditions from the daemon and the engine; never record what the launcher meant to do. A heap that disagrees with the request fails the cell. **GATE** `runner.observe_server`
- Overlay drivers sample their own peak memory from inside the container, started before the build. `run_conditions` records the ceiling, not the use. **GATE** `bench_common.SelfMemorySampler`
- The cgroup memory reading is valid only inside a bench container; record `host` so a reader knows which they have. **REMEMBERED**
- Time every phase of a lane and record the sum beside the runner's wall clock, so the residual is visible. l3s recorded only build_s while 85% of an 8.84M cell was unaccounted for. **GATE** `phases_accounted_s` in `l3_sparse.py`
- On-disk size is the writable layer plus every declared volume, destinations read from the daemon, and it must settle (two readings within 1%, else `disk_settled=False` with both). PostgreSQL's SizeRw stayed at 20480 bytes with 1017.5 MiB in its volume. **GATE** `runner.container_disk`
- Record IO alongside disk, taking the last `io.stat` reading: the counters are cumulative, so only the last one is the run's total. **GATE** `CgroupSampler`
- A silently killed cell must not read as success. Thirty OOM-killed TPC-H cells exited 0 with empty error strings. **GATE** OOM inspect + non-zero exit in `runner.py`
- Prefer the loud failure: when a lane can measure something other than what was asked for, make it abort rather than annotate. The loud crash cost 80 cells; the quiet wrong corpus cost 94 rows and nearly a paper. **REMEMBERED**
- A server adapter that sends vectors as text must round-trip float32 exactly (`%.9f`, not `%.6f`), because float32 needs nine significant decimal digits to survive the trip. **REMEMBERED**: `precision_check.py` is a synthetic experiment that reads no artifact, always exits 0, and nothing invokes
- Never let a result object's Python type stand in for the finding, and abort an arm whose control operations moved nothing. E2 stamped every single-engine backend atomic by construction. **GATE** validity guard in `e2_hybrid.py`
- Pin trial counts and denominators, not only outcomes. "5 of 5" bounds the failure rate only below ~45%; 200 injections bound it at ~1.5%. **GATE** `claims_check.e2_atomicity`, `page_check` count assertions
- Re-profile on the release rather than assuming a dev build's profile transfers (substrate share 5.05% on 26.8.1 against 3.49% on dev23), and never add overlapping percentages. **REMEMBERED**
- Do not add a new recorded field to a published driver until its lane is re-run; the driver's own frozen artifacts will not have the field. **GATE** `provenance_check.check_schema_homogeneity`, which compares the measured fields of every row in a (lane, scale, workload, backend) family and reports any field some rows carry and their siblings do not. Promoted from REMEMBERED on 2026-08-15 after the rule failed three times in one hour

## 3. How a comparison is kept fair

- Every container in a published cell gets the full 0-11 cpuset; a client/server pair shares that one cpuset rather than each getting its own cores. CPU competition stays inside the deployment under test. **GATE** `fairness_check.check_cpuset` (F1) + the loader filter, for the client or embedded container only; **REMEMBERED** for the server side of a pair: `observe_server` records `server_cpuset` and the observed cap, and no consumer reads either
- Every backend at a (lane, scale) gets the same `--memory`/`--memory-swap` and, for JVM engines, the same heap. Raising a resource for one engine obliges a re-measure of every engine at that tier: DEEP-10M went 28g/16g to 36g/24g and only ArcadeDB was re-measured. **GATE** `fairness_check.check_envelope` (F3)
- Normalize a served topology before comparing: total is `srv_cap / mem_split`, never client + server. Addition read 1.75x the envelope and failed five compliant tiers. **GATE** `_total_envelope` for the arithmetic; **REMEMBERED** for the constant, already stale: the runner now stamps `mem_split="full+client"` (section 7), which `float()` rejects, so the `SERVER_MEM_FRACTION_DEFAULT = 0.75` fallback will report 1.33x the true envelope on the first cell run under it
- Do not compare a setting to its own absence: heaps are compared only among engines that have one, and a missing heap on an ArcadeDB row is reported as a recording gap. **GATE** `check_envelope`
- Every dense backend at a scale gets the same effective base-layer degree, read in each engine's own unit (ArcadeDB maxConnections as-is, hnswlib-family M doubled at layer 0). A row recording no degree FAILS; sqlite-vec is exempt as an exact scan. Stamp the matched parameter from one shared function, called from both the lane and its bespoke driver, so the two cannot diverge. **GATE** `fairness_check.check_degree` (F7) + `l3d_dense.degree_stamp(backend)`
- Check the rows the table prints. Where a table reads an overlay, the fairness checks read that overlay too. **GATE** `_dense_rows()` swap in F3/F7
- Fit every engine's thread pools to the cpuset via `sched_getaffinity`; `os.cpu_count()`, `nproc --all` and `/proc/cpuinfo` in an adapter are the bug. DuckDB ran threads=20 inside a 12-CPU cpuset, ~1.7x oversubscribed. **REMEMBERED** (F6, and three DuckDB lanes are still unfixed)
- Verify the shared cpuset equalizes **use**, not merely the resource, before comparing p50s. Measured 2026-08-03: no embedded dense engine parallelizes a single query; LanceDB is ~20% slower on 12 CPUs than on 1. **REMEMBERED** (F1 evidence)
- When a campaign re-measures one engine and carries the others forward, re-run one untouched comparator as a control and record its old-vs-new delta beside the table it licenses. If the control does not reproduce, the tier is re-measured in full. F1-F8 constrain a cell's configuration and none constrains when it ran. **REMEMBERED** (F9)
- Measure every row in one table on the same engine release as the row beside it, so a version difference cannot be read as a configuration difference. **GATE** T4 and f8 only; **REMEMBERED** elsewhere (F5)
- Never divide a number from one experiment by a number from another and call the quotient a cost. The ten-tag schema cost was published as 23x by crossing two campaigns; within one probe it is 1.97x. **GATE** `claims_check._tentag` and the dense cold/warm boundary note
- Equalize a comparator's default only where leaving it makes the comparison apples-to-oranges (the four categories in section 7), and never relax a durability default under the same arm name: the arm then measures a system its name does not describe. **REMEMBERED**
- A fix that costs the rival a round-trip goes only in the untimed path, or the round-trip is charged to their latency (E2's counter mirror runs in the atomicity trial, not the latency path). **REMEMBERED**
- State the consequence of the memory contract that cuts against us: the JVM heap lives inside the container cap, so ArcadeDB's 24 GiB heap leaves ~12 GiB for JVM overhead and page cache while non-JVM comparators have all 36 GiB. Equal caps are what we can enforce. **REMEMBERED** (stated in the paper's protocol section)
- Keep `fairness_check.DISCLOSED` empty unless an override is live, and delete a disclosure the moment the asymmetry it describes is fixed. A disclosure that outlives its subject invites a reviewer to distrust the rest. **REMEMBERED**

## 4. What may be said about a number

- Never recompute a claim your own way: `import make_paper_tables` and ask `load_canonical()`. A hand-rolled median produced three false findings and replaced a correct number with an incorrect one. **GATE** `claims_check`
- Pin prose to a generated table cell (prose to table to data), address cells by meaning (system, tier, metric) and never by column index, and parse the k/M suffixes when reading a cell back. Restructuring T4 to three rows per system silently made two claims read a recall out of a p50 slot. **GATE** `claims_check.sparse_cell`, `cell()`
- Verify separately that the committed tables regenerate byte-identically from the data (generate into a temp dir and diff). Otherwise every cell-pinned claim passes against a stale file. **GATE** `claims_check --regen`
- Tolerance is the number's own printed rounding, half a unit in the last digit, so a wider window cannot pass a number the table no longer prints. **GATE** `page_check._check_prose`, which derives it as `0.5 * 10 ** -decimals`; **REMEMBERED** for `claims_check`, where tolerance is a hand-typed third tuple element and several are an order of magnitude or more past half a unit
- A selector that returns no rows, or raises, is a FAILURE, never a skip: it is otherwise green while pinning nothing. **GATE** `claims_check` NODATA/ERROR paths
- Pin ranks as well as values, and fail loudly when a name stops resolving; never let a lookup fall back to a sentinel. Relabeling one dense arm left four rank claims computing over 8 rows while their text said 9, green by luck. **GATE** `_dense_rank` raises on unresolved `DENSE_ROWS`
- Pin a ratio by recomputing it from its operands, and pin the endpoints of any range stated as one summary number. Both operands can be right and the quotient stale (2.4x against a true 3.7x); "within 15%" was 8% and 22%. **GATE** `claims_check` ratio selectors
- State every ratio in one direction, ours over theirs, even where flipping it would read as a win, so a regression moves the whole group the same way. **GATE** `mem.ratio.neo4j` pinned at 0.62
- Pin a "beats both" claim to the comparator we lose to. LadybugDB loads SF10 in 3.5 s against our 26.2. **GATE** `claims_check` L2 block
- When one system contributes two arms, pin each arm separately. "0.52 ms beats both specialists" was the document path in a paragraph about the native engine, which is 4.16 ms and loses. **GATE** `claims_check` l4 arm claims
- Select on `n_docs` wherever one scale name covers two corpora, and count reps for one arm, because an N claim describes a cell and not a pooled lane. **GATE** `_sparse_build`, `_sparse_reps`
- Exclude the GAV ablation (`gav is False`) from every ordinary selector; the ablation gets its own reader. Pooling gave 841.6 ms, the midpoint of two arms and a description of neither. **GATE** `claims_check._sel`
- Read one source per measurement. No fallback cascade across engine lines or overlay generations: the arms use different last-point keys, so a fallback changes the quantity as well as the engine. **GATE** `ts_arm`
- A number that appears in no table needs its own claim, or it has no auditor. **GATE** `gav_ablation`, `ingest_ab`, `e3`, `_sparse_arm`, `l2_peak_anon_gib`
- Leave an unsourced prose number pinned and FAILING rather than deleting the claim or nudging the number. **REMEMBERED**: the CLAIMS comment block enforces nothing, and the one deliberately failing pin (`l1.ingest.batched_UNSOURCED`) has been replaced by three passing ones
- Pin a known confound as a checkable quantity instead of publishing the ratio it corrupts. Never publish a cross-engine memory ratio computed from anonymous memory: anon is 26% of PostgreSQL's peak and 97.5% of ArcadeDB's. **GATE** `anon_share`, `anon_client_share`
- Split a served cell's memory into client and server before comparing with an embedded engine. The PostgreSQL cell a reader compares against ArcadeDB's 12.7 GiB is 88% our own Python driver on L1 and 99.6% on TPC-H. **GATE** `mem.postgres.client_share`
- Reject a throughput from a run that wrote the wrong number of rows. **GATE** `ingest_ab` honors `count_ok`
- Aggregate a decomposition over all matched released runs, and pin the fact that a term sits below resolution rather than quoting one tidy run. **GATE** `_e4_decomp`
- Pin a binding-overhead ratio by the exact pair of arms it compares. Swapping P-raw-call for P-SQL moves the published vector ratio 1.28 to 1.71 with every gate green. **GATE** `pyb_ratio`
- Sweep the paper at every freeze for ratios and unit-bearing measurements that no claim pins, so a new number cannot reach a freeze without an auditor. **GATE (report only)** `claims_check --sweep`
- Every figure the paper `\includegraphics` must be newer than the newest generated table, and no figure may exist that no paper cites: a stale figure plots numbers the tables no longer hold, and an orphan is what a later citation reaches for. **GATE** `figures_fresh`, `_check_no_orphan_figures`
- Both sides of a plotted ratio come from one artifact at one pass selection. f4's dense bar compared our warm p50 against Qdrant's cold one (0.15x cold/cold, 1.37x warm/warm). **GATE** `_check_f4_protocol`
- Enforce a comparator-selection rule in code, not on the axis: the real rule is "fastest engine at recall at least ours". **GATE** `_check_f4_comparators`
- Read labels back out of the rendered PDF. A figure can be wrong while every data check is right ("...log sca"). **GATE** `_check_labels_intact` + `EXPECT_IN_PDF`
- A figure label must carry its own valence and must not borrow another experiment's vocabulary. f7 printed "torn state 5/5" and "atomic 5/5" as identical fractions with opposite verdicts. **REMEMBERED**
- A caption's asserted engine version must appear in the versions its feeding overlays record; distinguish BAD (data contradicts) from UNVERIFIABLE (data cannot say). A caption is a provenance claim. **GATE** `provenance_check.caption_versions`
- Flag a table whose rows come from more than one engine version (the one-release-per-table rule is otherwise unchecked outside T4 and f8), and name every driver that writes a hardcoded version literal about itself. **GATE (report only)** `provenance_check`
- The page may show fewer numbers than the paper, never a different one: a page cell covering a claimed measurement must agree within that claim's tolerance, a STALE mapping fails, an ABSENT cell fails, and a pin for a deliberately dropped table is deleted rather than left reporting ABSENT. **GATE** `page_check.MAPPING`; deletion is **REMEMBERED**
- Key page pins on the raw harness backend name and resolve through the exporter's own `display_name()`, literal key first. A rename once turned all nine mapped cells ABSENT at once. **GATE** `page_check._resolve`
- Pin every hand-typed number in the page's prose to a named table column, keep cold and warm entries listed apart, and treat an unmatched regex or an unparseable capture as a failure. One caption sentence mixed a runs_paper.csv row with the dense overlay. **GATE** `page_check.PROSE`
- Check the page's atomicity counts against the artifact and assert the trial count alongside every zero-torn claim, because zero is what a broken read also produces. **GATE** `_check_page_atomicity`
- After copying the export to the site, verify the served file is byte-identical to the one the gates read. A planted wrong value left all four gates green. **GATE** `refresh_web_page`
- Read every published label from the thing it describes: deployment from the backend topology, version from the image tag, scale from an explicit map, dense precision from the adapter. `"server" in backend` told readers five served engines run in-process. **GATE** `export_web` topology lookup and `SCALE_LABELS` for l1/l2/l3 deployment, scale and label presence; **REMEMBERED** for the adapter half, since `DENSE_PRECISION` is a hand-transcribed dict nothing compares against `l3d_dense.py`, and for l4, which bypasses `deployment_of()` for a hardcoded `L4_DEPLOYMENT`
- Give every arm a display name; a raw backend id names a harness arm, not a system. **GATE** `display_name()`
- A table may have more than one source, and the source link printed under it must hold the rows above it. **REMEMBERED**: `SOURCES` is hand-maintained, nothing compares a table's declared paths against where its rows were read, and a table id missing from it gets an empty list and no warning
- State a comparator's storage precision from its own version-pinned source, never from our recall or a doc page for another version: precision changes between releases, and recall is not evidence of a storage format. **REMEMBERED**

## 5. How the checkers themselves must behave

- A check that could not run is carried to the summary as NOT CHECKED, not as a pass. **GATE** `_CAPTION_CHECK_RAN` and its warning, and `page_check._check_prose` returning `(0, 1)`; **REMEMBERED** for the rest, which is most of them: `caption_n` returns 0 on both skip paths, `run_conditions` continues past an empty feed, `figures_fresh` returns 0
- Handle both artifact shapes (object and array of per-pass records), and count an unreadable file as a finding rather than skipping it. A silent skip made the best-stamped feed in the paper audit as "no result files". **GATE** `_versions_in`, `run_conditions`
- Search for a version at every nesting level, since a key nested under `run_conditions` is invisible to a top-level scan, and reject populated but uninformative values ("unknown...", "?", "n/a", anything with no digit). **GATE** `_nested_version_keys` and `_is_real_version`, neither of which the overlay audit calls
- Exclude sidecars (`_buildstats.json`, `_gc.json`, `_manifest.json`) from version and condition audits. A checker that cries wolf is a checker nobody runs. **GATE** `SIDECAR_SUFFIXES`
- A gate that fails on compliance is worse than no gate: fix the checker before believing its findings. F3 once reported five FAILs, none real, with one true finding buried among them. **REMEMBERED**
- Derive a reported quantity by instrumenting the real generator, not by re-deriving it. A second implementation is a second thing that can drift. **GATE** `caption_n` monkeypatches `mmm`/`mmm_rec`
- Count unfixable history rather than failing on it, and name what it is: 415 overlay records predate `BENCH_IMAGE`, 235 of 380 canonical rows carry no producer stamp. Neither passed nor failed. **GATE** counters in `provenance_check` and `fairness_check`
- Keep check functions and their tables above `if __name__ == "__main__"`, and key them on the lane spelling `runs.jsonl` uses. F6b was dead code until 2026-08-01 and keyed `l1_tpc` where the data says `l1tpc`. **REMEMBERED**, nothing tests that a check is reachable

## 6. How work is queued and stored

- Every campaign dataset switch lives in `campaign_env.sh` in the repo and is sourced by the lane scripts. A launcher in a home directory is not where configuration lives: one written on 2026-08-08 omitted all six `BENCH_*` switches, and only l2 happened to validate its scale name. **REMEMBERED**: nothing sources the file, and the one live campaign script hardcodes its own switches and corpus test
- Check each corpus is present, not merely that its path variable is set; a set path with no corpus is how the synthetic sparse rows got in. **GATE** `campaign_env_check()` for a caller that sources it
- Run a smoke stage before any long matrix and let it abort the campaign. It caught an unknown backend arm in 19 seconds, and aborted q87 when the new disk columns came back null. **REMEMBERED**: no SMOKE-BAD stage survives outside the archive, and queue82's per-image import check runs no cell
- One runner per bench host. `sweep_orphans()` destroys a live campaign's in-flight cells, so the runner takes an exclusive flock; never rebuild a bench image and never co-run a smoke while a campaign is live. **GATE** `results/.runner.lock`
- The env forward list is an allowlist and gets a new entry with every new switch, or the flag parses and changes nothing; naming a workload no selected lane defines is an error. **GATE** allowlist and explicit-workload validation in `runner.py`
- A new tier is registered only when every scale table has it. `tpch10` reached MEM/TIMEOUT but not HEAP and died on KeyError after four hours in a queue. **REMEMBERED**, argparse validates against the first table only
- Pin server images by immutable digest and client libraries by exact version; the embedded wheel and the server image must be the same release. `:latest` once resolved to a SNAPSHOT on one host and a different digest on the other. **GATE** partial (served rows must carry a version or digest); **REMEMBERED** for the client pins
- Read a library version from the installed distribution (`importlib.metadata`), never from a module attribute. `qdrant-client` defines no `__version__`, so that row recorded "?" from the day the lane was written. **REMEMBERED**: no check inspects how a version was obtained, and "?" passes the overlay audit
- Merge campaign rows by appending, never replacing, and refuse the merge if it would shrink the canonical cell count, since a replacing merge drops rows a campaign already paid for. Dry run by default, timestamped backup first. **GATE** `merge_campaign.py`
- Keep the live append log untracked and write `results/runs_paper.csv` in the same call that writes the tables, so published rows and published tables cannot come from different states of the log. **GATE** `make_paper_tables.main`
- Archive before deleting anything under `results/`, guard the delete on the archive's own contents, and keep the archive tracked in the repo (check the ignore rules did not swallow it). The keep-list covers the logs of every job it keeps, not just the scripts, because the log is the only record of how a kept job ran. zsh does not word-split, so the first attempt tarred zero entries and then ran rm; the guard later fired for real on that empty archive. **REMEMBERED**
- Read the artifact for current state. Trackers, task notes and append-only status files are history; only the last entry describes now. **REMEMBERED**
- Published numbers are measured on tk@mini; a number from another host is not comparable with the rows beside it. The laptop is for harness development and smoke only. **REMEMBERED**

---

## 7. Defaults and sanctioned overrides

We run every engine as shipped, and override a default only where leaving it would
make the comparison meaningless. Four sanctioned categories:

1. **Resource fitting** (always applied): heap, thread pool and memory settings that
   fit an engine to the cell's cpuset and memory envelope. Envelope equality, not tuning.
2. **Vendor settle step**: documented bulk-load-then-query preparation, timed inside build (section 2).
3. **Operating-point matching**: where defaults put engines at different points of a
   quality/latency tradeoff, move them onto one point, because a latency comparison
   at unequal recall compares nothing.
4. **Documented escape hatch**: a default that is demonstrably pathological, tuned to
   the vendor's own recommendation, with the same care applied to every backend in the lane.

What we never do: per-system expert tuning beyond vendor guidance, or tuning
ArcadeDB with insider knowledge not applied to comparators.

An override nobody can find is a defect, whichever way it moves the number. Every
override is stamped on the row where a field exists (`es_prune`, `degree_param`,
`degree_family`, `heap`, `server_heap`) **and** named in reader-facing text (paper,
table caption, or page condition). `DISCLOSED WHERE = NOWHERE` below marks work
still to do.

| Engine | Setting | Category | Why | Disclosed where |
|---|---|---|---|---|
| ArcadeDB dense (emb + srv) | `LSM_VECTOR METADATA {"addHierarchy": true}` (default false) | operating-point | Makes the graph structurally comparable to the hierarchical hnswlib family. Inconsistent with our own E2 lane, which builds flat. | **NOWHERE**, and not stamped on any row |
| ArcadeDB server (all 4 arms) | `queryMaxHeapElementsAllowedPerOp=5000000` | escape hatch | Lets a >1.24M-group top-N complete. On 26.8.1 the default auto-scales to `max(500k, heap/2048)`, so the pin is LOWER than default at the 12g, 16g and 24g tiers and higher at 4g/6g/8g. | **NOWHERE** (code comment only) |
| ArcadeDB embedded (L1 tabular only) | same knob, `jvm_args` | escape hatch | Applied in 1 of the 8 ArcadeDB embedded adapters, so E4 compares two different query-memory caps. | **NOWHERE** |
| ArcadeDB embedded (L1-TPC, E2, L4 doc) | `heap_size` sets `-Xmx` only, `-Xms` left at the JVM default | resource fitting (absent) | The paper asserts `-Xms=-Xmx` as blanket protocol. False for three published arms whose server counterparts are pinned. | **CONTRADICTED** by paper.tex protocol paragraph |
| QuestDB (L4) | WAL-apply poll inside the timed ingest region | settle step, misplaced | Cannot exit under 3 s of sleep; QuestDB's 5.99 s measured ingest is roughly half poll. The 4.3x headline would fall near 2x. | **NOWHERE**, and the time-series section's prose says "No engine here takes a settle step" |
| ArcadeDB native TS vs QuestDB/DuckDB | ingest timer stops at `wait_completion()` (accepted, sealing outstanding) | operating-point | Three ingest rates timed to three completion semantics. | **NOWHERE** |
| ArcadeDB native TS | `SHARDS 4` (default 0 = 11 under this cpuset) | resource fitting | Fixes the shard count instead of deriving it from the cpuset. | raw JSON only |
| ArcadeDB native TS | `TS_PRIMITIVE=1` (default 0); `TS_NUMPY` already defaults to 1 | escape hatch | One opt-in fast path under the 1.86M pts/s headline; comparators use ordinary bulk paths. `TS_NUMPY=0` exists only to reproduce the pre-fix number. | raw JSON only |
| DuckDB (L1 tabular) | `PRAGMA threads = len(sched_getaffinity(0))` | resource fitting | The F6 fix. Applied in 1 of 4 DuckDB lanes; l1_tpc, l3d and l4 still run ~1.7x oversubscribed. | FAIRNESS.md F6 (as fixed); **NOWHERE** reader-facing |
| DuckDB (L1 tabular) | drop indexes before bulk load, recreate after | escape hatch | Idiomatic columnar bulk load, one arm only, under the published "10.7x ahead" loader claim. | **NOWHERE** |
| DuckDB VSS (L3d) | `hnsw_enable_experimental_persistence=true` | escape hatch | Required to persist an HNSW index at all. The row is measured on a vendor-labeled experimental configuration. | **NOWHERE** |
| ArcadeDB (L1-TPC) | index on `LineItem(l_shipdate)`, comparators get none | operating-point | Both published TPC-H queries filter that column. Bias runs for us; PostgreSQL would benefit most. | **NOWHERE** |
| Elasticsearch (L3s) | `xpack.security.enabled=false` | escape hatch | Harness plumbing; also removes TLS and auth from every ES latency measurement. | **NOWHERE** |
| Elasticsearch (L3s) | `number_of_replicas=0` | resource fitting | A single-node cluster cannot allocate a replica; the index would sit yellow forever. | **NOWHERE** |
| SurrealDB, composed Qdrant (E2) | `mem://` and `location=":memory:"` while ArcadeDB runs on disk | **unsanctioned** | Latency and atomicity both compared against in-memory stores. Weakens "rolled back cleanly in 200 of 200". | **NOWHERE** |
| sqlite-vec (L3d) | no PRAGMA cache/mmap/journal settings at all | resource fitting (absent) | The one dense arm given no resource fitting: stock ~2 MB page cache inside a 36 GiB cap. | partly (dagger discloses exact scan only) |
| Neo4j (L2, E2) | heap pinned per tier; `server_memory_pagecache_size` = container mem less heap less a 1 GiB reserve, floored at 512m | resource fitting | Heap parity, with the rest of the cap fitted for Neo4j rather than left at its default. | **NOWHERE** (runner comment only) |
| PostgreSQL (`postgres_tuned`) | shared_buffers etc derived from the container cap, durability untouched | resource fitting | Ablation arm asking whether image defaults make the latency comparison unfair. Has never run: 0 rows. | display name exists for a row that does not |
| harness-wide | manifest records cpuset/mem/heap/images and no engine configuration | **unsanctioned** | Nothing records the overrides above: the manifest holds ts, tier, scale, cpuset, workers, shards, reps, seed, mem, heap and images, and no configuration table exists in the paper. | **NOWHERE** |
| ArcadeDB dense, E2 | `"similarity": "EUCLIDEAN"` (default COSINE) | operating-point | SIFT1M ships exact L2 ground truth, DEEP-10M is unit-normalized, comparators are set to L2. Correct and symmetric. | lane docstring only |
| LanceDB (L3d) | `.ef(100).nprobes(10)` | operating-point | Puts LanceDB on the lane's shared operating point (unset ef gave recall 0.711); nprobes 10 from a flat sweep. | adapter comments only |
| all dense arms | `EF_CONSTRUCTION=100`, `EF_SEARCH=100` | operating-point | Shared beam. No-op for ArcadeDB; moves some comparators down from their own defaults, and no audit of those defaults exists. | lane docstring only |
| ArcadeDB server (all arms) | `ARCADEDB_OPTS_GC=` is cleared explicitly, and `JAVA_OPTS` carries `-XX:+UseCompactObjectHeaders` | operating-point | Makes E4 a transport comparison. **This row was false until 2026-08-30.** It claimed `JAVA_OPTS` replaces the image's `-XX:+UseZGC`; that was true at 26.8.1, where the Dockerfile put the flags IN `JAVA_OPTS`, and upstream then moved them to their own variable `ARCADEDB_OPTS_GC` precisely so they would survive a `JAVA_OPTS` override. Every served row measured between those points ran ZGC against an embedded arm on G1. | DISCLOSED: DECISIONS #54, enforced by `verify_pair_c25.sh` |
| ArcadeDB server vs embedded | both arms run ONE set of upstream jars on ONE JVM (Corretto 25) | fairness | The axis isolates transport. Until 2026-08-30 it also carried JVM major (Temurin 21 vs Corretto 25), libc (musl vs glibc), collector (ZGC vs G1) and object-header layout -- `-XX:+UseCompactObjectHeaders` is REJECTED by JDK 21, so the served arm could never have had what `jvm.py:513` gives every embedded JVM. | DISCLOSED: DECISIONS #54, enforced by `verify_pair_c25.sh` (jars AND JVM major on both sides) |
| ArcadeDB server (all arms) | `ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap}` (image ships 2G) | resource fitting | Heap parity per tier. The 2 GB default cost the server 15% p50 and 35% build time at 10M. | DISCLOSED: paper, T5 caption, F3, `server_heap` read back |
| Elasticsearch (L3s) | `ES_JAVA_OPTS=-Xms{heap} -Xmx{heap}` | resource fitting | Envelope equality across the lane's JVM engines. | DISCLOSED: FAIRNESS.md F3, enforced by `observe_server` |
| all served backends | server takes the full tier cap, client a separate `BENCH_CLIENT_MEM` (default 8g), stamped `mem_split="full+client"`; heap 50% of cap (67% at deep10m) | resource fitting | A served engine now sees exactly the cap an embedded engine of the same tier sees, with the driver on top. Changed 2026-08-14 in `c1cbf44721`; all 990 split-bearing rows in `results/` still carry the old 0.75. | **CONTRADICTED**: paper and T5 caption assert a 0.75/0.25 split |
| ES, Milvus, Qdrant, ArcadeDB, Neo4j, LadybugDB | forcemerge / flush+load / green-wait / COMPACT INDEX / awaitIndexes / CHECKPOINT, inside build | settle step | Each engine's own documented preparation. ArcadeDB takes none on L2 OLTP, and in the dense lane only Qdrant and Milvus define one at all. | DISCLOSED as a class: paper Limitations, FAIRNESS.md |
| ArcadeDB (L2 OLAP) | Graph Analytical View, `UPDATE MODE OFF`, build counted; `BENCH_GAV=0` ablation published | operating-point | ArcadeDB's documented OLAP answer, priced separately, with the view-off arm published. | DISCLOSED: page conditions, paper, `gav` on every row |
| ArcadeDB (L3s) | int8 posting quantization (the engine default); fp32 arm prices it | operating-point | The headline arm is the default. The ablation is the only quantization axis available. | DISCLOSED: T4 caption, `SPARSE_PRECISION` |
| ArcadeDB dense (L3d), all four arms | `graphBuildCacheSize=0`, the engine default: HNSW build cache sized as 25% of *available* heap at build start; unread for int8, which gets `DEFAULT_CACHE_SIZE=100,000` | operating-point (default) | The default is kept because it is what a user gets, and it cuts against us: on deep10m the served fp32 arm sized to 3.67M of 9.99M and built in 190-198 min where the same jars embedded sized to the whole corpus and built in 38-42; at a matched capacity the two are within 10%. Ablation `results/ablation_cache_8d6af9475.jsonl` (21 cells) prices the knob. | DISCLOSED: PAGE-SPEC dense build-cache note; to be filed upstream |
| ArcadeDB dense (T5 / page 10M multipass table only) | `graphBuildCacheSize=9,990,000` (whole corpus), explicit | operating-point, **flatters us**, user decision (DECISIONS #56) | The multipass re-run at 8d6af9475 pins the HNSW build cache to the corpus on all four ArcadeDB arms so the served fp32 build takes ~56 min instead of ~190 at the default. Comparators have no such knob. The single-pass campaign rows stay at the default. | MUST be in the T5 caption and the page condition; #7146 documents the default's cost |
| ArcadeDB vs dense comparators | `M=32` (maxConnections) against `M=16` (doubled at base) | operating-point | Numerically equal settings build graphs of half the degree, so the lane matches effective base degree. 32 is also 26.8.1's own default, so only the comparator side is set. Getting it wrong once published "0.951 vs 0.971, a small deficit". | FULLY DISCLOSED: paper, T5 caption, page, per-row stamps, F7 |
| ArcadeDB dense (L3d, E2) | `neighborOverflowFactor` left at the engine default 1.2 | not an override, declined deliberately | Raising it to 2.0 cuts graph-unreachable nodes 3.5x (299 -> 85 at 50k) with build time, peak RSS and recall flat. Declined because no hnswlib-family comparator has the knob, so it would move only our graph, in our favour. Unlike the `maxConnections` row above, which converts units rather than tunes. `l3d_dense.py` never sets it. | FAIRNESS.md F7, DECISIONS.md #45 |
| Elasticsearch (L3s) | `index_options {"prune": false}` | operating-point | ES 9.1+ prunes on ELSERv2 thresholds; on SPLADE that costs the recall in section 1, and the default's bias ran in our favor. | FULLY DISCLOSED: paper subsection, page condition, `es_prune` on every row |
| ArcadeDB native TS | `TS_TAGS=1` reduced schema; unbounded last-point query | operating-point | Applied to all three engines. The published unbounded form is the faster one for us: 0.720 ms against 0.860 ms for the 1-hour window (`TS_LAST_WINDOW_S=3600`), measured as a pair in the same rep. | DISCLOSED: schema-fidelity paragraph in the paper, which states both numbers |
| Milvus | `DEPLOY_MODE=STANDALONE`, embedded etcd, vendor's own `embedEtcd.yaml` | resource fitting | Single-container deployment plumbing; the mounted file is Milvus's own default. | not stated, low severity |
| Qdrant (L3s), ArcadeDB dense (L3d, E2) | sparse `on_disk=False`; dense `storeVectorsInGraph:false`, `beamWidth:100` | not an override | Explicit restatements of engine defaults, recorded so a future audit does not mistake one for a deviation. Their presence makes the ArcadeDB metadata clause look uniformly deliberate and hides which key actually departs. | recorded here only |
