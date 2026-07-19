from pathlib import Path


def test_workflow_has_one_audit_log_only_frontend_acceptance_command() -> None:
    workflow_text = Path(
        "docs/workflows/workflow-tencent-cloud-audit-deployment-stable.md"
    ).read_text(encoding="utf-8")
    section = workflow_text.split("### 7.6.1 生产前端语义验收", 1)[1].split(
        "### 7.7 增量更新 dry-run 演练", 1
    )[0]
    command = section.split("```bash\n", 1)[1].split("\n```", 1)[0]

    assert workflow_text.count("pnpm production:frontend-acceptance --") == 1
    assert command == """MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOTS=1 \\
MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOT_POLICY=all \\
pnpm production:frontend-acceptance -- \\
  --base-url https://audit.lute-tlz-dddd.top \\
  --expected-deploy-sha <APPROVED_SHA> \\
  --acceptance-run-id fa-<YYYYMMDD>t<HHMMSS>z-<8..32-lowercase-hex> \\
  --release-guard-report tmp/outputs/release-guard-s1-<STAMP>.json \\
  --allow-audit-log-writes \\
  --confirm-production-write audit.lute-tlz-dddd.top \\
  --output tmp/outputs/production-frontend-acceptance-<STAMP>.json \\
  --screenshot-dir tmp/screenshots/production-frontend-acceptance-<STAMP> \\
  --admin-role it-admin"""
    assert "audit-log-only" in section
    assert "只读前端语义验收" not in section
    assert "脚本只读" not in section

    gate_text = Path("scripts/run-production-frontend-acceptance-gate.mjs").read_text(
        encoding="utf-8"
    )
    assert (
        'summary.screenshot_capture === true && summary.screenshot_policy === "all"'
        in gate_text
    )
    assert "requireScreenshot: requireIndependentScreenshot" in gate_text
    assert (
        "hasValidPngScreenshot(check.screenshot, check.screenshot_evidence)"
        in gate_text
    )


def test_frontend_acceptance_uses_current_archive_contract_and_scopes_aborted_assets() -> None:
    script_text = Path("scripts/run-production-frontend-acceptance.mjs").read_text(
        encoding="utf-8"
    )

    assert 'requiredText: [/归档工作台/, /归档包/' in script_text
    assert "/项目档案归档/" not in script_text
    assert "ABORTABLE_STATIC_ASSET_PATH_PATTERN" in script_text
    assert "parsed.origin !== new URL(baseUrl).origin" in script_text


def test_frontend_acceptance_only_recovers_aborted_gets_with_same_url_success() -> None:
    script_text = Path("scripts/run-production-frontend-acceptance.mjs").read_text(
        encoding="utf-8"
    )

    assert "successfulResponseUrls" in script_text
    assert 'failed.error === "net::ERR_ABORTED"' in script_text
    assert "successfulResponseUrls.has(failed.url)" in script_text
    assert "recoveredAbortedRequestCount" in script_text
