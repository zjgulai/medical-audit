from medical_audit_kb.acceptance.reports import (
    build_acceptance_report,
    render_acceptance_report_markdown,
)
from medical_audit_kb.domain.constants import FileErrorType, IndexJobType
from medical_audit_kb.indexing.index_jobs import IndexRunSummary, ManifestIndexSnapshot
from medical_audit_kb.ingestion.pipeline import (
    PipelineFileIssue,
    PipelineRunResult,
)


def test_acceptance_report_calculates_rates_gates_and_markdown() -> None:
    run_result = PipelineRunResult(
        summary=IndexRunSummary(
            job_type=IndexJobType.FULL_REBUILD,
            index_version_key="full-rebuild-test",
            source_package_version_key="package-test",
            discovered_file_count=10,
            index_candidate_file_count=4,
            indexed_file_count=3,
            chunk_count=12,
            failed_file_count=1,
            pending_file_count=2,
            ignored_file_count=4,
        ),
        snapshot=ManifestIndexSnapshot(package_version_key="package-test", files_by_path={}),
        file_results=(),
        failed_files=(
            PipelineFileIssue(
                relative_path="医保目录/broken.pdf",
                error_type=FileErrorType.EXTRACTION_FAILED,
                error_summary="cannot parse pdf",
            ),
        ),
        pending_files=(
            PipelineFileIssue(
                relative_path="风险负面清单/scan.png",
                error_type=FileErrorType.UNSUPPORTED_TYPE,
                error_summary="unsupported-file-type",
            ),
            PipelineFileIssue(
                relative_path="全量法律/archive.zip",
                error_type=FileErrorType.UNSUPPORTED_TYPE,
                error_summary="unsupported-file-type",
            ),
        ),
    )

    report = build_acceptance_report(run_result)
    markdown = render_acceptance_report_markdown(report)

    assert report.index_success_rate == 0.75
    assert report.queue_explain_rate == 1.0
    assert report.no_silent_loss
    assert not report.passed
    assert report.failed_reason_counts == {"extraction-failed": 1}
    assert report.pending_reason_counts == {"unsupported-type": 2}
    assert "总体状态：`FAIL`" in markdown
    assert "`index_success_rate` | 75.00%" in markdown
    assert "`医保目录/broken.pdf`" in markdown


def test_acceptance_report_detects_silent_loss() -> None:
    run_result = PipelineRunResult(
        summary=IndexRunSummary(
            job_type=IndexJobType.FULL_REBUILD,
            index_version_key="full-rebuild-test",
            source_package_version_key="package-test",
            discovered_file_count=3,
            index_candidate_file_count=2,
            indexed_file_count=2,
            chunk_count=5,
            failed_file_count=0,
            pending_file_count=0,
            ignored_file_count=0,
        ),
        snapshot=ManifestIndexSnapshot(package_version_key="package-test", files_by_path={}),
        file_results=(),
        failed_files=(),
        pending_files=(),
    )

    report = build_acceptance_report(run_result)

    assert not report.no_silent_loss
    assert report.lost_file_count == 1
    assert report.gates[2].name == "no-silent-loss"
    assert not report.gates[2].passed
