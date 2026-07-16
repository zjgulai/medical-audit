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
  --allow-audit-log-writes \\
  --confirm-production-write audit.lute-tlz-dddd.top \\
  --output tmp/outputs/production-frontend-acceptance-latest.json \\
  --screenshot-dir tmp/screenshots/production-frontend-acceptance-latest \\
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
    assert "(!requireScreenshot || hasValidPngScreenshot(check.screenshot))" in gate_text
