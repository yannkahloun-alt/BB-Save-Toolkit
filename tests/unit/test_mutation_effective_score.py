from tests.mutation.effective_score import parse_report

def test_parse_mutation_report_summary():
    text = """total jobs: 125
complete: 125 (100.00%)
surviving mutants: 1 (0.80%)
"""
    assert parse_report(text) == (125, 1)


from tests.mutation.effective_score import outcome_rows

def test_outcome_rows_lists_incompetent_operator():
    text = """bbtool\\projection\\scoring.py core/AddNot 2
worker outcome: WorkerOutcome.NORMAL, test outcome: TestOutcome.INCOMPETENT
bbtool\\projection\\scoring.py core/NumberReplacer 1
worker outcome: WorkerOutcome.NORMAL, test outcome: TestOutcome.KILLED
total jobs: 2
complete: 2 (100.00%)
surviving mutants: 0 (0.00%)
"""
    rows = outcome_rows(text)
    assert rows[0]["operator"] == "core/AddNot 2"
    assert rows[0]["outcome"] == "INCOMPETENT"
    assert rows[1]["outcome"] == "KILLED"
