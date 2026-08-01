from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Protocol

_JOB_ID = re.compile(r"^contract-audit-[a-f0-9]{32}$")


class ContractAuditJobStore(Protocol):
    def put(self, job: dict[str, object]) -> dict[str, object]: ...

    def get(self, job_id: str) -> dict[str, object] | None: ...


class FileContractAuditJobStore:
    """Small append/update JSON store; it does not write to the product database."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._lock = Lock()

    def put(self, job: dict[str, object]) -> dict[str, object]:
        job_id = _validated_job_id(job.get("job_id"))
        payload = deepcopy(job)
        with self._lock:
            self._root.mkdir(parents=True, exist_ok=True)
            target = self._root / f"{job_id}.json"
            temporary = self._root / f".{job_id}.json.pending"
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary.replace(target)
        return deepcopy(payload)

    def get(self, job_id: str) -> dict[str, object] | None:
        normalized = _validated_job_id(job_id)
        target = self._root / f"{normalized}.json"
        if not target.is_file():
            return None
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("job_id") != normalized:
            raise ValueError("contract audit job payload is invalid")
        return payload


def _validated_job_id(value: object) -> str:
    if not isinstance(value, str) or _JOB_ID.fullmatch(value) is None:
        raise ValueError("invalid contract audit job id")
    return value
