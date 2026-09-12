# -*- coding: utf-8 -*-
"""金融数据服务智能体 v1.3 —— 契约 + 接口落地（字段驱动重设计）。

只做载荷契约与接口：/v1/agent/compute、/v1/agent/invoke、/v1/agent/resolve、/health。
取数复用 v1.2 的 new_query 内核（见 datasource.py）；不含调度器/沙箱/前端/管理面/通用查询通道。
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .contract import envelopes as _env
from .routers import agent_compute, agent_invoke

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pg-ops-agent")

app = FastAPI(title="金融数据服务智能体", version="1.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_invoke.router)
app.include_router(agent_compute.router)


def _db_ready() -> bool:
    try:
        from .datasource import query
        res = query(api_name="trade_cal", limit=1)
        return bool(res.get("row_count") or res.get("rows"))
    except Exception:  # noqa: BLE001 — 健康检查必须 fail closed。
        return False


@app.get("/healthz")
def healthz():
    """轻量存活探针：不查 DB，仅证明事件循环可响应。"""
    return {"status": "ok"}


@app.get("/health")
def health():
    """external_agent_health_v0 契约健康检查。"""
    data_ready = _db_ready()
    return {
        "schema_version": "external_agent_health_v0",
        "status": "ok" if data_ready else "degraded",
        "agent_id": _env.AGENT_ID,
        "external_agent_id": _env.EXTERNAL_AGENT_ID,
        "agent_uid": _env.AGENT_UID,
        "agent_name": _env.AGENT_NAME,
        "uid_display": "%s｜%s" % (_env.AGENT_UID, _env.AGENT_NAME),
        "version": "1.3",
        "service_version": _env.SERVICE_VERSION,
        "plane": "contract",
        "admin_plane_separated": False,
        "agent_kind": _env.AGENT_KIND,
        "supported_dimensions": ["l1"],
        "capabilities": [
            "structured_health",
            "compute_endpoint",
            "invoke_endpoint",
            "resolve_endpoint",
            "data_bundle_v1",
            "point_in_time",
            "field_driven_registry",
            "classify_asset",
        ],
        "input_modes": ["structured", "natural_language"],
        "output_modes": ["external_agent_compute_v0", "external_agent_response_v0",
                         "data_bundle_v1", "target_resolution_v1"],
        "llm_configured": False,
        "tools_configured": True,
        "data_ready": data_ready,
        "max_concurrency": 4,
        "timeout_seconds": 30,
        "warnings": [] if data_ready else ["database unavailable（数据接入层复用 v1.2 内核，需 v1.2 可连库）"],
    }
