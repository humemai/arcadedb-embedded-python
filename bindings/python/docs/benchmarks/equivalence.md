# Answer Checking: Did the Engines Answer the Same Question?

A benchmark that never checks the answer measures how fast an engine can be wrong.

That is not a hypothetical. An adapter that silently drops a filter, a join condition, or a
group returns faster than one that does not, and on a latency-only table it reads as a lead
rather than as a bug. So does an engine defect that skips rows. Both have happened here, in
our favour, on tables that had already been through several review passes.

This page is the reason the suite is not a stopwatch.

## What Changed, and When

Until 2026-09-14 nothing in this harness compared answers across engines. The vector lanes
measured recall against ground truth and the cross-model lane compared torn state after an
interrupted transaction; every other lane recorded latency, throughput, and for a few
queries a row count. Nothing had ever asked whether two engines returned the same rows for
the same question.

The rule from that date:

> Every timed query whose answer is deterministic records a **canonical digest** of that
> answer, with a short readable sample beside it. A gate refuses to publish a table whose
> engines disagree at the same size. A query an engine cannot express is **declared** absent
> in its adapter, and the gate names it. It is never silently skipped.

The digest is computed **outside the timed section**, from the object the timed call
returned, so checking the answer costs the measurement nothing. The gate is
`equivalence_check.py`, and it runs on every publish beside the provenance, fairness, and
page checks.

Two consequences followed immediately. The campaign that was starting did not start until
the digests and the gate existed and every lane recorded them. And the same digests were
run first at small scale across every engine on every table, because if an adapter had been
answering a different question all along, the rows already published were wrong, and that
had to be known before anyone read them.

## The Canonical Form

Two engines that agree about an answer will not hand back the same objects. One returns
tuples, another dictionaries, another its own row wrapper; one calls a group key `_id` and
another names it in the return clause; one gives an integer where another gives a double;
one returns a timezone-aware datetime and another epoch milliseconds; one returns the same
set in a different order. Hashing what a driver handed back would disagree on every engine
pair for reasons that have nothing to do with the answer.

So the answer is put into a canonical form first, identically for every engine, and the
digest is taken of that.

**Declared columns.** Every query declares its column order. That is what makes a dictionary
row comparable with a positional tuple: the declaration is looked up in a mapping row and
taken as-is from a tuple row, which a SQL driver already returns in the select list's order.
A column may declare alternative names, because the same question is answered under
different names by different drivers, and a dotted name reaches into a sub-document, which
is how a composite group key is read without writing a digest per engine.

**Order.** The canonical form is sorted unless the query defines an order, because a query
without an `ORDER BY` does not define one and two engines returning the same set in
different orders agree. When the query does define an order, the rows are stably sorted on
the declared key with an identifier as tie-break, because engines break ties arbitrarily and
two identically ranked rows in a different order are not a disagreement. The membership of
an ordered query with a limit still is: a wrong order returns a different set of rows. The
sort is applied to every engine identically, so it is a canonicalisation and not a
relaxation.

**Values.** Floats are rounded to a fixed number of significant digits before hashing. Nulls
and absent columns get distinct tokens, so a missing column can never be mistaken for a null
one. Anything that varies with the driver rather than with the answer is normalised away
before the hash, which is what lets a digest mismatch mean the **answers** differ and
nothing else.

**What is recorded.** A short stable hash over the canonical rows, the declared column
names, and the ordering flags; the row count; and the first few canonical rows as one short
readable line. The sample is there so a disagreement can be **read** rather than only
detected. A gate that can only say "these two differ" sends you back to the machine; one
that prints both sides tells you which engine is wrong.

!!! note "A digest is of the canonical answer, not of the raw rows"
    Two engines whose digests match did not return identical result objects, and were never
    expected to. This is the single most common way to misread the field.

## Measures, Counts, and Identifiers

A summed or averaged column is a **measure**, and it is declared as one in the query's
digest specification and compared as a number whatever type the driver hands back. A count
or an identifier is not declared that way and is compared exactly.

The distinction was forced by a real split. At the campaign's own document size, a pricing
summary split seven engines against one, and the one returned a summed integer column as an
integer where the SQL engines, MongoDB, and SurrealDB returned a double. The canonical form
printed an integer exactly and a double to six significant digits, so one number became two
strings. In the same row the count was an integer on both sides and identical, the average
was bit-identical, and the average times the count is the sum. Nobody had computed anything
wrong. The two spellings happen to coincide below a certain magnitude, which is why every
earlier run had passed.

