"""Shared Milvus steps for the dense and sparse lanes (2026-10-22, Zilliz's review of our setup, issue "Milvus as Zilliz recommends").

Three things the vendor asked for and both lanes now do the same way:

1. BULK IMPORT, not row-by-row inserts (https://milvus.io/docs/import-data.md). The vendor's documented path is:
   write the rows to Parquet with `RemoteBulkWriter` straight into Milvus's own MinIO bucket, then start one import job
   (`bulk_import`) and poll it (`get_import_progress`) until it is Completed. Files go under a prefix of their own
   (`bench_import/`), never under Milvus's internal `files/` directory, which 3.0.3 refuses as an import path.
   Everything between the first row and the job's Completed state is the lane's ingest_s, as for every other engine whose
   documented bulk path is "prepare, send, wait": file preparation, upload and the job are timed separately and recorded
   (`milvus_import_prep_s`, `milvus_import_job_s`) and their sum is `ingest_s`.
2. SEALED AND FULLY INDEXED BEFORE ANY TIMED SEARCH: `wait_sealed_and_indexed` waits until `flush` is done, every
   persisted segment is Flushed (none Growing or Sealed), the index reports Finished with no pending rows, and, after
   `load`, the loaded segments hold every row. Each wait is timed on its own (`milvus_seal_wait_s`, `milvus_index_wait_s`,
   `milvus_load_s`), and the lane's `index_s` stays the sum of them as before (the same timer that has always covered
   flush, index wait, compaction and load).
3. WHAT A SEARCH RETURNS IS RECORDED: `SEARCH_SHAPE` is stamped on every row. The timed search returns primary keys and
   distances only (no output fields, no vector field, no filter), because the workload asks for nothing else.
"""
import os
import time

BULK_PREFIX = "bench_import"
BUCKET = "a-bucket"          # Milvus's default minio.bucketName; the compose file does not change it
MINIO_USER = MINIO_PASSWORD = "minioadmin"   # the compose file's MINIO_ACCESS_KEY / MINIO_SECRET_KEY

# Stamped on every Milvus row (engine_stats): what each timed query asks the server to return.
SEARCH_SHAPE = {"milvus_search_output_fields": [], "milvus_search_filter": "", "milvus_search_returns": "ids_and_distances"}


def bulk_import(cl, host, collection, schema, rows, file_type="PARQUET", timeout_s=7200):
    """Prepare `rows` (an iterable of dicts matching `schema`), upload them to MinIO, import them. Returns the timings.

    `host` is the Milvus server's hostname (BENCH_SERVER_HOST); MinIO's is BENCH_SIDECAR_MINIO, set by the runner for the
    compose deployment."""
    from pymilvus.bulk_writer import BulkFileType, RemoteBulkWriter, bulk_import as _import, get_import_progress
    minio = os.environ["BENCH_SIDECAR_MINIO"]
    conn = RemoteBulkWriter.S3ConnectParam(endpoint=f"{minio}:9000", access_key=MINIO_USER, secret_key=MINIO_PASSWORD,
                                           bucket_name=BUCKET, secure=False)
    t0 = time.perf_counter()
    with RemoteBulkWriter(schema=schema, remote_path=BULK_PREFIX, connect_param=conn,
                          file_type=getattr(BulkFileType, file_type)) as w:
        for r in rows:
            w.append_row(r)
        w.commit()
        files = w.batch_files
    prep_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    url = f"http://{host}:19530"
    resp = _import(url=url, collection_name=collection, files=files)
    job = resp.json()["data"]["jobId"]
    last = None
    while time.perf_counter() - t1 < timeout_s:
        d = get_import_progress(url=url, job_id=job).json().get("data", {})
        last = d
        if d.get("state") == "Completed":
            break
        if d.get("state") == "Failed":
            raise RuntimeError(f"milvus bulk import job {job} failed: {d.get('reason')}")
        time.sleep(0.5)
    else:
        raise RuntimeError(f"milvus bulk import job {job} did not complete within {timeout_s}s: {last}")
    job_s = time.perf_counter() - t1
    return {"milvus_import_prep_s": round(prep_s, 2), "milvus_import_job_s": round(job_s, 2),
            "milvus_import_files": sum(len(f) for f in files), "milvus_import_file_type": file_type,
            "milvus_import_job": job, "ingest_s": round(prep_s + job_s, 2)}


