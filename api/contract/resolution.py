# -*- coding: utf-8 -*-
"""标的解析与字段路由（v1.3，纯规则，无 LLM）。

四块缺口中的两块在此落地：
  · classify_asset —— 缺口 1：target → 资产类型（stock/index/industry/fut/bond/rate/market/macro）
  · _resolve_target —— 缺口 2：多资产码表 + 非 6 位码放行，契约三元组 (ts_code, how, cands) 不变
其余为从 v1.2 平移的纯规则辅助（as_of 校验、接口判定、参数构造）。
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .registry import DATASET, FIELD_DICT, PRIMARY, Family, _NO_TARGET_APIS

log = logging.getLogger("pg-ops-agent.resolution")

# ---- as_of 六别名（与全队一致，顺序即优先级仅用于报告，不用于取值仲裁）----
AS_OF_ALIASES = ("as_of", "as_of_date", "target_date", "query_date", "date", "trade_date")

# ---- 接口关键词表：纯规则，无 LLM（沿用 v1.2 契约）----
_INTENT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("daily_basic", ("市盈率", "pe", "市净率", "pb", "换手率", "股息率", "市值", "估值指标", "ps")),
    ("daily", ("收盘价", "开盘价", "股价", "行情", "涨跌幅", "成交量", "成交额", "k线", "价格")),
    ("moneyflow_dc", ("资金流", "主力", "净流入", "净流出", "大单")),
    ("fina_indicator", ("财务指标", "roe", "净资产收益率", "毛利率", "净利率", "资产负债率")),
    ("income", ("利润表", "营业收入", "净利润", "营收", "归母")),
    ("balancesheet", ("资产负债表", "总资产", "总负债", "股东权益")),
    ("cashflow", ("现金流量表", "经营现金流", "自由现金流", "现金流")),
    ("report_rc", ("研报", "分析师", "盈利预测", "评级", "目标价")),
    ("index_daily", ("指数行情", "指数收盘", "沪深300", "上证指数", "中证")),
    ("index_dailybasic", ("指数估值", "指数市盈率", "指数pe", "指数pb")),
    ("trade_cal", ("交易日", "交易日历", "开市", "休市")),
    ("cn_cpi", ("cpi", "居民消费价格")),
    ("cn_ppi", ("ppi", "工业品出厂")),
    ("cn_pmi", ("pmi", "采购经理")),
    ("margin_detail", ("融资融券", "两融", "融资余额")),
    ("hk_hold", ("陆股通", "北向", "港资持股")),
    ("top_list", ("龙虎榜",)),
    ("cyq_perf", ("筹码", "获利比例")),
    ("stock_basic", ("上市日期", "所属行业", "基本信息", "股票代码")),
]

# 这些接口按"期间"取数，其余按"单日"取数（从注册表推导，随表扩展自动覆盖）
_MONTHLY_APIS = {t for t, m in DATASET.items() if m.get("time") == "month"}
_PERIOD_APIS = {t for t, m in DATASET.items() if m["family"] in (Family.PERIOD, Family.EVENT)}
# _NO_TARGET_APIS 从 registry 导入（按 asset 维度推导，单一事实来源）

# 指数代码基线（写死的兜底；运行时再补 index_basic 全量）
_KNOWN_INDEX_CODES = {
    "000001.SH", "000016.SH", "000300.SH", "000905.SH", "000852.SH",
    "399001.SZ", "399006.SZ", "399300.SZ",
}

_NAME_MAP: dict[str, str] | None = None    # 名称 → ts_code（多资产），进程内缓存
_KNOWN_CODES: set[str] | None = None       # 合法 ts_code 全集，进程内缓存
_INDEX_CODES: set[str] | None = None       # 指数代码全集，进程内缓存


def _business_today() -> date:
    """业务日固定按北京时间，避免 UTC 服务器在 00:00—08:00 误判「今天」为未来。"""
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


# ------------------------------------------------------------------ as_of

def _norm_date(v: Any) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    s = s.replace("-", "").replace("/", "").replace(".", "")
    return s if re.fullmatch(r"\d{8}", s) else ""


def _date_from_text(text: str) -> str:
    s = str(text or "")
    m = re.search(r"(?<!\d)(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", s)
    if not m:
        m = re.search(r"(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)", s)
    if not m:
        return ""
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y%m%d")
    except ValueError:
        return ""


def _scan_as_of(payload: dict, question: str = "") -> tuple[str, str]:
    """扫描顶层、options、context 与问句日期。返回 (值, 错误码)。"""
    found: dict[str, str] = {}
    scopes = (
        ("top", payload),
        ("options", payload.get("options") or {}),
        ("context", payload.get("context") or {}),
    )
    for scope_name, scope in scopes:
        if not isinstance(scope, dict):
            continue
        for k in AS_OF_ALIASES:
            if k in scope and str(scope[k] or "").strip():
                n = _norm_date(scope[k])
                if not n:
                    return "", "AS_OF_MALFORMED"
                found[f"{scope_name}.{k}"] = n
    text_date = _date_from_text(question)
    if text_date:
        found["question.date"] = text_date
    if not found:
        return "", ""
    vals = set(found.values())
    if len(vals) > 1:
        return "", "AS_OF_ALIAS_MISMATCH"
    v = vals.pop()
    if v > _business_today().strftime("%Y%m%d"):
        return "", "AS_OF_IN_FUTURE"
    return v, ""


# --------------------------------------------------------------- 取数内核（懒加载，避免无 v1.2 时 import 即炸）

def _query(api_name: str, **params) -> dict:
    from ..datasource import query
    return query(api_name=api_name, **params)


# --------------------------------------------------------------- 标的解析（多资产）

def _load_name_map() -> dict[str, str]:
    global _NAME_MAP
    if _NAME_MAP is not None:
        return _NAME_MAP
    m: dict[str, str] = {}
    for api in ("stock_basic", "index_basic", "fut_basic"):
        try:
            d = _query(api_name=api, fields="ts_code,name", limit=100000)
            cols = d.get("columns") or []
            if "ts_code" not in cols or "name" not in cols:
                continue
            i_c, i_n = cols.index("ts_code"), cols.index("name")
            for r in d.get("rows") or []:
                nm = str(r[i_n] or "").strip()
                if nm:
                    m[nm] = str(r[i_c])
                    m[nm.replace(" ", "")] = str(r[i_c])
        except Exception as e:  # noqa: BLE001
            log.warning("名称表加载失败（%s，标的解析降级为仅代码规则）：%s", api, e)
    _NAME_MAP = m
    return m


def _load_codes() -> set[str]:
    global _KNOWN_CODES
    if _KNOWN_CODES is not None:
        return _KNOWN_CODES
    codes = set(_KNOWN_INDEX_CODES) | set(_load_name_map().values())
    for api in ("index_basic", "fut_basic"):
        try:
            d = _query(api_name=api, fields="ts_code", limit=100000)
            cols = d.get("columns") or []
            if "ts_code" in cols:
                i = cols.index("ts_code")
                codes.update(str(r[i]) for r in (d.get("rows") or []) if r[i])
        except Exception:  # noqa: BLE001
            continue
    _KNOWN_CODES = codes
    return codes


def _load_index_codes() -> set[str]:
    global _INDEX_CODES
    if _INDEX_CODES is not None:
        return _INDEX_CODES
    codes = set(_KNOWN_INDEX_CODES)
    try:
        d = _query(api_name="index_basic", fields="ts_code", limit=100000)
        cols = d.get("columns") or []
        if "ts_code" in cols:
            i = cols.index("ts_code")
            codes.update(str(r[i]) for r in (d.get("rows") or []) if r[i])
    except Exception:  # noqa: BLE001
        pass
    _INDEX_CODES = codes
    return codes


def _resolve_target(raw: str) -> tuple[str, str, list[str]]:
    """纯规则标的解析（多资产）。返回 (ts_code, 解析依据, 候选列表)。

    规则：① 已带交易所后缀直通；② 6 位数字按首位补后缀；③ 期货码（X.YYY / X1234.YYY）直通；
    ④ 查多资产名称表。名称歧义时返回全部候选而不擅自挑一个。
    """
    s = str(raw or "").strip()
    if not s:
        return "", "empty", []
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", s.upper()):
        code = s.upper()
        return (code, "explicit_suffix", []) if code in _load_codes() else ("", "not_found", [])
    if re.fullmatch(r"\d{6}", s):
        head = s[0]
        sfx = ".SH" if head in "56" else (".BJ" if head == "8" else ".SZ")
        code = s + sfx
        return (code, "numeric_rule", []) if code in _load_codes() else ("", "not_found", [])
    if re.fullmatch(r"[A-Z]{1,3}(?:\d{3,4})?\.(SHF|CZC|DCE|INE|CFX|GFEX)", s.upper()):
        code = s.upper()
        return (code, "explicit_suffix", []) if code in _load_codes() else ("", "not_found", [])
    m = _load_name_map()
    if s in m:
        return m[s], "name_exact", []
    cands = sorted({v for k, v in m.items() if s in k})
    if len(cands) == 1:
        return cands[0], "name_fuzzy_unique", []
    if cands:
        return "", "name_ambiguous", cands[:20]
    return "", "not_found", []


def classify_asset(ts_code: str) -> str:
    """缺口 1：target → 资产类型。规则快路径 + DB 兜底；查不到 → unknown（不猜）。"""
    code = str(ts_code or "").strip().upper()
    if not code:
        return "unknown"
    # 期货交易所后缀 → fut
    if re.search(r"\.(SHF|CZC|DCE|INE|CFX|GFEX)$", code):
        return "fut"
    # 6 位 A 股 / 指数
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", code):
        return "index" if code in _load_index_codes() else "stock"
    # DB 兜底：谁命中归谁
    for asset, api in (("index", "index_basic"), ("fut", "fut_basic"), ("stock", "stock_basic")):
        try:
            d = _query(api_name=api, ts_code=code, limit=1)
            if d.get("row_count") or d.get("rows"):
                return asset
        except Exception:  # noqa: BLE001
            continue
    return "unknown"


def _target_from_question(question: str) -> tuple[str, str, list[str], str]:
    """从完整问句中确定性提取标的，不用 LLM；最后一项为实际拿来解析的表达式。"""
    text = str(question or "").strip()
    code_match = re.search(r"(?<!\d)(\d{6}(?:\.[A-Z]{2,4})?)(?!\d)", text, flags=re.I)
    if code_match:
        raw = code_match.group(1)
        code, how, cands = _resolve_target(raw)
        return code, how, cands, raw

    cleaned = re.sub(r"^(?:请问|请查询|查询一下|帮我查一下|帮我查|请分析|分析一下|看看)\s*", "", text)
    cut = len(cleaned)
    for _api, keywords in _INTENT_RULES:
        for keyword in keywords:
            pos = cleaned.lower().find(keyword.lower())
            if 0 <= pos < cut:
                cut = pos
    raw = cleaned[:cut]
    raw = re.sub(r"20\d{2}年\s*\d{1,2}月\s*\d{1,2}日", "", raw)
    raw = re.sub(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", "", raw)
    raw = re.sub(r"(?:截至|截止|在|现在|当前|今天|目前|最新|当日|的|，|,|\s)+$", "", raw).strip()
    if not raw:
        return "", "empty", [], ""
    code, how, cands = _resolve_target(raw)
    return code, how, cands, raw


def _target_reason(raw: str, how: str) -> str:
    if how == "name_ambiguous":
        return "TARGET_AMBIGUOUS"
    return "TARGET_NOT_FOUND"


# ------------------------------------------------------------- 字段路由（resolve / desc）

def resolve(field: str, asset: str) -> list[str]:
    """返回候选表名，按 prio 升序。仅匹配同 asset 的表（market/宏观不默认并入）。"""
    hit = [t for t, m in DATASET.items()
           if m["asset"] == asset and field in m["cols"]]
    return sorted(hit, key=lambda t: DATASET[t]["prio"])


def resolve_one(field: str, asset: str) -> str | None:
    """取主表（先看 PRIMARY 钉死，再看 prio 最小）；并列则返回 None，交由路由层裁决。"""
    if field in PRIMARY:
        t = PRIMARY[field]
        return t if (DATASET[t]["asset"] == asset and field in DATASET[t]["cols"]) else None
    c = resolve(field, asset)
    if not c:
        return None
    if len(c) > 1 and DATASET[c[0]]["prio"] == DATASET[c[1]]["prio"]:
        return None
    return c[0]


def desc(field: str, table: str) -> tuple[str, str]:
    """返回 (物理列, 单位)。列级覆盖优先，其次 FIELD_DICT 缺省单位。"""
    v = DATASET[table]["cols"][field]
    if isinstance(v, tuple):
        return v
    return v, FIELD_DICT.get(field, {}).get("unit")


# ------------------------------------------------------------- 接口判定（invoke 用）

def _pick_api(text: str) -> tuple[str, list[str]]:
    t = str(text or "").lower()
    hits = [api for api, kws in _INTENT_RULES if any(k in t for k in kws)]
    return (hits[0] if hits else ""), hits


def _build_params(api: str, ts_code: str, as_of: str, opts: dict) -> dict:
    p: dict[str, Any] = {}
    for k in ("fields", "limit", "offset", "start_date", "end_date", "trade_date",
              "period", "ann_date", "report_date", "exchange", "m", "start_m", "end_m"):
        if opts.get(k) not in (None, ""):
            p[k] = opts[k]
    if ts_code and api not in _NO_TARGET_APIS:
        p.setdefault("ts_code", ts_code)
    if as_of:
        if api in _MONTHLY_APIS:
            p.setdefault("end_m", as_of[:6])
            p.setdefault("start_m", "%04d%02d" % (int(as_of[:4]) - 1, int(as_of[4:6])))
        elif api in _PERIOD_APIS:
            p.setdefault("end_date", as_of)
            p.setdefault("start_date", "%04d%s" % (int(as_of[:4]) - 1, as_of[4:]))
        else:
            p.setdefault("trade_date", as_of)
    p.setdefault("limit", int(opts.get("limit") or 200))
    return p
