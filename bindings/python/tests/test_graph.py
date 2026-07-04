

def test_graph_batch_new_edges_bulk(tmp_path):
    """new_edges buffers many property-less edges in one crossing."""
    import arcadedb_embedded as arcadedb

    with arcadedb.create_database(str(tmp_path / "bulk_edges_db")) as db:
        db.command("sql", "CREATE VERTEX TYPE BP")
        db.command("sql", "CREATE EDGE TYPE BE")
        with db.graph_batch(use_wal=False) as batch:
            rids = batch.create_vertices("BP", [{"id": i} for i in range(100)])
            sources = [rids[i] for i in range(0, 99)]
            dests = [rids[i + 1] for i in range(0, 99)]
            batch.new_edges(sources, "BE", dests)

        count = db.query("sql", "SELECT count(*) as c FROM BE").first().get("c")
        assert count == 99