def _index_done(cl, collection, field):
    d = cl.describe_index(collection, field)
    return (d.get("state") == "Finished" and int(d.get("pending_index_rows", 0)) == 0
            and int(d.get("indexed_rows", -1)) == int(d.get("total_rows", -2)))


def wait_sealed(cl, collection, n_rows, timeout_s=7200):
    """flush, then wait until every persisted segment is Flushed and together they hold n_rows. Returns seconds."""
    t0 = time.perf_counter()
    cl.flush(collection)
    while time.perf_counter() - t0 < timeout_s:
        segs = cl.list_persistent_segments(collection)
        if segs and all("Flushed" in str(s.state) for s in segs) and sum(int(s.num_rows) for s in segs) == n_rows:
            return time.perf_counter() - t0
        time.sleep(0.5)
    raise RuntimeError(f"milvus segments not all sealed and flushed within {timeout_s}s: "
                       f"{[(str(s.state), s.num_rows) for s in cl.list_persistent_segments(collection)]}")


def wait_indexed(cl, collection, field, what, timeout_s=7200):
    """Wait until the index is Finished with nothing pending. The three-part test is the dense lane's (BUGS F8)."""
    t0 = time.perf_counter()
    d = None
    while time.perf_counter() - t0 < timeout_s:
        if _index_done(cl, collection, field):
            return time.perf_counter() - t0
        d = cl.describe_index(collection, field)
        time.sleep(1.0)
    raise RuntimeError(f"milvus index did not finish within {timeout_s}s ({what}): {d}")


def load_and_check(cl, collection, n_rows):
    """load, then check the loaded segments hold every row. Returns seconds."""
    t0 = time.perf_counter()
    cl.load_collection(collection)
    loaded = sum(int(s.num_rows) for s in cl.list_loaded_segments(collection))
    if loaded != n_rows:
        raise RuntimeError(f"milvus loaded segments hold {loaded} rows, expected {n_rows}")
    return time.perf_counter() - t0


def wait_sealed_and_indexed(cl, collection, field, n_rows, compact=False):
    """The settle step before any timed search. `compact` runs the dense lane's compaction passes (BUGS F8) between the
    index wait and the load, as the lane always did. Returns the separately timed waits plus the segment trace."""
    out = {"milvus_seal_wait_s": round(wait_sealed(cl, collection, n_rows), 2)}
    out["milvus_index_wait_s"] = round(wait_indexed(cl, collection, field, "after seal"), 2)
    trace = [len(cl.list_persistent_segments(collection))]
    compactions, comp_s = 0, 0.0
    if compact:
        for _ in range(8):
            t0 = time.perf_counter()
            job = cl.compact(collection)
            while time.perf_counter() - t0 < 7200:
                if "Completed" in str(cl.get_compaction_state(job)):
                    break
                time.sleep(1.0)
            else:
                raise RuntimeError(f"milvus compaction {job} did not complete within 7200s")
            compactions += 1
            out["milvus_index_wait_s"] = round(out["milvus_index_wait_s"] + wait_indexed(cl, collection, field,
                                                                                         f"after compaction {compactions}"), 2)
            comp_s += time.perf_counter() - t0
            trace.append(len(cl.list_persistent_segments(collection)))
            if trace[-1] >= trace[-2]:
                break
        out["milvus_seal_wait_s"] = round(out["milvus_seal_wait_s"] + wait_sealed(cl, collection, n_rows), 2)
    out["milvus_load_s"] = round(load_and_check(cl, collection, n_rows), 2)
    out["milvus_compactions_forced"] = compactions
    out["milvus_segments_trace"] = trace
    return out
