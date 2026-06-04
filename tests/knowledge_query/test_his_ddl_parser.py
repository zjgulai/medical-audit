from uuid import UUID

import pytest

from medical_audit_kb.his.ddl_parser import (
    build_his_table_schema_payloads,
    his_ddl_parse_report_json,
    parse_his_ddl,
    render_his_ddl_parse_report_markdown,
)


def test_parse_his_ddl_extracts_tables_columns_keys_and_comments() -> None:
    report = parse_his_ddl(
        """
        CREATE TABLE HIS.T_VISIT (
            VISIT_ID VARCHAR2(64) NOT NULL,
            PATIENT_ID VARCHAR2(64) NOT NULL,
            VISIT_TIME DATE,
            DEPT_CODE VARCHAR2(32),
            CONSTRAINT PK_T_VISIT PRIMARY KEY (VISIT_ID)
        );
        COMMENT ON TABLE HIS.T_VISIT IS '就诊记录';
        COMMENT ON COLUMN HIS.T_VISIT.PATIENT_ID IS '患者脱敏ID';

        CREATE TABLE T_CHARGE_DETAIL (
            CHARGE_ID TEXT PRIMARY KEY,
            VISIT_ID TEXT NOT NULL,
            ITEM_CODE VARCHAR(64) COMMENT '院内项目编码',
            AMOUNT NUMERIC(12, 2) NOT NULL,
            CHARGED_AT TIMESTAMP
        );
        """
    )

    assert report.status == "pass"
    assert report.table_count == 2
    visit_table = report.tables[0]
    charge_table = report.tables[1]
    patient_column = next(column for column in visit_table.columns if column.name == "PATIENT_ID")
    charge_id_column = next(column for column in charge_table.columns if column.name == "CHARGE_ID")
    item_code_column = next(column for column in charge_table.columns if column.name == "ITEM_CODE")

    assert visit_table.table_name == "HIS.T_VISIT"
    assert visit_table.business_domain == "visit"
    assert visit_table.table_comment == "就诊记录"
    assert visit_table.primary_key_fields == ("VISIT_ID",)
    assert visit_table.time_fields == ("VISIT_TIME",)
    assert patient_column.comment == "患者脱敏ID"
    assert charge_table.business_domain == "charge_detail"
    assert charge_id_column.primary_key is True
    assert charge_id_column.nullable is False
    assert item_code_column.comment == "院内项目编码"
    assert "CHARGED_AT" in charge_table.time_fields


def test_his_ddl_parse_report_renders_json_markdown_and_table_schema_payloads() -> None:
    report = parse_his_ddl(
        """
        CREATE TABLE T_CHARGE_DETAIL (
            CHARGE_ID TEXT PRIMARY KEY,
            AMOUNT NUMERIC(12, 2) NOT NULL,
            CHARGED_AT TIMESTAMP
        );
        """
    )
    source_batch_id = UUID("11111111-1111-4111-8111-111111111111")

    payloads = build_his_table_schema_payloads(
        report,
        source_batch_id=source_batch_id,
        batch_key="his-batch-0001",
    )
    markdown = render_his_ddl_parse_report_markdown(report, source_path="his.sql")
    report_json = his_ddl_parse_report_json(report)

    assert payloads[0].source_batch_id == source_batch_id
    assert payloads[0].schema_key.startswith("his-batch-0001-t-charge-detail-")
    assert payloads[0].table_name == "T_CHARGE_DETAIL"
    assert payloads[0].business_domain == "charge_detail"
    assert payloads[0].primary_key_fields == ["CHARGE_ID"]
    assert payloads[0].time_fields == ["CHARGED_AT"]
    assert payloads[0].field_dictionary["columns"][0]["name"] == "CHARGE_ID"
    assert "HIS DDL 解析报告" in markdown
    assert '"table_count": 1' in report_json


def test_parse_his_ddl_fails_when_no_create_table_exists() -> None:
    report = parse_his_ddl("COMMENT ON TABLE T_VISIT IS 'only comments';")

    assert report.status == "fail"
    assert report.table_count == 0
    assert report.issues[0].message == "no CREATE TABLE statements were parsed"


def test_his_table_schema_payloads_reject_failed_parse_report() -> None:
    report = parse_his_ddl("SELECT 1;")

    with pytest.raises(ValueError, match="failed DDL parse report"):
        build_his_table_schema_payloads(
            report,
            source_batch_id=UUID("11111111-1111-4111-8111-111111111111"),
            batch_key="his-batch-0001",
        )
