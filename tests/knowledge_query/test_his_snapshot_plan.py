from pathlib import Path
from uuid import UUID

from medical_audit_kb.his.ddl_parser import HisDdlParseReport, parse_his_ddl
from medical_audit_kb.his.sample_quality import (
    HisSampleQualityReport,
    build_his_sample_quality_report,
    his_sample_quality_report_json,
)
from medical_audit_kb.his.snapshot_plan import (
    build_his_snapshot_plan,
    his_snapshot_plan_json,
    load_his_sample_quality_report_json,
    render_his_snapshot_plan_markdown,
)


def test_his_snapshot_plan_builds_audit_data_snapshot_payload(tmp_path: Path) -> None:
    quality_report = _passing_quality_report(tmp_path)
    project_id = UUID("11111111-1111-4111-8111-111111111111")

    plan = build_his_snapshot_plan(
        quality_report,
        project_id=project_id,
        snapshot_key="snapshot-his-0001",
        source_batch_key="his-batch-0001",
        time_range={"from": "2025-01-01", "to": "2025-01-31"},
    )
    markdown = render_his_snapshot_plan_markdown(plan)
    plan_json = his_snapshot_plan_json(plan)

    assert plan.status == "pass"
    assert plan.can_create_snapshot is True
    assert plan.checksum is not None
    assert plan.checksum.startswith("sha256:")
    assert plan.row_counts == {"T_CHARGE_DETAIL": 1}
    assert plan.audit_data_snapshot_payload is not None
    assert plan.audit_data_snapshot_payload.project_id == project_id
    assert plan.audit_data_snapshot_payload.snapshot_key == "snapshot-his-0001"
    assert plan.audit_data_snapshot_payload.source_batch_key == "his-batch-0001"
    assert plan.audit_data_snapshot_payload.row_counts == {"T_CHARGE_DETAIL": 1}
    assert plan.audit_data_snapshot_payload.checksum == plan.checksum
    assert "HIS 数据快照计划" in markdown
    assert '"can_create_snapshot": true' in plan_json


def test_his_snapshot_plan_blocks_failed_quality_report(tmp_path: Path) -> None:
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(sample_root / "T_CHARGE_DETAIL.csv", "CHARGE_ID,VISIT_ID,AMOUNT\nC001,,1\n")
    quality_report = build_his_sample_quality_report(sample_root, ddl_report=_ddl_report())

    plan = build_his_snapshot_plan(
        quality_report,
        project_id=UUID("11111111-1111-4111-8111-111111111111"),
        snapshot_key="snapshot-his-0001",
        source_batch_key="his-batch-0001",
    )

    assert plan.status == "fail"
    assert plan.can_create_snapshot is False
    assert plan.audit_data_snapshot_payload is None
    assert plan.checksum is None
    assert "sample quality report is not PASS" in plan.issues
    assert "table quality is not PASS: T_CHARGE_DETAIL" in plan.issues


def test_his_snapshot_plan_loads_sample_quality_report_json(tmp_path: Path) -> None:
    quality_report = _passing_quality_report(tmp_path)
    quality_report_json = tmp_path / "his-sample-quality.json"
    _write_text(quality_report_json, his_sample_quality_report_json(quality_report))

    loaded_report = load_his_sample_quality_report_json(quality_report_json)

    assert loaded_report.status == "pass"
    assert loaded_report.total_row_count == 1


def _passing_quality_report(tmp_path: Path) -> HisSampleQualityReport:
    sample_root = tmp_path / "samples"
    sample_root.mkdir(exist_ok=True)
    _write_text(
        sample_root / "T_CHARGE_DETAIL.csv",
        "CHARGE_ID,VISIT_ID,AMOUNT,CHARGED_AT\nC001,V001,1,2025-01-01\n",
    )
    return build_his_sample_quality_report(sample_root, ddl_report=_ddl_report())


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
