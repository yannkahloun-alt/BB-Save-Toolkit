import sqlite3

from tests.mutation.inventory_session import module_counts


def test_inventory_counts_direct_module_path_column(tmp_path):
    db = tmp_path / "session.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE work_items (job_id TEXT, module_path TEXT)")
    con.executemany(
        "INSERT INTO work_items VALUES (?, ?)",
        [
            ("1", "bbtool/app/runner.py"),
            ("2", "bbtool/app/runner.py"),
            ("3", "bbtool/projection/context.py"),
        ],
    )
    con.commit()
    con.close()

    assert module_counts(str(db)) == {
        "bbtool/app/runner.py": 2,
        "bbtool/projection/context.py": 1,
    }


def test_inventory_falls_back_to_serialized_work_item_fields(tmp_path):
    db = tmp_path / "session.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE work_items (job_id TEXT, payload TEXT)")
    con.executemany(
        "INSERT INTO work_items VALUES (?, ?)",
        [
            ("1", '{"module_path":"bbtool\\\\app\\\\cli.py","operator":"x"}'),
            ("2", 'WorkItem(module_path="bbtool/app/cli.py")'),
            ("3", 'WorkItem(module_path="bbtool/models.py")'),
        ],
    )
    con.commit()
    con.close()

    assert module_counts(str(db)) == {
        "bbtool/app/cli.py": 2,
        "bbtool/models.py": 1,
    }
