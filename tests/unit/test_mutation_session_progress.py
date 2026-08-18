import sqlite3

from tests.mutation.session_progress import session_stats


def test_session_stats_counts_work_results_as_completed_jobs(tmp_path):
    db = tmp_path / "session.sqlite"
    con = sqlite3.connect(db)
    try:
        con.execute("CREATE TABLE work_items (job_id TEXT PRIMARY KEY)")
        con.execute(
            "CREATE TABLE work_results ("
            "worker_outcome TEXT, output TEXT, test_outcome TEXT, diff TEXT, "
            "job_id TEXT PRIMARY KEY)"
        )
        con.executemany(
            "INSERT INTO work_items(job_id) VALUES (?)",
            [("a",), ("b",), ("c",), ("d",)],
        )
        con.executemany(
            "INSERT INTO work_results(worker_outcome, test_outcome, job_id) "
            "VALUES (?, ?, ?)",
            [("NORMAL", "KILLED", "a"), ("NORMAL", "SURVIVED", "b")],
        )
        con.commit()
    finally:
        con.close()

    assert session_stats(str(db)) == {"total": 4, "complete": 2}
