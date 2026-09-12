# -*- coding: utf-8 -*-
"""数据接入缝（v1.3）：复用 v1.2 的 new_query.query() 真实内核。

「其余不要」的边界在这里：v1.3 只做 L1（本地库 + 内核自身降级 tushare），
不重写 SQL / 不落 L2/L3/L4 瀑布 / 不落快照 / 不落降级日志——那些仍属 v1.2。

懒加载：首次真正取数才把 v1.2 的 app 包动态挂载并 import，
保证「仅 import 契约层（如 /v1/agent/resolve 冒烟）」不依赖 v1.2/DB。

包名冲突说明：v1.2 与 v1.3 都用 `app` 作包名，直接 `from app.routers.new_query`
会解析到 v1.3 自己。故这里用 importlib 把 v1.2 的 app 包以 `v12app` 名字加载，
其内部 `from ..config import settings` 等相对导入会正确解析到 `v12app.config`。
"""
from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys

log = logging.getLogger("pg-ops-agent.datasource")

_nq_query = None
_nq_stock_basic = None
_loaded = False


def _load() -> None:
    global _nq_query, _nq_stock_basic, _loaded
    if _loaded:
        return
    _v12_backend = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "financial_data_service", "pg-ops-agent-v1.2", "backend"))
    _pkg_dir = os.path.join(_v12_backend, "app")
    _pkg_init = os.path.join(_pkg_dir, "__init__.py")

    # 以 v12app 名字动态加载 v1.2 的 app 包，绕开包名冲突
    spec = importlib.util.spec_from_file_location(
        "v12app", _pkg_init, submodule_search_locations=[_pkg_dir])
    if spec is None or spec.loader is None:
        raise ImportError("无法定位 v1.2 内核：%s" % _pkg_init)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v12app"] = mod
    spec.loader.exec_module(mod)

    nq = importlib.import_module("v12app.routers.new_query")
    _nq_query = nq.query
    _nq_stock_basic = nq.stock_basic
    _loaded = True


def query(api_name: str, **params) -> dict:
    """L1 取数内核直通：api_name → v1.2 new_query 的 handler。"""
    _load()
    return _nq_query(api_name=api_name, **params)


def stock_basic(**params) -> dict:
    _load()
    return _nq_stock_basic(**params)


def fetch(api: str, **params) -> tuple[dict, str]:
    """L1 薄封装：返回 (payload, source)。取不到就抛，不返回空以伪装成功。"""
    res = query(api_name=api, **params)
    src = str(res.get("source") or "database")
    return res, src
