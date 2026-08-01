from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from importlib.resources import files

from medical_audit_kb.contract_audit.prompt import (
    CONTRACT_AUDIT_AGENT_ID,
    CONTRACT_AUDIT_AGENT_PROMPT,
    CONTRACT_AUDIT_PROMPT_VERSION_KEY,
)

CATALOG_CONTRACT_VERSION = "agent-market-catalog-v2"
REVIEWED_ENTRY_COUNT = 132


@lru_cache(maxsize=1)
def _catalog_by_id() -> dict[str, dict[str, object]]:
    payload = json.loads(
        files("medical_audit_kb.catalog")
        .joinpath("agent_catalog_reviewed_v1.json")
        .read_text(encoding="utf-8")
    )
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != REVIEWED_ENTRY_COUNT:
        raise RuntimeError(
            f"reviewed agent catalog must contain exactly {REVIEWED_ENTRY_COUNT} entries"
        )
    catalog: dict[str, dict[str, object]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise RuntimeError(f"reviewed agent catalog entry {index} is invalid")
        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            raise RuntimeError(f"reviewed agent catalog entry {index} metadata is invalid")
        template_id = str(entry.get("agent_key") or "").strip()
        prompt = str(entry.get("prompt") or "").strip()
        if not template_id or not prompt or template_id in catalog:
            raise RuntimeError(
                f"reviewed agent catalog entry {index} identity is invalid: {template_id!r}"
            )
        catalog[template_id] = {
            "id": template_id,
            "name": str(entry.get("name") or "未命名智能体"),
            "category": str(metadata.get("catalog_source_category") or "工具智能体"),
            "agent_category": str(entry.get("category") or "效率类"),
            "summary": str(
                metadata.get("catalog_intro") or metadata.get("catalog_scene") or "审计辅助智能体"
            ),
            "topic": str(entry.get("topic") or "审计辅助"),
            "project": "智能体广场",
            "knowledge_base": str(entry.get("knowledge_base") or "项目默认知识库"),
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "featured": False,
            "featured_rank": None,
            "source": "loop120-reviewed-catalog",
            "metadata": metadata,
        }
    contract_prompt_sha = hashlib.sha256(CONTRACT_AUDIT_AGENT_PROMPT.encode("utf-8")).hexdigest()
    catalog[CONTRACT_AUDIT_AGENT_ID] = {
        "id": CONTRACT_AUDIT_AGENT_ID,
        "name": "合同审计智能体",
        "category": "工具智能体",
        "agent_category": "业务类",
        "summary": (
            "上传合同后完成原生文本或 Unlimited-OCR 提取、页面证据绑定、"
            "四维风险审计并下载报告。"
        ),
        "topic": "合同审计与风险复核",
        "project": "全院审计项目",
        "knowledge_base": "合同审计知识与项目材料",
        "prompt": CONTRACT_AUDIT_AGENT_PROMPT,
        "prompt_sha256": contract_prompt_sha,
        "featured": True,
        "featured_rank": 1,
        "source": "contract-audit-v2",
        "metadata": {
            "catalog_source_category": "工具智能体",
            "catalog_contract_version": CATALOG_CONTRACT_VERSION,
            "prompt_version_key": CONTRACT_AUDIT_PROMPT_VERSION_KEY,
            "workflow": "upload->extract->page-evidence->audit->report-download",
        },
    }
    return catalog


def list_public_agent_templates() -> list[dict[str, object]]:
    items = [_public_item(item) for item in _catalog_by_id().values()]
    return sorted(
        items,
        key=lambda item: (
            not bool(item["featured"]),
            _rank(item.get("featured_rank")),
            str(item["name"]),
        ),
    )


def get_agent_template(template_id: str) -> dict[str, object] | None:
    item = _catalog_by_id().get(template_id)
    return copy.deepcopy(item) if item is not None else None


def _public_item(item: dict[str, object]) -> dict[str, object]:
    return {
        "id": item["id"],
        "name": item["name"],
        "category": item["category"],
        "summary": item["summary"],
        "topic": item["topic"],
        "project": item["project"],
        "featured": item["featured"],
        "featured_rank": item["featured_rank"],
        "prompt_sha256": item["prompt_sha256"],
        "source": item["source"],
        "template_key": item["id"],
    }


def _rank(value: object) -> int:
    return value if isinstance(value, int) else 9999
