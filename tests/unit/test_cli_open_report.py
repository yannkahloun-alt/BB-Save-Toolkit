from bbtool.app.cli import parse_args


def test_open_report_is_opt_in(tmp_path):
    save = tmp_path / "test.sav"
    save.write_bytes(b"x")
    options = parse_args([str(save)])
    assert options.open_report is False


def test_open_report_flag_is_parsed(tmp_path):
    save = tmp_path / "test.sav"
    save.write_bytes(b"x")
    options = parse_args([str(save), "--open-report"])
    assert options.open_report is True
