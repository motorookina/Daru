"""akshare 公共客户端：懒加载、失败重试、分段拉取、文件导出、数据库导入。

供 download_akshare.py 复用。也可以被其他脚本 import：

    from akshare_client import get_ak, call_interface, fetch_by_period, export

数据源为公开网页抓取，接口可能随上游改版失效，因此统一做失败重试。
"""
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # 尝试加载项目根目录 .env（若从项目内运行）

_ak = None


def get_ak():
    """懒加载 akshare 模块（单例）。"""
    global _ak
    if _ak is None:
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError(
                "未找到 akshare：请先 pip install akshare（本技能只负责下载导出）"
            ) from exc
        _ak = ak
    return _ak


def call_interface(name: str, retries: int = 3, base_wait: float = 1.0,
                   **kwargs) -> pd.DataFrame:
    """调用 akshare 接口，失败递增重试。

    数据源多为公开网页抓取，偶发超时/反爬；失败重试 retries 次，间隔 base_wait 递增。
    全部失败抛 RuntimeError，统一包装。
    """
    ak = get_ak()
    last = None
    for i in range(retries):
        try:
            return getattr(ak, name)(**kwargs)
        except Exception as exc:  # noqa: BLE001 - 重试所有异常后统一包装
            last = exc
            time.sleep(base_wait * (i + 1))
    raise RuntimeError(f"调用 {name}({kwargs}) 连续失败 {retries} 次: {last}")


def fetch_by_period(name: str, start_date: str, end_date: str,
                    slice_days: int = 365, **kwargs) -> pd.DataFrame:
    """按时间段切片调用接口并合并去重，规避接口的区间上限。

    适用于以 start_date/end_date 分页、且区间有上限的接口：
    - `bond_china_yield` / `repo_rate_hist`：单次区间必须小于一年 → slice_days=330
    - `futures_main_sina`：大区间单次请求过重 → slice_days=365
    分段失败会打印警告，不影响其他分段。

    Args:
        name: akshare 接口名，如 "futures_main_sina"
        start_date / end_date: YYYYMMDD
        slice_days: 每段天数
        **kwargs: 透传给接口的其他参数，如 symbol
    """
    start = pd.to_datetime(str(start_date))
    end = pd.to_datetime(str(end_date))
    frames = []
    cur = start
    while cur <= end:
        seg_end = min(cur + pd.Timedelta(days=slice_days - 1), end)
        s = cur.strftime("%Y%m%d")
        e = seg_end.strftime("%Y%m%d")
        try:
            df = call_interface(name, start_date=s, end_date=e, **kwargs)
            if df is not None and not df.empty:
                frames.append(df)
        except Exception as exc:  # noqa: BLE001
            print(f"[分段失败] {name} {s}~{e}: {exc}")
        cur = seg_end + pd.Timedelta(days=1)

    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    return result.drop_duplicates().reset_index(drop=True)


def save_csv(df: pd.DataFrame, path: Path) -> str:
    """导出 DataFrame 到 CSV（utf-8-sig，Excel 直接打开不乱码），返回文件路径。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def save_parquet(df: pd.DataFrame, path: Path) -> str:
    """导出 DataFrame 到 parquet，返回文件路径。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return str(path)


def import_to_db(df: pd.DataFrame, table_name: str, db_url: str | None = None,
                 if_exists: str = "replace") -> str:
    """将 DataFrame 导入 PostgreSQL 表。

    Args:
        df: 要导入的数据
        table_name: 目标表名（自动建表）
        db_url: PostgreSQL 连接串，覆盖 .env 的 DATABASE_URL
        if_exists: "replace" 覆盖 / "append" 追加
    """
    from sqlalchemy import create_engine

    url = db_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "未找到 DATABASE_URL：请在项目 .env 配置，或传 --db-url 参数"
        )
    engine = create_engine(url)
    df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    return table_name


def export(df: pd.DataFrame, path: Path, fmt: str = "csv",
           table: str | None = None, db_url: str | None = None,
           append: bool = False) -> str:
    """按格式导出：csv / parquet / db。返回文件路径或表名。"""
    if fmt == "db":
        return import_to_db(df, table, db_url,
                            if_exists="append" if append else "replace")
    if fmt == "parquet":
        return save_parquet(df, path)
    return save_csv(df, path)
