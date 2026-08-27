"""AKShare 数据下载脚本（akshare-pro 技能配套）。

用法示例（11 个接口各一个子命令）：
    # 期货主力连续（PVC，2020-2021）
    python download_akshare.py futures_main_sina V0 20200101 20220101 [--out data]

    # 中债综合指数（财富，总值）
    python download_akshare.py bond_new_composite_index_cbond [--indicator 财富] [--period 总值]

    # 国债收益率 / 回购定盘利率（区间须 <1 年，超长自动分段）
    python download_akshare.py bond_china_yield 20210201 20220201
    python download_akshare.py repo_rate_hist 20231001 20240101

    # 全市场 / 指数 PE、PB（symbol 见 references/数据接口.md 可选值）
    python download_akshare.py stock_market_pe_lg 上证
    python download_akshare.py stock_market_pb_lg 上证
    python download_akshare.py stock_index_pe_lg 上证50
    python download_akshare.py stock_index_pb_lg 上证50

    # 申万行业指数（日/周/月）
    python download_akshare.py index_hist_sw 801193 [--period day]

    # 宏观：存款准备金率 / 央行基准利率（无参数）
    python download_akshare.py macro_china_reserve_requirement_ratio
    python download_akshare.py macro_bank_china_interest_rate

    # 通用输出参数：--out / --fmt csv|parquet|db / --table / --db-url / --append
    python download_akshare.py stock_market_pe_lg 上证 --fmt db --table stock_market_pe_lg
"""
import argparse
import sys
from pathlib import Path

from akshare_client import call_interface, export, fetch_by_period

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


def cmd_futures_main_sina(args):
    """期货主力连续（新浪），单品种；跨年自动分段。"""
    df = fetch_by_period("futures_main_sina", args.start, args.end,
                         slice_days=365, symbol=args.symbol)
    _export(args, f"futures_main_sina_{args.symbol}", df)


def cmd_bond_new_composite_index_cbond(args):
    """中债综合指数（调用最密集）。"""
    df = call_interface("bond_new_composite_index_cbond",
                        indicator=args.indicator, period=args.period)
    _export(args, f"bond_new_composite_index_cbond_{args.indicator}_{args.period}", df)


def cmd_bond_china_yield(args):
    """国债收益率（中债）；单次区间须 <1 年，超长自动按 330 天分段。"""
    df = fetch_by_period("bond_china_yield", args.start, args.end, slice_days=330)
    _export(args, "bond_china_yield", df)


def cmd_repo_rate_hist(args):
    """回购定盘利率历史；单次区间须 <1 年，超长自动按 330 天分段。"""
    df = fetch_by_period("repo_rate_hist", args.start, args.end, slice_days=330)
    _export(args, "repo_rate_hist", df)


def cmd_stock_market_pe_lg(args):
    """全市场市盈率（乐咕乐股）。"""
    df = call_interface("stock_market_pe_lg", symbol=args.symbol)
    _export(args, f"stock_market_pe_lg_{args.symbol}", df)


def cmd_stock_market_pb_lg(args):
    """全市场市净率（乐咕乐股）。"""
    df = call_interface("stock_market_pb_lg", symbol=args.symbol)
    _export(args, f"stock_market_pb_lg_{args.symbol}", df)


def cmd_stock_index_pe_lg(args):
    """指数市盈率（乐咕乐股）。"""
    df = call_interface("stock_index_pe_lg", symbol=args.symbol)
    _export(args, f"stock_index_pe_lg_{args.symbol}", df)


def cmd_stock_index_pb_lg(args):
    """指数市净率（乐咕乐股）。"""
    df = call_interface("stock_index_pb_lg", symbol=args.symbol)
    _export(args, f"stock_index_pb_lg_{args.symbol}", df)


def cmd_index_hist_sw(args):
    """申万行业指数历史（申万宏源研究）；注意与 tushare sw_daily 去重。"""
    df = call_interface("index_hist_sw", symbol=args.symbol, period=args.period)
    _export(args, f"index_hist_sw_{args.symbol}_{args.period}", df)


