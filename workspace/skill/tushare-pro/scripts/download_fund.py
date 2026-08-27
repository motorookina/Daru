"""基金数据下载脚本（tushare-pro 技能配套）。

用法示例：
    # 导出 CSV（默认）
    python download_fund.py fund_list [--out data]
    python download_fund.py fund_nav 159915.SZ 20240101 20241231 [--out data]

    # 直接导入 PostgreSQL（表不存在自动建表，默认覆盖；--append 追加）
    python download_fund.py fund_nav 159915.SZ 20240101 20241231 --fmt db --table fund_nav_159915
"""
import argparse
import sys
from pathlib import Path

from tushare_client import export, fetch_by_period, get_pro

# 公共参数
common = argparse.ArgumentParser(add_help=False)
common.add_argument("--out", default="data", help="输出目录（默认 ./data，仅 csv/parquet 用）")
common.add_argument("--fmt", choices=["csv", "parquet", "db"], default="csv",
                    help="输出格式：csv / parquet / db（导入 PostgreSQL）")
common.add_argument("--table", default=None, help="导入数据库时的表名（默认用接口名）")
common.add_argument("--db-url", default=None, help="PostgreSQL 连接串，覆盖 .env 的 DATABASE_URL")
common.add_argument("--append", action="store_true", help="导入数据库时追加而非覆盖")


def _export(args, base_name: str, df) -> str:
    """统一导出入口，按 --fmt 分发到文件或数据库。"""
    if args.fmt == "db":
        table = args.table or base_name
        result = export(df, Path(), fmt="db", table=table,
                        db_url=args.db_url, append=args.append)
        print(f"已导入 {len(df)} 行 -> 数据库表 {result}")
        return result
    suffix = "parquet" if args.fmt == "parquet" else "csv"
    path = export(df, Path(args.out) / f"{base_name}.{suffix}", fmt=args.fmt)
    print(f"已导出 {len(df)} 行 -> {path}")
    return str(path)


def cmd_fund_list(pro, args):
    """场内基金列表。"""
    df = pro.fund_basic(
        market="E", status="L",
        fields="ts_code,fund_name,fund_type,found_date,issue_date,delist_date",
    )
    _export(args, "fund_basic", df)


def cmd_fund_nav(pro, args):
    """基金净值（自动分段拉取）。"""
    df = fetch_by_period("fund_nav", args.start, args.end, ts_code=args.ts_code)
    _export(args, f"fund_nav_{args.ts_code}_{args.start}_{args.end}", df)


def main():
    parser = argparse.ArgumentParser(description="基金数据下载")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("fund_list", parents=[common], help="基金列表")
    p_list.set_defaults(fn=cmd_fund_list)

    p_nav = sub.add_parser("fund_nav", parents=[common], help="基金净值")
    p_nav.add_argument("ts_code")
    p_nav.add_argument("start")
    p_nav.add_argument("end")
    p_nav.set_defaults(fn=cmd_fund_nav)

    args = parser.parse_args()

    try:
        pro = get_pro()
        args.fn(pro, args)
    except RuntimeError as exc:
        print(f"[错误] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"[错误] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
