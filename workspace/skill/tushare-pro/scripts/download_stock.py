"""股票数据下载脚本（tushare-pro 技能配套）。

用法示例：
    # 导出 CSV（默认）
    python download_stock.py daily 600519.SH 20240101 20241231 [--adj qfq] [--out data]
    python download_stock.py stock_basic [--out data]

    # 导出 parquet
    python download_stock.py daily 600519.SH 20240101 20241231 --fmt parquet --out data

    # 直接导入 PostgreSQL（表不存在自动建表，默认覆盖；--append 追加）
    python download_stock.py stock_basic --fmt db --table stock_basic
    python download_stock.py daily 600519.SH 20240101 20241231 --fmt db --table daily_600519
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


def cmd_daily(pro, args):
    """日线行情；--adj 指定复权方式时走 pro_bar（前/后复权）。"""
    if args.adj:
        df = pro.pro_bar(ts_code=args.ts_code, start_date=args.start,
                         end_date=args.end, adj=args.adj)
    else:
        df = fetch_by_period("daily", args.start, args.end, ts_code=args.ts_code)
    _export(args, f"daily_{args.ts_code}_{args.start}_{args.end}", df)


def cmd_stock_basic(pro, args):
    """全部 A 股股票列表。"""
    df = pro.stock_basic(
        exchange="", list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date",
    )
    _export(args, "stock_basic", df)


def cmd_fina_indicator(pro, args):
    """财务指标（单标的单报告期，注意单次最多 100 条）。"""
    df = pro.fina_indicator(ts_code=args.ts_code, period=args.period)
    _export(args, f"fina_indicator_{args.ts_code}_{args.period}", df)


def cmd_trade_cal(pro, args):
    """指定年份的上交所交易日历。"""
    start, end = f"{args.year}0101", f"{args.year}1231"
    df = pro.trade_cal(exchange="SSE", start_date=start, end_date=end)
    _export(args, f"trade_cal_{args.year}", df)


def main():
    parser = argparse.ArgumentParser(description="股票数据下载")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_daily = sub.add_parser("daily", parents=[common], help="日线行情（可复权）")
    p_daily.add_argument("ts_code")
    p_daily.add_argument("start")
    p_daily.add_argument("end")
    p_daily.add_argument("--adj", choices=["qfq", "hfq"], default=None, help="复权方式")
    p_daily.set_defaults(fn=cmd_daily)

    p_basic = sub.add_parser("stock_basic", parents=[common], help="股票列表")
    p_basic.set_defaults(fn=cmd_stock_basic)

    p_fina = sub.add_parser("fina_indicator", parents=[common], help="财务指标")
    p_fina.add_argument("ts_code")
    p_fina.add_argument("period")
    p_fina.set_defaults(fn=cmd_fina_indicator)

    p_cal = sub.add_parser("trade_cal", parents=[common], help="交易日历")
    p_cal.add_argument("year")
    p_cal.set_defaults(fn=cmd_trade_cal)

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