def cmd_macro_china_reserve_requirement_ratio(args):
    """存款准备金率（东方财富）。"""
    df = call_interface("macro_china_reserve_requirement_ratio")
    _export(args, "macro_china_reserve_requirement_ratio", df)


def cmd_macro_bank_china_interest_rate(args):
    """央行基准利率（金十数据）。"""
    df = call_interface("macro_bank_china_interest_rate")
    _export(args, "macro_bank_china_interest_rate", df)


def main():
    parser = argparse.ArgumentParser(description="AKShare 数据下载（akshare-pro 技能）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fut = sub.add_parser("futures_main_sina", parents=[common], help="期货主力连续（新浪）")
    p_fut.add_argument("symbol", help="品种代码，如 V0；可用 ak.futures_display_main_sina() 获取列表")
    p_fut.add_argument("start", help="开始日期 YYYYMMDD")
    p_fut.add_argument("end", help="结束日期 YYYYMMDD")
    p_fut.set_defaults(fn=cmd_futures_main_sina)

    p_cbond = sub.add_parser("bond_new_composite_index_cbond", parents=[common], help="中债综合指数")
    p_cbond.add_argument("--indicator", default="财富", help="指标，默认 财富")
    p_cbond.add_argument("--period", default="总值", help="待偿期限分段，默认 总值")
    p_cbond.set_defaults(fn=cmd_bond_new_composite_index_cbond)

    p_yield = sub.add_parser("bond_china_yield", parents=[common], help="国债收益率（中债）")
    p_yield.add_argument("start", help="开始日期 YYYYMMDD")
    p_yield.add_argument("end", help="结束日期 YYYYMMDD")
    p_yield.set_defaults(fn=cmd_bond_china_yield)

    p_repo = sub.add_parser("repo_rate_hist", parents=[common], help="回购定盘利率历史")
    p_repo.add_argument("start", help="开始日期 YYYYMMDD")
    p_repo.add_argument("end", help="结束日期 YYYYMMDD")
    p_repo.set_defaults(fn=cmd_repo_rate_hist)

    p_mpe = sub.add_parser("stock_market_pe_lg", parents=[common], help="全市场市盈率")
    p_mpe.add_argument("symbol", help="上证 / 深证 / 创业板 / 科创版")
    p_mpe.set_defaults(fn=cmd_stock_market_pe_lg)

    p_mpb = sub.add_parser("stock_market_pb_lg", parents=[common], help="全市场市净率")
    p_mpb.add_argument("symbol", help="上证 / 深证 / 创业板 / 科创版")
    p_mpb.set_defaults(fn=cmd_stock_market_pb_lg)

    p_ipe = sub.add_parser("stock_index_pe_lg", parents=[common], help="指数市盈率")
    p_ipe.add_argument("symbol", help="上证50 / 沪深300 等 12 个指数名")
    p_ipe.set_defaults(fn=cmd_stock_index_pe_lg)

    p_ipb = sub.add_parser("stock_index_pb_lg", parents=[common], help="指数市净率")
    p_ipb.add_argument("symbol", help="上证50 / 沪深300 等 12 个指数名")
    p_ipb.set_defaults(fn=cmd_stock_index_pb_lg)

    p_sw = sub.add_parser("index_hist_sw", parents=[common], help="申万行业指数历史")
    p_sw.add_argument("symbol", help="申万指数代码，如 801193")
    p_sw.add_argument("--period", choices=["day", "week", "month"], default="day",
                     help="数据周期，默认 day")
    p_sw.set_defaults(fn=cmd_index_hist_sw)

    p_rrr = sub.add_parser("macro_china_reserve_requirement_ratio", parents=[common],
                           help="存款准备金率")
    p_rrr.set_defaults(fn=cmd_macro_china_reserve_requirement_ratio)

    p_rate = sub.add_parser("macro_bank_china_interest_rate", parents=[common],
                            help="央行基准利率")
    p_rate.set_defaults(fn=cmd_macro_bank_china_interest_rate)

    args = parser.parse_args()
    try:
        args.fn(args)
    except RuntimeError as exc:
        print(f"[错误] {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
