from uuid import UUID

from medical_audit_kb.indexing.index_activation import (
    activate_index_version_to_cursor,
    rollback_index_version_to_cursor,
)


def test_activate_index_version_deactivates_matching_active_versions() -> None:
    target_id = UUID("00000000-0000-0000-0000-000000000002")
    cursor = RecordingActivationCursor(
        target_row=(target_id, "candidate-next", "openai", "kimi-for-coding", "candidate"),
        deactivated_rows=[("active-old",)],
        activated_row=("candidate-next",),
    )

    result = activate_index_version_to_cursor(cursor, "candidate-next")

    assert result.index_version_key == "candidate-next"
    assert result.vector_provider == "openai"
    assert result.vector_model == "kimi-for-coding"
    assert result.previous_status == "candidate"
    assert result.deactivated_index_version_keys == ("active-old",)
    assert cursor.queries[1][1] == (target_id, "openai", "kimi-for-coding")
    assert cursor.queries[2][1] == (target_id,)


def test_rollback_index_version_restores_inactive_version() -> None:
    target_id = UUID("00000000-0000-0000-0000-000000000003")
    cursor = RecordingActivationCursor(
        target_row=(target_id, "active-previous", "openai", "kimi-for-coding", "inactive"),
        deactivated_rows=[("active-current",)],
        activated_row=("active-previous",),
    )

    result = rollback_index_version_to_cursor(cursor, "active-previous")

    assert result.index_version_key == "active-previous"
    assert result.vector_provider == "openai"
    assert result.vector_model == "kimi-for-coding"
    assert result.previous_status == "inactive"
    assert result.deactivated_index_version_keys == ("active-current",)
    assert cursor.queries[1][1] == (target_id, "openai", "kimi-for-coding")
    assert cursor.queries[2][1] == (target_id,)


class RecordingActivationCursor:
    def __init__(
        self,
        *,
        target_row: tuple[object, ...],
        deactivated_rows: list[tuple[object, ...]],
        activated_row: tuple[object, ...],
    ) -> None:
        self._target_row = target_row
        self._deactivated_rows = deactivated_rows
        self._activated_row = activated_row
        self._stage = "target"
        self.queries: list[tuple[str, tuple[object, ...] | None]] = []

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> object:
        self.queries.append((query, params))
        return None

    def fetchone(self) -> tuple[object, ...] | None:
        if self._stage == "target":
            self._stage = "deactivate"
            return self._target_row
        return self._activated_row

    def fetchall(self) -> list[tuple[object, ...]]:
        self._stage = "activate"
        return self._deactivated_rows