It was fixed by declaring what each column **is**, rather than by loosening the comparison.
Loosening it would have been the wrong fix: a count rounded to six significant digits would
let two counts that differ by one agree, and a lost row is exactly what this gate exists to
catch. The declaration is per query and never per engine, so it cannot be used to make one
engine's answer match another's.

The rounding itself was measured rather than assumed. Six significant digits leaves an
enormous margin over the worst disagreement observed between engines on real floating-point
cells, while tightening it further splits real data where two engines land one bit either
side of the same value.

!!! warning "Where rounding can hide a lost row, the query changed, not the rounding"
    Two analytical queries carried no count column, and at the campaign's largest size a
    single lost row moved each of their sums by less than the digest's rounding, so it went
    undetected much of the time. Both queries now count the rows they aggregate, and that
    count is compared exactly. It is part of the answer, not a page column. The reason it
    was worth a query change before a campaign, which is the only time such a change is
    free, is the engine defect described below: an engine that silently loses one row to an
    index bound is exactly what those two queries could not see.

## When an Engine Cannot Express a Query

Some engines genuinely cannot ask some questions. That is a result, and it is recorded as
one.

An adapter records `unexpressible: <reason>` for that query. The gate lists every such
declaration with its reason, the page prints a dash in that cell, and the table's condition
names the engine and the operation. A blank is indistinguishable from agreement; this string
is not.

**"Unexpressible" is a declaration, not a failure.** It is not a crashed cell, not a
timeout, not a gap waiting to be filled, and not evidence that the engine is slow. A
silently missing answer is the failure, and telling the two apart is exactly what the gate
is for.

It is also a claim that has to be earned. An adapter may record a query as unexpressible
only after the engine's own documentation has been read and the constructs that were tried
are named, and the declaration carries that evidence rather than a one-line opinion. A first
failure is evidence about our fluency, not about the engine. Two precedents settled that
rule: one engine's degree distribution was impossible with a single grouping and correct as
two subqueries, and another's vector index looked unusable until its parameters were read
out of the documentation and calibrated. A third case was a triangle count declared
impossible in an engine's own language that turned out simply to be untried; the rewrite is
exact against an independent enumeration at several corpus sizes, and its digest matches the
number five other engines already agreed on.

A rewrite must compute the **same answer**, proven by the digest, never merely run faster.
That is also what makes it defensible for one engine's two deployments to run different
query text where the faster spelling inverts between their versions: both texts stay in the
adapter, both are measured, and the digests prove the two forms compute the same number. One
shared text would otherwise hand whichever deployment it suits less a penalty that measures
our spelling rather than either engine.

## Three Ways to Pass While Proving Nothing

The gate is written against its own failure modes, because a gate that passes vacuously is
worse than no gate at all.

**A group with one engine is unchecked, not passed.** One digest agrees with itself. Those
groups are counted and listed under their own heading, never folded into the count of
groups that actually agreed.

**Silence is not agreement.** A backend that records no digest for a query its neighbours do
record fails: either it answered and did not say what it answered, or it never ran the
query. The only way out is the explicit unexpressible declaration above.

**An engine must agree with itself.** Repetitions of one cell are the same database asked
the same question, and so are its two durability settings, since a strict commit changes
when a write becomes durable and not what the answer is. Two digests from one backend inside
one group mean the digest is not a property of the cell, which is its own failure class.

## Where Recall Replaces the Digest

