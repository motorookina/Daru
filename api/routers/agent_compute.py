# -*- coding: utf-8 -*-
"""结构化查询口 /v1/agent/compute（v1.3 字段驱动重设计）。

与 v1.2 的差异：字段不再 1:1 硬编码到表，而是
    target → classify_asset → asset
    field  → resolve_one(field, asset) → 表
    family → 决定取数通道 + 三时点标注
缺口 3（event 族时点/新鲜度）在本文件落地。
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from ..contract import envelopes as _env
from ..contract.registry import (DATASET, FIELD_DICT, PRIMARY, Family,
                                 DATASET_HISTORICAL, STATIC_ONLY_APIS)
from ..contract.resolution import (_resolve_target, _scan_as_of, _business_today,
                                   _target_reason, classify_asset, resolve_one, desc)
from ..datasource import fetch as _fetch, query as _query

log = logging.getLogger("pg-ops-agent.agent_compute")

router = APIRouter(tags=["external_agent"])

DEFAULT_FIELDS = ["close", "pct_chg", "pe_ttm", "pb", "total_mv", "turnover_rate",
                  "name", "industry"]

# FD-DIR-03: 登记派生算子（percentile_ops_v1）
ALLOWED_OPS: set = {"pe_ttm_percentile", "pb_percentile", "ps_ttm_percentile"}
KNOWN_REQUEST_KEYS = {
    "target", "ts_code", "code", "fields", "as_of", "as_of_date", "query_date",
    "date", "trade_date", "target_date", "request_id", "options", "schema_version",
    "external_agent_id", "agent_id", "question", "horizon_days", "derived",
}
STATIC_CURRENT_TOLERANCE_DAYS = 30

_FRESHNESS_POLICY_ID = "fdata_freshness_policy_v2"
_QUOTE_TZ = "Asia/Shanghai"
_QUOTE_CLOSE = "15:00"
_QUOTE_AVAIL_CUTOFF = "1800"


def _d8(v) -> str:
    t = re.sub(r"[^0-9]", "", str(v or ""))
    return t[:8] if len(t) >= 8 else ""


def _shift(d: str, days: int) -> str:
    return (datetime.strptime(d, "%Y%m%d") + timedelta(days=days)).strftime("%Y%m%d")


def _l1p0_unknown_params(payload: dict) -> list:
    if not isinstance(payload, dict):
        return []
    return sorted(k for k in payload.keys() if k not in KNOWN_REQUEST_KEYS)


def _l1p0_is_historical_request(as_of: str, today_compact: str) -> bool:
    a = str(as_of or "").replace("-", "")[:8]
    if not (a and a.isdigit() and len(a) == 8 and today_compact):
        return False
    try:
        d1 = datetime.strptime(a, "%Y%m%d")
        d0 = datetime.strptime(today_compact, "%Y%m%d")
    except Exception:
        return False
    return (d0 - d1).days > STATIC_CURRENT_TOLERANCE_DAYS


# ══════════════════════════ 取数通道（按 family）═════════════════════════════

def _fetch_daily_like(table: str, ts_code: str, as_of: str) -> tuple[dict, str, str]:
    """daily 族：向前吸附到 as_of 当日或之前最近一个交易日。只能向前不能向后。"""
    meta = DATASET[table]
    payload, src = _fetch(table, ts_code=ts_code, start_date=_shift(as_of, -20),
                          end_date=as_of, limit=40)
    colidx = {c: i for i, c in enumerate(payload["columns"])}
    ti = colidx.get(meta["time"])
    rows = payload["rows"]
    if ti is not None:
        rows = sorted(rows, key=lambda r: str(r[ti] or ""))
        rows = [r for r in rows if str(r[ti]).replace("-", "") <= as_of]
    if not rows:
        raise RuntimeError("%s 在 %s 及之前无数据" % (table, as_of))
    last = rows[-1]
    data_as_of = _d8(last[ti]) if ti is not None else as_of
    return ({"columns": payload["columns"], "row": last}, src, data_as_of)


def _fetch_fina(table: str, ts_code: str, as_of: str) -> tuple[dict, str, str]:
    """period 族：按公告日 pit[1] 门控（防前视）。"""
    meta = DATASET[table]
    obs_col, avl_col, _delay = meta.get("pit", ("end_date", "ann_date", 0))
    payload, src = _fetch(table, ts_code=ts_code, start_date=_shift(as_of, -900),
                          end_date=as_of, limit=40)
    ci = {c: i for i, c in enumerate(payload["columns"])}
    ai = ci.get(avl_col)
    oi = ci.get(obs_col)
    rows = payload["rows"]
    if ai is not None:
        rows = [r for r in rows if r[ai] and _d8(r[ai]) <= as_of]
    if not rows:
        raise RuntimeError("%s 在公告日 <= %s 内无数据" % (table, as_of))
    rows = sorted(rows, key=lambda r: (str(r[oi] or "") if oi is not None else "",
                                       str(r[ai] or "") if ai is not None else ""))
    last = rows[-1]
    data_as_of = _d8(last[ai]) if ai is not None else as_of
    return ({"columns": payload["columns"], "row": last}, src, data_as_of)


def _fetch_event(table: str, ts_code: str, as_of: str) -> tuple[dict, str, str]:
    """event 族：按事件/生效日 pit[0] 门控，可见日 pit[1] 决定 visible。"""
    meta = DATASET[table]
    obs_col, avl_col, _delay = meta.get("pit", (meta["time"], None, 0))
    payload, src = _fetch(table, ts_code=ts_code, limit=100)
    ci = {c: i for i, c in enumerate(payload["columns"])}
    oi = ci.get(obs_col)
    rows = payload["rows"]
    if oi is not None:
        rows = [r for r in rows if r[oi] and _d8(r[oi]) <= as_of]
    if not rows:
        raise RuntimeError("%s 在事件日 <= %s 内无数据" % (table, as_of))
    rows = sorted(rows, key=lambda r: str(r[oi] or "") if oi is not None else "")
    last = rows[-1]
    data_as_of = _d8(last[oi]) if oi is not None else as_of
    return ({"columns": payload["columns"], "row": last}, src, data_as_of)


def _fetch_static(table: str, ts_code: str) -> tuple[dict, str]:
    payload, src = _fetch(table, ts_code=ts_code, limit=5)
    if not payload["rows"]:
        raise RuntimeError("%s 无 %s 记录" % (table, ts_code))
    return ({"columns": payload["columns"], "row": payload["rows"][0]}, src)


def _fetch_table(table: str, ts_code: str, as_of: str):
    """按 family 分发到取数通道。返回 (got, src, data_as_of)。"""
    fam = DATASET[table]["family"]
    if fam == Family.DAILY:
        return _fetch_daily_like(table, ts_code, as_of)
    if fam == Family.PERIOD:
        return _fetch_fina(table, ts_code, as_of)
    if fam == Family.EVENT:
        return _fetch_event(table, ts_code, as_of)
    got, src = _fetch_static(table, ts_code)
    return got, src, as_of


# ══════════════════════════ 三时点标注 ══════════════════════════

def _timepoint(meta: dict, got: dict, daof: str) -> tuple[str | None, str | None, str | None]:
    """返回 (observed_at, available_at, timepoint_reason)。"""
    fam = meta["family"]
    if fam == Family.DAILY:
        return daof, daof, None
    if fam in (Family.PERIOD, Family.EVENT):
        obs_col, avl_col, _delay = meta.get("pit", (meta["time"], None, 0))
        ci = {c: i for i, c in enumerate(got["columns"])}
        row = got["row"]
        obs = _d8(row[ci[obs_col]]) if obs_col in ci and row[ci[obs_col]] else None
        avl = None
        if avl_col and avl_col in ci and row[ci[avl_col]]:
            avl = _d8(row[ci[avl_col]])
        why = None
        if not avl:
            why = "缺可见日(%s):不得用请求日/抓取日/报告期回填可见日(FD-DIR-01§二.5)" % (avl_col or "pit[1]")
        return obs, avl, why
    # static
    return None, None, "静态当前快照:无观测/可见时点(FD-DIR-01§二.5)"


# ══════════════════════════ 字段收集 ══════════════════════════

def _collect(ts_code: str, as_of: str, fields: list[str], asset: str) -> tuple[dict, list, list, list, dict]:
    by_table: dict[str, list[str]] = {}
    unknown: list[str] = []
    for f in fields:
        if f not in FIELD_DICT:
            unknown.append(f)
            continue
        t = resolve_one(f, asset)
        if t is None:
            unknown.append(f)   # 该资产下无此字段，或主表并列歧义
            continue
        by_table.setdefault(t, []).append(f)

    values, missing, evidence, srcs = {}, list(unknown), [], {}
    for table, fs in by_table.items():
        meta = DATASET[table]
        try:
            got, src, daof = _fetch_table(table, ts_code, as_of)
        except Exception as e:  # noqa: BLE001
            missing.extend(fs)
            evidence.append({"api_name": table, "status": "failed",
                             "reason": str(e)[:180], "fields": fs})
            continue
        srcs[table] = src
        _tp_obs, _tp_avl, _tp_why = _timepoint(meta, got, daof)
        for f in fs:
            phys, unit = desc(f, table)
            ci = {c: i for i, c in enumerate(got["columns"])}
            i = ci.get(phys)
            v = got["row"][i] if i is not None else None
            if v is None:
                missing.append(f)
                continue
            values[f] = {"value": v, "unit": unit, "source": table, "field": phys,
                         "data_as_of": daof, "adj_type": "none" if table == "daily" else None,
                         "observed_at": _tp_obs, "available_at": _tp_avl,
                         "timepoint_reason": _tp_why}
        _pit_ok = (src == "database") and DATASET_HISTORICAL.get(table, False)
        evidence.append({"api_name": table, "status": "ok", "source": src,
                         "data_as_of": daof, "fields": fs,
                         "point_in_time": _pit_ok,
                         "dataset_has_history": DATASET_HISTORICAL.get(table, False),
                         "pit_basis": ("库内历史分区" if _pit_ok else
                                       ("静态当前快照,无历史版本" if table in STATIC_ONLY_APIS
                                        else "非库内来源"))})
    return values, missing, evidence, unknown, srcs


# ══════════════════════════ 新鲜度 ══════════════════════════

def _last_open_day(as_of: str):
    try:
        res = _query(api_name="trade_cal", exchange="SSE", is_open="1",
                     start_date=_shift(as_of, -25), end_date=as_of, limit=30)
        cix = {c: i for i, c in enumerate(res.get("columns") or [])}
        di = cix.get("cal_date")
        if di is None:
            return None
        days = sorted(_d8(r[di]) for r in (res.get("rows") or []) if r[di])
        days = [d for d in days if d <= as_of]
        return days[-1] if days else None
    except Exception:  # noqa: BLE001
        return None


def _expected_fina_period(as_of: str) -> str:
    y, md = int(as_of[:4]), as_of[4:8]
    if md >= "1031":
        return "%d0930" % y
    if md >= "0831":
        return "%d0630" % y
    if md >= "0430":
        return "%d0331" % y
    return "%d0930" % (y - 1)


def _family_of(table: str) -> str:
    fam = DATASET.get(table, {}).get("family")
    if fam == Family.DAILY:
        return "quote_daily"
    if fam == Family.PERIOD:
        return "financial_statement"
    if fam == Family.EVENT:
        return "event"
    if fam == Family.STATIC:
        return "static"
    return "unregistered"


def _freshness(as_of: str, values: dict, srcs: dict) -> dict:
    fams: dict = {}
    for table in srcs:
        fam = _family_of(table)
        if fam in fams:
            continue
        base = {"data_family": fam, "policy_id": _FRESHNESS_POLICY_ID,
                "threshold": None, "lag_days": None,
                "observed_at": None, "available_at": None}
        if fam == "quote_daily":
            expected = _last_open_day(as_of)
            avl = max([(v or {}).get("available_at") or "" for v in values.values()
                       if _family_of((v or {}).get("source") or "") == "quote_daily"] or [""]) or None
            base.update(observed_at=avl, available_at=avl,
                        threshold="latest_expected_complete_trading_day=%s" % expected,
                        policy_detail={"timezone": _QUOTE_TZ, "close_time": _QUOTE_CLOSE,
                                       "daily_availability_cutoff": "%s:%s" % (
                                           _QUOTE_AVAIL_CUTOFF[:2], _QUOTE_AVAIL_CUTOFF[2:]),
                                       "baseline_rule": "查询时点前最近已完成且按发布时延应可得的交易日"})
            if not expected:
                base.update(status="unknown", reason="交易日历不可用,无法判定(不默认新鲜)")
            elif not avl:
                base.update(status="unknown", reason="本次未取到行情族可见时点")
            else:
                lag = (datetime.strptime(expected, "%Y%m%d")
                       - datetime.strptime(avl, "%Y%m%d")).days
                base.update(status="stale" if avl < expected else "fresh",
                            lag_days=max(lag, 0),
                            reason=("数据交易日 %s 早于应有最近完整交易日 %s" % (avl, expected)
                                    if avl < expected else
                                    "数据已到应有最近完整交易日(周末/节假日/未收盘交易日不算陈旧)"))
        elif fam == "financial_statement":
            expected = _expected_fina_period(as_of)
            obs = max([(v or {}).get("observed_at") or "" for v in values.values()
                       if _family_of((v or {}).get("source") or "") == "financial_statement"] or [""]) or None
            avl = max([(v or {}).get("available_at") or "" for v in values.values()
                       if _family_of((v or {}).get("source") or "") == "financial_statement"] or [""]) or None
            base.update(observed_at=obs, available_at=avl,
                        threshold="statutory_expected_period=%s" % expected)
            if not obs or not avl:
                base.update(status="unknown",
                            reason="缺报告期或公告可见日,按披露可见性无法判定(不默认新鲜)")
            else:
                base.update(status="stale" if obs < expected else "fresh",
                            reason=("按披露节奏截至 as_of 应见 %s 期,实际最新 %s 期"
                                    % (expected, obs) if obs < expected else
                                    "最新已披露报告期不晚于法定应披露期"))
        elif fam == "event":
            base.update(status="unknown",
                        reason="event 族未登记新鲜度策略,不默认新鲜(FD-DIR-01)")
        else:
            base.update(status="unknown",
                        reason="数据族未登记新鲜度策略(%s),不静默套用行情阈值" % fam)
        fams[fam] = base
    if any(f.get("status") == "stale" for f in fams.values()):
        overall = "stale"
    elif any(f.get("status") == "unknown" for f in fams.values()):
        overall = "unknown"
    elif fams:
        overall = "fresh"
    else:
        overall = "unknown"
    return {"status": overall, "as_of": as_of,
            "policy_id": _FRESHNESS_POLICY_ID, "families": fams}


# ══════════════════════════ 派生算子（percentile_ops_v1）═════════════════════════════

_OP_VERSION = "percentile_ops_v1"
_OP_FIELD = {"pe_ttm_percentile": "pe_ttm", "pb_percentile": "pb", "ps_ttm_percentile": "ps_ttm"}
_OP_MIN_SAMPLES = 60
_OP_RULES = {
    "valid_sample_rule": "仅取有限正值(v>0 且非 inf/nan);PE 为负/无穷/缺失不入排名样本",
    "tie_rule": "经验分位=样本中 <=当前值 的占比(并列值计入,含当前日自身)",
    "windows": "full=全历史;y5=as_of 往前 1826 自然日",
}


def _derived_percentiles(ts_code: str, as_of: str, ops: list) -> dict:
    out: dict = {}
    try:
        res = _query(api_name="daily_basic", ts_code=ts_code, end_date=as_of,
                     fields="trade_date,pe_ttm,pb,ps_ttm", limit=200000)
        src = str(res.get("source") or "database")
        cols = {c: i for i, c in enumerate(res.get("columns") or [])}
        rows = res.get("rows") or []
    except Exception as e:  # noqa: BLE001
        for op in ops:
            out[op] = {"status": "error", "reason": "序列取数失败(%s)" % type(e).__name__}
        return out
    if src != "database":
        for op in ops:
            out[op] = {"status": "abstain",
                       "reason": "库内无该标的估值序列;PIT 口径禁实时补源(来源=%s)" % src}
        return out
    ti = cols.get("trade_date")
    if ti is None or not rows:
        for op in ops:
            out[op] = {"status": "abstain", "reason": "库内序列为空"}
        return out
    rows = sorted((r for r in rows if r[ti]), key=lambda r: _d8(r[ti]))
    rows = [r for r in rows if _d8(r[ti]) <= as_of]
    y5_floor = _shift(as_of, -1826)
    for op in ops:
        f = _OP_FIELD[op]
        fi = cols.get(f)
        if fi is None:
            out[op] = {"status": "error", "reason": "序列缺列 %s" % f}
            continue
        series = []
        for r in rows:
            d = _d8(r[ti])
            try:
                fv = float(r[fi])
            except (TypeError, ValueError):
                continue
            if fv > 0 and fv == fv and fv not in (float("inf"), float("-inf")):
                series.append((d, fv))
        cur_d = _d8(rows[-1][ti])
        try:
            cur_v = float(rows[-1][fi])
        except (TypeError, ValueError):
            cur_v = None
        item = {"operator": op, "field": f, "operator_version": _OP_VERSION,
                "value": cur_v if cur_v is not None else None,
                "data_as_of": cur_d, "observed_at": cur_d, "available_at": cur_d,
                "source": "database", "rules": _OP_RULES, "windows": {}}
        if cur_v is None or not (cur_v > 0) or cur_v != cur_v:
            item["status"] = "not_applicable"
            item["reason"] = "当前值缺失或非正(=%r):该指标此时无经济含义,不做分位排名" % rows[-1][fi]
            out[op] = item
            continue
        ok_windows = 0
        for wname, wseries in (("full", series),
                               ("y5", [x for x in series if x[0] >= y5_floor])):
            n_valid = len(wseries)
            wd = {"n_samples": n_valid,
                  "window_start": wseries[0][0] if wseries else None,
                  "window_end": wseries[-1][0] if wseries else None}
            if n_valid < _OP_MIN_SAMPLES:
                wd["status"] = "insufficient"
                wd["reason"] = "有效样本 %d < %d,不出正式分位(FD-DIR-03§三.4)" % (n_valid, _OP_MIN_SAMPLES)
            else:
                wd["status"] = "ok"
                wd["percentile"] = round(sum(1 for _, v in wseries if v <= cur_v) / n_valid, 4)
                ok_windows += 1
            item["windows"][wname] = wd
        item["status"] = ("ok" if ok_windows == 2 else
                          ("partial" if ok_windows == 1 else "abstain"))
        if item["status"] != "ok":
            item.setdefault("reason", "部分/全部窗口样本不足,见 windows.*.reason")
        out[op] = item
    return out


# ══════════════════════════ 端点 ══════════════════════════

@router.post("/v1/agent/compute")
async def external_agent_compute(request: Request):
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    opts = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    request_id = str(payload.get("request_id") or uuid.uuid4().hex)

    def env(status, tool, warns, errs, reason, extra=None):
        return _env.compute_envelope(status, tool, warns, errs, reason, request_id, extra)

    as_of, err = _scan_as_of(payload)
    if err:
        return env("error", None, [], ["as_of 校验失败：%s" % err], err)
    warns = []
    if not as_of:
        as_of = _business_today().strftime("%Y%m%d")
        warns.append("请求未给 as_of，已按今日 %s 取数" % as_of)

    raw = str(payload.get("target") or payload.get("ts_code") or
              opts.get("target") or opts.get("ts_code") or "").strip()
    ts_code, how, cands = _resolve_target(raw)
    if not raw:
        return env("error", None, warns, ["缺少 target"], "TARGET_REQUIRED")
    if not ts_code:
        code = _target_reason(raw, how)
        return env("abstain", None, warns + ["标的无法唯一确定，未擅自选取"], [], code,
                   {"target_input": raw, "candidates": cands})
    asset = classify_asset(ts_code)

    fields = opts.get("fields") or payload.get("fields") or DEFAULT_FIELDS
    if isinstance(fields, str):
        fields = [x.strip() for x in re.split(r"[,\s]+", fields) if x.strip()]

    values, missing, evidence, unknown, srcs = await run_in_threadpool(
        _collect, ts_code, as_of, list(fields), asset)

    non_db = sorted({v for v in srcs.values() if v != "database"})
    if non_db:
        warns.append("部分字段来自实时接口（%s），PIT 不成立，不得用于回测或反前视场景"
                     % "/".join(non_db))
    if unknown:
        warns.append("字段字典无此字段或该资产下无法解析：%s" % ", ".join(unknown))

    _derived_req = payload.get("derived") or opts.get("derived") or []
    if isinstance(_derived_req, str):
        _derived_req = [x.strip() for x in re.split(r"[,\s]+", _derived_req) if x.strip()]
    _bad_ops = [o for o in _derived_req if o not in ALLOWED_OPS]
    _unk_params = _l1p0_unknown_params(payload)
    if _unk_params:
        warns.append("未登记的请求参数被忽略：%s；本服务一期只提供原始字段查询，"
                     "标准算子尚未注册(允许的参数：%s)"
                     % (", ".join(_unk_params), ", ".join(sorted(KNOWN_REQUEST_KEYS)[:8]) + "…"))

    data_as_of = max([v.get("data_as_of") or "" for v in values.values()] or [""]) or as_of
    n_req = len(fields)
    cov = round(len(values) / max(n_req, 1), 4)

    _today = datetime.now().strftime("%Y%m%d")
    _hist_req = _l1p0_is_historical_request(as_of, _today)
    _pit_dropped = []
    if _hist_req:
        for _f in list(values.keys()):
            _api = (values[_f] or {}).get("source")
            if _api in STATIC_ONLY_APIS:
                _pit_dropped.append({"field": _f, "api": _api,
                                     "current_value_withheld": True,
                                     "reason": "该字段来自静态当前快照(无历史版本),"
                                               "历史请求下不得回填当前值(L1-P0-PIT/§7.2-2)"})
                values.pop(_f, None)
                if _f not in missing:
                    missing.append(_f)

    status = "ok" if values and not missing else ("partial" if values else "error")
    reason = "ok" if status == "ok" else ("partial_data" if values else "NO_DATA")
    if _pit_dropped and not values:
        status, reason = "abstain", "pit_unavailable_static_dataset"
    elif _pit_dropped:
        reason = "partial_data_pit_withheld"

    if _bad_ops:
        warns.append("未登记的派生算子:%s;已注册算子:%s(说不了就不要说,不返回原始值以免误读)"
                     % (", ".join(_bad_ops), ", ".join(sorted(ALLOWED_OPS))))
    if _unk_params or _bad_ops:
        _cleared = sorted(values.keys())
        values.clear()
        for _cf in _cleared:
            if _cf not in missing:
                missing.append(_cf)
        status, reason = "needs_clarification", ("unregistered_operator"
                                                 if _bad_ops else "unregistered_operator_param")

    tool = {"schema_version": "data_bundle_v1", "kind": "table",
            "agent_uid": _env.AGENT_UID, "agent_id": _env.AGENT_ID,
            "external_agent_id": _env.EXTERNAL_AGENT_ID,
            "not_for_weighting": True, "values": values,
            "missing_fields": sorted(set(missing)), "coverage": cov,
            "point_in_time": (all(s == "database" and DATASET_HISTORICAL.get(a, False)
                                  for a, s in srcs.items()) if srcs else False),
            "pit_detail": {a: {"source": s, "dataset_has_history": DATASET_HISTORICAL.get(a, False)}
                           for a, s in srcs.items()},
            "pit_withheld_fields": _pit_dropped,
            "rejected_params": _unk_params,
            "operator_support": {
                "registered_operators": sorted(ALLOWED_OPS) or [],
                "operator_registry_status": "registered:%d 个(percentile_ops_v1)" % len(ALLOWED_OPS),
                "allowed_request_params": sorted(KNOWN_REQUEST_KEYS),
                "why_not_ok": "出现未登记的语义参数时不能返回原始值 —— 调用方会把它误认成算子结果(CC9-P1-001)",
            } if _unk_params else None,
            "derived": (_derived_percentiles(ts_code, as_of, _derived_req)
                        if (_derived_req and not _bad_ops) else None),
            "field_data_as_of": {k: (v or {}).get("data_as_of") for k, v in values.items()},
            "field_observed_at": {k: (v or {}).get("observed_at") for k, v in values.items()},
            "field_available_at": {k: (v or {}).get("available_at") for k, v in values.items()},
            "timepoint_basis": ("daily族:观测日=可见日=交易日;"
                                "period族:observed_at=报告期end_date,available_at=公告日ann_date;"
                                "event族:observed_at=事件/生效日,available_at=公告/发布日;"
                                "缺可靠可见日填空并给 timepoint_reason,不回填(FD-DIR-01)"),
            "freshness": _freshness(as_of, values, srcs),
            "oldest_key_evidence_at": (min([(v or {}).get("data_as_of") for v in values.values()
                                            if (v or {}).get("data_as_of")], default=None)),
            "sources": srcs,
            "notes": "日频字段已向前吸附至 %s；财务字段按公告日门控" % data_as_of}
    return env(status, tool, warns, [] if values else ["全部字段均未取到"], reason,
               {"target": ts_code, "target_input": raw, "as_of": as_of,
                "as_of_date": as_of, "data_as_of": data_as_of,
                "asset": asset, "resolved_from": how, "evidence": evidence})
