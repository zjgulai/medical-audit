import json
import subprocess
from pathlib import Path


def test_serve_chat_workbench_script_is_valid_and_does_not_store_secret() -> None:
    script_path = Path("scripts/serve-chat-workbench.sh")

    result = subprocess.run(
        ["bash", "-n", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "KIMI_API_KEY" in script_text
    assert "sk-" not in script_text


def test_capture_chat_workbench_visual_baseline_script_is_valid() -> None:
    script_path = Path("scripts/capture-chat-workbench-visual-baseline.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "tmp/screenshots" in script_text
    assert "tmp/outputs/knowledge-query-chat-visual-baseline-latest.json" in script_text
    assert "desktop" in script_text
    assert "mobile" in script_text
    assert "可追溯回答" in script_text
    assert "证据卷宗" in script_text
    assert "人工复核清单" in script_text
    assert "创建复核任务" in script_text
    assert "导出 Markdown 底稿" in script_text
    assert "导出 JSON 记录" in script_text


def test_serve_chat_workbench_container_script_is_valid_and_does_not_store_secret() -> None:
    script_path = Path("scripts/serve-chat-workbench-container.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "KIMI_API_KEY" in script_text
    assert "sk-" not in script_text
    assert "urllib.request" in script_text


def test_run_production_e2e_smoke_script_is_valid_and_does_not_store_secret() -> None:
    script_path = Path("scripts/run-production-e2e-smoke.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "tmp/outputs/production-e2e-smoke-latest.json" in script_text
    assert "tls-certificate-san" in script_text
    assert "query-api-with-citations" in script_text
    assert "citation-preview" in script_text
    assert "review-flow-create-update-export" in script_text
    assert "--include-review-write" in script_text
    assert "Default is read-only production smoke" in script_text
    assert "edge-regression" in script_text


def test_run_audit_log_archive_audit_script_is_valid_and_does_not_store_secret() -> None:
    script_path = Path("scripts/run-audit-log-archive-audit.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "audit-log-archive-audit" in script_text
    assert "MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET" in script_text
    assert "MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_ROOT" in script_text
    assert "MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_REPORT_DIR" in script_text
    assert "latest_json_report" in script_text


def test_classify_knowledge_pending_files_script_writes_reports(tmp_path: Path) -> None:
    script_path = Path("scripts/classify-knowledge-pending-files.py")
    source_root = tmp_path / "source"
    pending_file = tmp_path / "pending_files.jsonl"
    output = tmp_path / "pending-report.md"
    json_output = tmp_path / "pending-report.json"
    _write_bytes(source_root / "风险负面清单" / "scan.png", b"png")
    _write_bytes(source_root / "全量法律.zip", b"zip")
    pending_file.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "relative_path": "风险负面清单/scan.png",
                        "error_type": "unsupported-type",
                        "error_summary": "unsupported-file-type",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "relative_path": "全量法律.zip",
                        "error_type": "unsupported-type",
                        "error_summary": "unsupported-file-type",
                    },
                    ensure_ascii=False,
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--pending-file",
            str(pending_file),
            "--source-root",
            str(source_root),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    report_text = output.read_text(encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert body["summary"]["total_pending_files"] == 2
    assert body["summary"]["source_missing_count"] == 0
    assert body["counts"]["by_category"] == {
        "archive-unpack-required": 1,
        "ocr-required-image": 1,
    }
    assert body["counts"]["by_source_collection"] == {
        "root": 1,
        "风险负面清单": 1,
    }
    assert "知识库 pending 文件分类报告" in report_text
    assert "scan.png" in report_text
    assert "全量法律.zip" in report_text


def test_audit_index_rollback_readiness_allows_inactive_target(tmp_path: Path) -> None:
    script_path = Path("scripts/audit-index-rollback-readiness.py")
    versions_file = tmp_path / "versions.json"
    output = tmp_path / "rollback-readiness.md"
    json_output = tmp_path / "rollback-readiness.json"
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                },
                {
                    "version_key": "full-rebuild-previous",
                    "status": "inactive",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 480,
                    "chunk_count": 48000,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--versions-file",
            str(versions_file),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stderr
    assert body["status"] == "pass"
    assert body["safe_to_execute_rollback_rehearsal"] is True
    assert body["summary"]["rollback_target_count"] == 1
    assert "知识库索引回滚就绪审计报告" in output.read_text(encoding="utf-8")


def test_audit_index_rollback_readiness_blocks_without_inactive_target(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/audit-index-rollback-readiness.py")
    versions_file = tmp_path / "versions.json"
    output = tmp_path / "rollback-readiness.md"
    json_output = tmp_path / "rollback-readiness.json"
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--versions-file",
            str(versions_file),
            "--expected-active-key",
            "full-rebuild-current",
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert body["status"] == "blocked"
    assert body["safe_to_execute_rollback_rehearsal"] is False
    assert body["blocking_reasons"] == ["no-inactive-rollback-target-for-active-provider-model"]
    assert body["summary"]["rollback_target_count"] == 0


def test_audit_index_candidate_release_readiness_allows_new_candidate_key(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/audit-index-candidate-release-readiness.py")
    import_result_file = tmp_path / "pgvector-import-dry-run.json"
    versions_file = tmp_path / "versions.json"
    output = tmp_path / "candidate-release-readiness.md"
    json_output = tmp_path / "candidate-release-readiness.json"
    import_result_file.write_text(
        json.dumps(_candidate_import_result("full-rebuild-next"), ensure_ascii=False),
        encoding="utf-8",
    )
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--import-result-json",
            str(import_result_file),
            "--versions-file",
            str(versions_file),
            "--expected-active-key",
            "full-rebuild-current",
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stderr
    assert body["status"] == "pass"
    assert body["safe_to_execute_candidate_write"] is True
    assert body["candidate"]["candidate_index_version_key"] == "full-rebuild-next"
    assert body["evidence_grade"] == "L2-fixture-or-dry-run"
    assert "知识库 candidate 发布就绪审计报告" in output.read_text(encoding="utf-8")


def test_audit_index_candidate_release_readiness_blocks_existing_candidate_key(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/audit-index-candidate-release-readiness.py")
    import_result_file = tmp_path / "pgvector-import-dry-run.json"
    versions_file = tmp_path / "versions.json"
    output = tmp_path / "candidate-release-readiness.md"
    json_output = tmp_path / "candidate-release-readiness.json"
    import_result_file.write_text(
        json.dumps(_candidate_import_result("full-rebuild-current"), ensure_ascii=False),
        encoding="utf-8",
    )
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--import-result-json",
            str(import_result_file),
            "--versions-file",
            str(versions_file),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert body["status"] == "blocked"
    assert body["safe_to_execute_candidate_write"] is False
    assert "candidate-index-version-key-already-exists" in body["blocking_reasons"]
    assert "candidate-index-version-key-matches-active" in body["blocking_reasons"]


def test_audit_index_candidate_release_readiness_blocks_chunk_id_collision(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/audit-index-candidate-release-readiness.py")
    import_result_file = tmp_path / "pgvector-import-dry-run.json"
    versions_file = tmp_path / "versions.json"
    candidate_chunks_file = tmp_path / "candidate-chunks.jsonl"
    active_chunks_file = tmp_path / "active-chunks.jsonl"
    output = tmp_path / "candidate-release-readiness.md"
    json_output = tmp_path / "candidate-release-readiness.json"
    import_result_file.write_text(
        json.dumps(_candidate_import_result("full-rebuild-next"), ensure_ascii=False),
        encoding="utf-8",
    )
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "source_package_version_key": "source-package-current",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(candidate_chunks_file, [{"chunk_id": "chunk-shared"}])
    _write_jsonl(active_chunks_file, [{"chunk_id": "chunk-shared"}])

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--import-result-json",
            str(import_result_file),
            "--versions-file",
            str(versions_file),
            "--candidate-chunks-file",
            str(candidate_chunks_file),
            "--active-chunks-file",
            str(active_chunks_file),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert body["status"] == "blocked"
    assert "candidate-chunk-id-collides-with-active-package" in body["blocking_reasons"]
    assert body["chunk_collision_check"]["collision_count"] == 1
    assert body["chunk_collision_check"]["collision_samples"] == ["chunk-shared"]


def _candidate_import_result(index_version_key: str) -> dict[str, object]:
    return {
        "mode": "dry-run",
        "executed": False,
        "success": True,
        "index_version_status": "candidate",
        "manifest": {
            "ready_for_write": True,
            "source_document_count": 486,
            "document_chunk_count": 48985,
            "chunk_embedding_count": 48985,
            "failed_file_count": 0,
            "pending_file_count": 13,
            "source_file_missing_count": 0,
            "invalid_source_metadata_count": 0,
            "plan": {
                "expected_embedding_provider": "openai",
                "expected_embedding_model": "kimi-for-coding",
                "summary": {
                    "index_version_key": index_version_key,
                    "source_package_version_key": "source-package-next",
                    "embedding_provider": "openai",
                    "embedding_model": "kimi-for-coding",
                },
            },
        },
    }


def _write_bytes(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path
