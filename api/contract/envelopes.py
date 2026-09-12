# -*- coding: utf-8 -*-
"""契约常量与 envelope 构造器（v1.3，与 v1.2 逐字段一致）。"""
from __future__ import annotations

import uuid
from typing import Any

AGENT_ID = "financial_data_service"
EXTERNAL_AGENT_ID = "financial_data_service"
AGENT_UID = "CMAGT-000022"
AGENT_KIND = "L1_data"
AGENT_NAME = "金融数据服务"
SERVICE_VERSION = "financial-data-service-1.3.0"


def compute_envelope(status: str, tool: dict | None, warnings: list[str], errors: list[str],
                     reason: str, request_id: str = "", extra: dict | None = None) -> dict:
    """external_agent_compute_v0 信封（/v1/agent/compute）。"""
    d: dict[str, Any] = {
        "schema_version": "external_agent_compute_v0",
        "request_id": request_id or uuid.uuid4().hex,
        "agent_id": AGENT_ID,
        "external_agent_id": EXTERNAL_AGENT_ID,
        "agent_uid": AGENT_UID,
        "agent_kind": AGENT_KIND,
        "service_version": SERVICE_VERSION,
        "status": status,
        "reason_code": reason,
        "tool_result": tool,
        "warnings": warnings,
        "errors": errors,
    }
    d.update(extra or {})
    return d


def invoke_envelope(status: str, question: str, parsed: dict, tool: dict | None,
                    warnings: list[str], errors: list[str], reason: str = "ok",
                    request_id: str = "") -> dict:
    """external_agent_response_v0 信封（/v1/agent/invoke）。"""
    return {
        "schema_version": "external_agent_response_v0",
        "request_id": request_id or uuid.uuid4().hex,
        "agent_id": AGENT_ID,
        "external_agent_id": EXTERNAL_AGENT_ID,
        "agent_uid": AGENT_UID,
        "agent_kind": AGENT_KIND,
        "service_version": SERVICE_VERSION,
        "status": status,
        "reason_code": reason,
        "question": question,
        "parsed_request": parsed,
        "tool_result": tool,
        "warnings": warnings,
        "errors": errors,
    }


def resolve_envelope(query: str, ts_code: str | None, how: str, candidates: list[str],
                     asset: str | None = None) -> dict:
    """target_resolution_v1（/v1/agent/resolve）。asset 为 v1.3 新增字段，向后兼容。"""
    d = {
        "schema_version": "target_resolution_v1",
        "query": query,
        "ts_code": ts_code,
        "resolved_from": how,
        "candidates": candidates,
        "llm_used": False,
    }
    if asset is not None:
        d["asset"] = asset
    return d