A digest over an approximate answer would be a false precision. The vector lanes therefore
keep **recall against ground truth**, which is the stronger check: the corpora ship exact
top-k ground truth, so an approximate index is measured against the right answer rather than
against another approximate index. Latency is never printed without the recall it was
achieved at, and the operating points are matched so that the recalls are comparable in the
first place. See the [vectors table](https://humem.ai/projects/arcadedb#vectors).

The cross-model lane keeps its **torn-state comparison**: after an interrupted transaction,
what does each engine leave behind. Its two read paths carry recall against a brute-force
answer over the same filtered candidate set, with the graph and document halves digest
compared exactly, because an engine that filters after the search shows it in the recall and
not in the latency. See the
[cross-model table](https://humem.ai/projects/arcadedb#crossmodel).

## What It Found

Answer checking found five defects in two days. Three are in the engine and are filed
upstream; two were ours.

### Three Engine Defects, Filed Upstream

[**ArcadeData/arcadedb#7609**](https://github.com/ArcadeData/arcadedb/issues/7609): a
comparison against a bare decimal literal loses the boundary value. Found because an
analytical revenue query returned a different total from every comparator on the same data.
Reproduced on a small fixture: an equality against the literal returns nothing, a
greater-or-equal returns exactly what a strictly-greater returns, and a `BETWEEN` over the
same bounds is correct. Root-caused in the engine to a suffix-less literal being parsed at
single precision and widened back to double, which reproduces the error rather than undoing
it. It is wider than the first example, since the direction depends on which literal is
written, and sharper than it looks: the same rows behind an index answer every comparison
correctly, because an index fetch takes a different path, so adding or dropping an index
changes the answer. The harness rule that follows is that ArcadeDB SQL in this repository
compares a numeric column through `BETWEEN` or a bound parameter and never against a bare
decimal literal, and the gate enforces it rather than discipline.

[**ArcadeData/arcadedb#7610**](https://github.com/ArcadeData/arcadedb/issues/7610): the
served engine serialises a time bucket as a date, so every bucket inside one calendar day
collapses to one value. The embedded engine on the same build returns the full grouping, and
so do five comparators. Grouping, row counts, and aggregates are all correct; only the value
on the wire is destroyed. The affected cell is withheld from the page and printed as a known
disagreement rather than published as a latency for a different answer, and the rule that
follows is that a served query projecting a temporal value is checked against its embedded
twin. See the [time series table](https://humem.ai/projects/arcadedb#timeseries).

[**ArcadeData/arcadedb#7611**](https://github.com/ArcadeData/arcadedb/issues/7611): an
indexed lower bound loses part of a run of equal entries. An ascending range seek starts
wherever the binary search landed inside the run, and the entries before it are never
produced, so a query over an indexed column can be short by rows that qualify. Found by
running the document lane at the campaign's own scale factor rather than a small one, and
root-caused with a repro against the engine API, including a candidate fix. It is not
specific to one type, an unindexed scan over the same rows is correct, and rows written in
one transaction merge into one entry and answer correctly, which is why bulk-loaded data
hides it. This is the defect the two added row counts exist to catch.

### Two of Our Own

One of our analytical query texts computed four of the five aggregates every comparator
computed, so the cell timed a smaller question than the row beside it, and it was faster for
that reason. The other was the integer against double split described above, which was a
defect in the digest specification rather than in any answer.

Both of ours made ArcadeDB look better than the truth. That is the argument for this gate in
one sentence: two wrong numbers, both in our favour, on a page that had already been
reviewed three times.

The response on the page was not a caveat. Both ArcadeDB rows came down from the document
analytics table, the table carries a condition naming ArcadeDB and saying why, and the page
gate was changed so that a **declared** withdrawal passes while a silent one still fails. A
table may lose a row only by telling the reader it did. See the
[documents table](https://humem.ai/projects/arcadedb#documents).

!!! info "Bugs are written down when they are found, not when they are fixed"
    A finding gets a reproduction the day it is found, an upstream draft when it belongs to
    the engine, and an entry in the issues trail whether or not it has been filed yet. What
    each attempt teaches about a comparator's dialect is written down per engine, so the
    next dialect problem starts from what is already known instead of from a shrug.

## What Answer Checking Cannot Prove

Several comparators share a SQL dialect closely enough that a defect in a shape all of them
spell the same way would agree with itself and pass. The independent evidence therefore
comes from the engines with languages of their own on each lane, and the gate is only as
strong as that independence.

ArcadeDB collects the most findings here, and the honest reason is partly that it is the
engine examined hardest: its source is open to us, it runs in two deployments, and its SQL
is hand-written by us rather than generated. A comparator that had the same scrutiny would
probably yield findings too.

## What It Means for a Reader

- A published latency is a latency for **the answer the other engines gave**. If the engines
  of a table disagreed at any size, the table did not publish.
- A dash on the page is either a declared unexpressible operation, with its reason in the
  table's condition, or a censored cell with its budget stated. Neither is a gap nobody
  noticed.
- A withheld cell is a reproduced and filed disagreement, named as such, and it comes back
  at the re-pin that carries the fix.
- A missing ArcadeDB row is declared in a condition naming ArcadeDB and the reason.

The full rules are
[`FAIRNESS.md` F12](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/FAIRNESS.md)
and section 2 of
[`PROTOCOL.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/PROTOCOL.md).
