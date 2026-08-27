"""tushare pro 公共客户端：统一初始化、分段拉取、文件导出、数据库导入。

供 download_stock.py / download_fund.py 复用。也可以被其他脚本 import：

    from tushare_client import get_pro, save_csv, import_to_db, export
"""
import os
from pathlib import Path

import pandas as pd
import tushare as ts
from dotenv import load_dotenv

load_dotenv()  # 尝试加载项目根目录 .env（若从项目内运行）

_pro = None


def get_pro():
    """懒加载 tushare pro 接口实例（单例）。"""
    global _pro
    if _pro is None:
        token = os.getenv("TUSHARE_TOKEN") or ts.get_token()
        if not token:
            raise RuntimeError(
                "未找到 TUSHARE_TOKEN：请在项目 .env 配置 TUSHARE_TOKEN，或设置环境变量"
            )
        _pro = ts.pro_api(token)
    return _pro


def fetch_by_period(api_name: str, start_date: str, end_date: str,
                    slice_days: int = 365, **kwargs) -> pd.DataFrame:
    """按时间段切片调用接口并合并去重，规避单次请求行数上限。

    适用于以 start_date/end_date 分页的接口（如 daily、fund_nav、index_daily）。
    分段失败会打印警告，不影响其他分段。

    Args:
        api_name: tushare 接口名，如 "daily"
        start_date / end_date: YYYYMMDD
        slice_days: 每段天数，默认 365（按年切）
        **kwargs: 透传给接口的其他参数，如 ts_code
    """
    pro = get_pro()
    start = pd.to_datetime(str(start_date))
    end = pd.to_datetime(str(end_date))
    frames = []
    cur = start
    while cur <= end:
        seg_end = min(cur + pd.Timedelta(days=slice_days - 1), end)
        s = cur.strftime("%Y%m%d")
        e = seg_end.strftime("%Y%m%d")
        try:
            df = getattr(pro, api_name)(start_date=s, end_date=e, **kwargs)
            if df is not None and not df.empty:
                frames.append(df)
        except Exception as exc:
            print(f"[分段失败] {api_name} {s}~{e}: {exc}")
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
