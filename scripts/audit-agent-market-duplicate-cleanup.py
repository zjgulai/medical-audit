#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import cast

INPUT_FORMAT = "medical-audit-agent-market-inventory-v1"
REPORT_FORMAT = "medical-audit-agent-market-duplicate-cleanup-dry-run-v1"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class InventoryError(RuntimeError):
    pass


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "emit-sql":
            output = _inventory_sql()
        elif args.command == "analyze":
            inventory = _load_json(Path(args.input_json))
            output = json.dumps(
                _analyze_inventory(inventory),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n"
        else:
            raise InventoryError("missing command")
        _write_output(output, str(args.output))
    except InventoryError as exc:
        print(f"agent duplicate cleanup dry-run failed: {exc}", file=sys.stderr)
        return 2
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only audit_agents inventory query or analyze its JSON output. "
            "This tool never emits or executes database mutation SQL."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    emit_sql = subparsers.add_parser(
        "emit-sql", help="Emit strict read-only PostgreSQL inventory SQL"
    )
    emit_sql.add_argument("--output", default="-")
    analyze = subparsers.add_parser(
        "analyze", help="Build a deterministic cleanup dry-run manifest"
    )
    analyze.add_argument("--input-json", required=True)
    analyze.add_argument("--output", default="-")
    return parser.parse_args()


def _inventory_sql() -> str:
    return """BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY DEFERRABLE;
SELECT jsonb_build_object(
  'format', 'medical-audit-agent-market-inventory-v1',
  'source', 'production-readonly-sql',
  'transaction_read_only', current_setting('transaction_read_only'),
  'agents', COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'agent_id', a.id::text,
        'agent_key', a.agent_key,
        'created_by', a.created_by,
        'project_name', a.project_name,
        'status', a.status,
        'metadata', a.metadata,
        'created_at', a.created_at,
        'updated_at', a.updated_at,
        'invocation_count', COALESCE(inv.invocation_count, 0)
      ) ORDER BY a.agent_key
    ) FILTER (WHERE a.id IS NOT NULL),
    '[]'::jsonb
  )
)
FROM public.audit_agents AS a
LEFT JOIN (
  SELECT agent_id, count(*)::bigint AS invocation_count
  FROM public.audit_agent_invocations
  WHERE agent_id IS NOT NULL
  GROUP BY agent_id
) AS inv ON inv.agent_id = a.id
WHERE a.metadata ->> 'source' = 'agent-market';
COMMIT;
"""


def _analyze_inventory(payload: Mapping[str, object]) -> dict[str, object]:
    if payload.get("format") != INPUT_FORMAT:
        raise InventoryError("inventory format is invalid")
    if payload.get("transaction_read_only") != "on":
        raise InventoryError("inventory transaction_read_only must be on")
    source = _required_text(payload.get("source"), "source")
    raw_agents = payload.get("agents")
    if not isinstance(raw_agents, list):
        raise InventoryError("inventory agents must be a list")

    rows = [_normalize_agent(item, index=index) for index, item in enumerate(raw_agents)]
    agent_ids = [row["agent_id"] for row in rows]
    agent_keys = [row["agent_key"] for row in rows]
    if len(set(agent_ids)) != len(agent_ids):
        raise InventoryError("inventory contains duplicate agent_id values")
    if len(set(agent_keys)) != len(agent_keys):
        raise InventoryError("inventory contains duplicate agent_key values")

    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        identity = cast(tuple[str, str, str], row.pop("_identity"))
        grouped[identity].append(row)

    duplicate_groups: list[dict[str, object]] = []
    active_duplicate_group_count = 0
    excess_row_count = 0
    for identity, candidates in sorted(grouped.items(), key=lambda item: item[0]):
        if len(candidates) < 2:
            continue
        active_count = sum(candidate["status"] == "active" for candidate in candidates)
        if active_count > 1:
            active_duplicate_group_count += 1
        excess_row_count += len(candidates) - 1
        survivor = sorted(candidates, key=_survivor_sort_key)[0]
        survivor_id = str(survivor["agent_id"])
        candidate_reports = [_public_candidate(candidate) for candidate in candidates]
        actions = []
        for candidate in sorted(candidates, key=lambda item: str(item["agent_key"])):
            is_survivor = str(candidate["agent_id"]) == survivor_id
            action = (
                "keep-market-identity"
                if is_survivor
                else "detach-market-identity-and-archive"
            )
            actions.append(
                {
                    "agent_id": candidate["agent_id"],
                    "agent_key": candidate["agent_key"],
                    "action": action,
                    "preserve_agent_row": True,
                    "preserve_invocation_history": True,
                }
            )
        duplicate_groups.append(
            {
                "identity": {
                    "fingerprint": _identity_fingerprint(identity),
                    "template_id": identity[2],
                },
                "row_count": len(candidates),
                "active_row_count": active_count,
                "survivor": _public_candidate(survivor),
                "candidates": sorted(candidate_reports, key=lambda item: str(item["agent_key"])),
                "proposed_actions": actions,
            }
        )

    report = {
        "format": REPORT_FORMAT,
        "status": "pass",
        "decision": "dry-run-only",
        "evidence_grade": "L2-fixture-or-dry-run",
        "source": source,
        "database_write": False,
        "production_unchanged": True,
        "sql_write_statements_emitted": False,
        "cleanup_write_authorization_required": bool(duplicate_groups),
        "survivor_policy": [
            "prefer-active-status",
            "highest-invocation-count",
            "newest-updated-at",
            "newest-created-at",
            "lexicographically-smallest-agent-key",
        ],
        "identity_contract": ["created_by", "trimmed-project_name", "metadata.template_id"],
        "summary": {
            "market_row_count": len(rows),
            "active_market_row_count": sum(row["status"] == "active" for row in rows),
            "identity_group_count": len(grouped),
            "ambiguous_identity_group_count": len(duplicate_groups),
            "active_duplicate_group_count": active_duplicate_group_count,
            "excess_row_count": excess_row_count,
        },
        "duplicate_groups": duplicate_groups,
    }
    _validate_report(report)
    return report


def _normalize_agent(value: object, *, index: int) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InventoryError(f"agents[{index}] must be an object")
    row = cast(dict[str, object], value)
    agent_id = _required_text(row.get("agent_id"), f"agents[{index}].agent_id")
    agent_key = _required_text(row.get("agent_key"), f"agents[{index}].agent_key")
    created_by = _required_text(row.get("created_by"), f"agents[{index}].created_by")
    project_name = _required_text(row.get("project_name"), f"agents[{index}].project_name")
    status = _required_text(row.get("status"), f"agents[{index}].status").lower()
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        raise InventoryError(f"agents[{index}].metadata must be an object")
    if _required_text(metadata.get("source"), f"agents[{index}].metadata.source") != "agent-market":
        raise InventoryError(f"agents[{index}] is outside the agent-market inventory scope")
    template_id = _required_text(
        metadata.get("template_id"), f"agents[{index}].metadata.template_id"
    )
    invocation_count = row.get("invocation_count")
    if (
        isinstance(invocation_count, bool)
        or not isinstance(invocation_count, int)
        or invocation_count < 0
    ):
        raise InventoryError(f"agents[{index}].invocation_count must be a non-negative integer")
    created_at = _required_timestamp(row.get("created_at"), f"agents[{index}].created_at")
    updated_at = _required_timestamp(row.get("updated_at"), f"agents[{index}].updated_at")
    return {
        "agent_id": agent_id,
        "agent_key": agent_key,
        "status": status,
        "invocation_count": invocation_count,
        "created_at": created_at,
        "updated_at": updated_at,
        "_identity": (created_by, project_name.strip(), template_id),
    }


def _survivor_sort_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        0 if row["status"] == "active" else 1,
        -int(cast(int, row["invocation_count"])),
        -cast(datetime, row["updated_at"]).timestamp(),
        -cast(datetime, row["created_at"]).timestamp(),
        str(row["agent_key"]),
    )


