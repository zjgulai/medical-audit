from pathlib import Path

from medical_audit_kb.his.ddl_parser import HisDdlParseReport, parse_his_ddl
from medical_audit_kb.his.sample_quality import (
    build_his_sample_quality_report,
    his_sample_quality_report_json,
    render_his_sample_quality_report_markdown,
)


def test_his_sample_quality_report_accepts_valid_csv_against_ddl(tmp_path: Path) -> None:
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(
        sample_root / "T_CHARGE_DETAIL.csv",
        "CHARGE_ID,VISIT_ID,AMOUNT,CHARGED_AT\n"
        "C001,V001,120.50,2025-01-01 08:00:00\n"
        "C002,V001,80.00,2025-01-01 09:00:00\n",
    )

    report = build_his_sample_quality_report(sample_root, ddl_report=_ddl_report())
    markdown = render_his_sample_quality_report_markdown(report)
    report_json = his_sample_quality_report_json(report)

    assert report.status == "pass"
    assert report.table_count == 1
    assert report.total_row_count == 2
    assert report.tables[0].table_name == "T_CHARGE_DETAIL"
    assert report.tables[0].missing_expected_columns == ()
    assert report.tables[0].required_empty_counts == {}
    assert report.tables[0].duplicate_primary_key_count == 0
    assert "HIS 脱敏样本数据质量报告" in markdown
    assert '"total_row_count": 2' in report_json


def test_his_sample_quality_report_blocks_missing_empty_and_duplicate_rows(
    tmp_path: Path,
) -> None:
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(
        sample_root / "charge_detail.csv",
        "CHARGE_ID,VISIT_ID,AMOUNT\nC001,V001,120.50\nC001,,80.00\n",
    )

    report = build_his_sample_quality_report(sample_root, ddl_report=_ddl_report())
    table = report.tables[0]

    assert report.status == "fail"
    assert table.status == "fail"
    assert table.table_name == "T_CHARGE_DETAIL"
    assert table.missing_expected_columns == ("CHARGED_AT",)
    assert table.required_empty_counts == {"VISIT_ID": 1, "CHARGED_AT": 2}
    assert table.duplicate_primary_key_count == 1
    assert "missing expected columns: CHARGED_AT" in table.issues
    assert "duplicate primary keys: 1" in table.issues


def test_his_sample_quality_report_reads_jsonl_rows(tmp_path: Path) -> None:
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(
        sample_root / "T_CHARGE_DETAIL.jsonl",
        '{"CHARGE_ID":"C001","VISIT_ID":"V001","AMOUNT":"1","CHARGED_AT":"2025-01-01"}\n',
    )

    report = build_his_sample_quality_report(sample_root, ddl_report=_ddl_report())

    assert report.status == "pass"
    assert report.tables[0].file_format == "jsonl"
    assert report.tables[0].row_count == 1


def test_his_sample_quality_report_fails_when_sample_has_no_matching_ddl(
    tmp_path: Path,
) -> None:
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(sample_root / "unknown_table.csv", "ID\n1\n")

    report = build_his_sample_quality_report(sample_root, ddl_report=_ddl_report())

    assert report.status == "fail"
    assert report.tables[0].table_name == "unknown_table"
    assert report.tables[0].issues == ("sample file has no matching DDL table",)


def _ddl_report() -> HisDdlParseReport:
    return parse_his_ddl(
        """
        CREATE TABLE T_CHARGE_DETAIL (
            CHARGE_ID TEXT PRIMARY KEY,
            VISIT_ID TEXT NOT NULL,
            AMOUNT NUMERIC(12, 2) NOT NULL,
            CHARGED_AT TIMESTAMP NOT NULL
        );
        """
    )


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
