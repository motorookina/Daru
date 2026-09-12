# -*- coding: utf-8 -*-
"""自然语言口 /v1/agent/invoke + 标的解析口 /v1/agent/resolve（v1.3）。

缺口 4 在此落地：`_NO_TARGET_APIS` 从注册表推导（entity=None 的宏观/利率/日历表），
不再硬编码——新增宏观表自动免 target。
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from ..contract import envelopes as _env
from ..contract.resolution import (
    _resolve_target, _scan_as_of, _business_today, _target_from_question,
    _target_reason, _pick_api, _build_params, _NO_TARGET_APIS, classify_asset,
)
from ..datasource import query as _query

log = logging.getLogger("pg-ops-agent.agent_invoke")

router = APIRouter(tags=["external_agent"])

_PERIOD_APIS = {"income", "balancesheet", "cashflow", "fina_indicator", "report_rc",
                "trade_cal", "express", "forecast", "fina_audit", "namechange"}


def _d8(v) -> str:
    t = re.sub(r"[^0-9]", "", str(v or ""))
    return t[:8] if len(t) >= 8 else ""


@router.post("/v1/agent/invoke")
async def external_agent_invoke(request: Request):
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    opts = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    question = str(payload.get("query") or payload.get("question") or "").strip()
    request_id = str(payload.get("request_id") or uuid.uuid4().hex)

    as_of, as_of_err = _scan_as_of(payload, question)
    if as_of_err:
        return _env.invoke_envelope("error", question, {"as_of_error": as_of_err}, None, [],
                                    ["as_of 校验失败：%s" % as_of_err], as_of_err, request_id)
    if not as_of:
        as_of = _business_today().strftime("%Y%m%d")
        as_of_defaulted = True
    else:
        as_of_defaulted = False
    base_warnings = (["请求未给 as_of，已按今日 %s 取数" % as_of] if as_of_defaulted else [])

    raw_target = str(payload.get("target") or payload.get("ts_code") or
                     opts.get("target") or opts.get("ts_code") or "").strip()
    if raw_target:
        ts_code, how, cands = _resolve_target(raw_target)
    else:
        ts_code, how, cands, raw_target = _target_from_question(question)
    if raw_target and not ts_code:
        parsed = {"raw_target": raw_target, "resolved_from": how, "candidates": cands, "as_of": as_of}
        code = _target_reason(raw_target, how)
        return _env.invoke_envelope("abstain", question, parsed, None,
                                    base_warnings + ["标的无法唯一确定，未擅自选取"], [], code, request_id)

    api = str(opts.get("api_name") or "").strip()
    api_from = "explicit"
    if not api:
        api, hits = _pick_api(question)
        api_from = "keyword_rule"
        if not api:
            parsed = {"ts_code": ts_code, "as_of": as_of, "matched": []}
            return _env.invoke_envelope("abstain", question, parsed, None,
                                        base_warnings + ["无法从问题判定应查哪个接口，未猜测"], [],
                                        "API_NOT_DETERMINED", request_id)

    if api not in _NO_TARGET_APIS and not ts_code:
        parsed = {"ts_code": "", "as_of": as_of, "api_name": api, "resolved_from": how}
        return _env.invoke_envelope("abstain", question, parsed, None,
                                    base_warnings + ["问题需要明确 A 股或境内指数标的，未执行全市场兜底查询"], [],
                                    "TARGET_REQUIRED", request_id)

    params = _build_params(api, ts_code, as_of, opts)
    try:
        res = await run_in_threadpool(_query, api_name=api, **params)
    except Exception as e:  # noqa: BLE001
        parsed = {"api_name": api, "params": params, "ts_code": ts_code, "as_of": as_of}
        return _env.invoke_envelope("error", question, parsed, None, base_warnings,
                                    ["%s: %s" % (type(e).__name__, e)], "QUERY_FAILED", request_id)

    src = str(res.get("source") or "unknown")
    warns: list[str] = list(base_warnings)
    if src == "tushare":
        warns.append("数据来自 tushare 实时接口（库内无此数据），PIT 不成立，"
                     "不得用于回测或反前视场景")

    def _row_dict(r, _cols=(res.get("columns") or [])):
        return r if isinstance(r, dict) else dict(zip(_cols, r))

    _rows = [_row_dict(r) for r in (res.get("rows") or [])]
    _pit_ok = (src == "database")
    _data_dates: list[str] = []
    if api in _PERIOD_APIS and _rows:
        if any("ann_date" in d for d in _rows):
            _vis = [d for d in _rows if _d8(d.get("ann_date")) and _d8(d.get("ann_date")) <= as_of]
            _dropped = len(_rows) - len(_vis)
            if _dropped:
                warns.append("公告日门控：过滤 %d 行公告晚于 %s 的记录（防前视）" % (_dropped, as_of))
            _vis.sort(key=lambda d: (_d8(d.get("end_date")), _d8(d.get("ann_date"))), reverse=True)
            if not _vis:
                warns.append("公告日门控后无可见记录：该时点尚无已公告数据")
            _rows = _vis
            _data_dates = [_d8(d.get("ann_date")) for d in _vis if _d8(d.get("ann_date"))]
        else:
            _pit_ok = False
            warns.append("返回无 ann_date 列，无法核验公告日，不标记 point_in_time")
    elif _rows:
        _data_dates = [x for x in (_d8(d.get("trade_date") or d.get("end_date") or d.get("ann_date"))
                                   for d in _rows) if x]
        _bad = [x for x in _data_dates if x > as_of]
        if _bad:
            _rows = [d for d in _rows
                     if not (_d8(d.get("trade_date") or d.get("end_date") or d.get("ann_date")) > as_of)]
            _data_dates = [x for x in _data_dates if x <= as_of]
            warns.append("时点门控：过滤 %d 行晚于 %s 的记录" % (len(_bad), as_of))
    _real_data_as_of = max(_data_dates) if _data_dates else None
    n = len(_rows)
    status = "ok" if n > 0 else "partial"

    tool = {
        "schema_version": "data_bundle_v1",
        "kind": "table",
        "not_for_weighting": True,
        "agent_id": _env.AGENT_ID,
        "external_agent_id": _env.EXTERNAL_AGENT_ID,
        "agent_uid": _env.AGENT_UID,
        "target": ts_code or None,
        "as_of": as_of,
        "as_of_date": as_of,
        "data_as_of": _real_data_as_of or as_of,
        "data_as_of_is_actual": _real_data_as_of is not None,
        "point_in_time": bool(_pit_ok and n > 0),
        "source": src,
        "api_name": api,
        "columns": res.get("columns"),
        "rows": _rows,
        "row_count": n,
        "evidence": {"api_name": api, "params": params, "source": src,
                     "resolved_from": how if raw_target else "not_requested"},
    }
    parsed = {"api_name": api, "api_from": api_from, "ts_code": ts_code,
              "resolved_from": how if raw_target else "not_requested",
              "as_of": as_of, "params": params}
    return _env.invoke_envelope(status, question, parsed, tool, warns, [], "ok", request_id)


@router.get("/v1/agent/resolve")
async def resolve_target(q: str = ""):
    """标的解析独立口（纯规则，无 LLM）。歧义返回全部候选；附带 asset（v1.3 新增）。"""
    ts_code, how, cands = await run_in_threadpool(_resolve_target, q)
    asset = classify_asset(ts_code) if ts_code else None
    return _env.resolve_envelope(q, ts_code or None, how, cands, asset)