def _public_candidate(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "agent_id": row["agent_id"],
        "agent_key": row["agent_key"],
        "status": row["status"],
        "invocation_count": row["invocation_count"],
        "created_at": cast(datetime, row["created_at"]).isoformat(),
        "updated_at": cast(datetime, row["updated_at"]).isoformat(),
    }


def _identity_fingerprint(identity: Sequence[str]) -> str:
    return hashlib.sha256("\0".join(identity).encode("utf-8")).hexdigest()


def _validate_report(report: Mapping[str, object]) -> None:
    groups = report.get("duplicate_groups")
    if not isinstance(groups, list):
        raise InventoryError("dry-run report duplicate_groups is invalid")
    for group in groups:
        if not isinstance(group, dict):
            raise InventoryError("dry-run report duplicate group is invalid")
        identity = group.get("identity")
        if not isinstance(identity, dict) or not SHA256_PATTERN.fullmatch(
            str(identity.get("fingerprint", ""))
        ):
            raise InventoryError("dry-run identity fingerprint is invalid")
        actions = group.get("proposed_actions")
        if not isinstance(actions, list) or len(actions) != int(group.get("row_count", 0)):
            raise InventoryError("dry-run proposed action set is incomplete")


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InventoryError(f"{field} must be a non-empty string")
    return value.strip()


def _required_timestamp(value: object, field: str) -> datetime:
    text = _required_text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InventoryError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise InventoryError(f"{field} must include a timezone")
    return parsed


def _load_json(path: Path) -> Mapping[str, object]:
    if not path.is_file():
        raise InventoryError(f"inventory JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise InventoryError(f"inventory JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise InventoryError("inventory JSON root must be an object")
    return cast(Mapping[str, object], payload)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _write_output(content: str, output: str) -> None:
    if output == "-":
        sys.stdout.write(content)
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
