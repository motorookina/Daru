---
name: tushare-pro
description: 专用于从 Tushare 下载/导出金融数据的技能。当用户需要拉取、下载、导出 A 股/指数/基金行情、财务报表、基础信息、宏观数据到本地文件（CSV/parquet）时使用。仅负责数据下载与导出，不包含投资分析。
metadata:
  author: db-ops（基于 tushare.pro 官方 skill 改造）
  version: 1.0.0
---

# tushare-pro（数据下载）

专用于 **Tushare 数据下载与导出** 的技能。

## 前置条件

- **TUSHARE_TOKEN**：Tushare Token，用于认证授权访问数据服务。获取方式：https://tushare.pro/register
- **Python 3.7+**，需要安装 `tushare` 包（`pip install tushare`）
- **导入 PostgreSQL**：需要 `sqlalchemy` + PG 驱动（`psycopg`），并在 .env 配置 `DATABASE_URL`
- 需要网络访问 Tushare 服务

## 这个技能用来做什么

- 下载个股 / 指数 / 基金的行情数据（日线、周线、月线、复权行情）
- 下载基础信息（股票列表、指数列表、基金列表、交易日历）
- 下载财务数据（利润表、资产负债表、现金流量表、财务指标、业绩预告/快报）
- 下载宏观数据（CPI、PPI、PMI、GDP、货币供应量）
- 按时间 / 标的分段批量拉取，合并去重
- 导出为 CSV / parquet 到本地目录，或直接导入 PostgreSQL 数据库（自动建表）

## 何时使用

当用户表达以下意图时优先使用：

- "把 XX 的日线数据下载下来"
- "导出 XXX 的财务数据到 CSV"
- "拉取近三年 A 股行情"
- "下载交易日历"
- "批量下载基金净值"

## 何时不使用

- 需要投资分析 / 选股 / 板块轮动 / 资金流解读 → 使用 tushare（研究）技能
- 买卖建议或投资顾问
- 无 TUSHARE_TOKEN 或积分权限不足时强行伪造数据

## 环境检查

在请求数据前先确认：

1. `tushare` 包已安装（`pip install tushare`）
2. `TUSHARE_TOKEN` 已配置（项目 .env 或环境变量）
3. 高权限接口提前提示可能存在积分限制

## 数据下载工作流

1. **解析任务**：标的（ts_code）、时间范围、频率、字段、输出格式
2. **选接口**：从 `references/数据接口.md` 查找接口与参数
3. **分段拉取**：长区间按年/季度切片，规避单次行数上限
4. **合并去重**：分段结果合并 + 去重 + 排序
5. **校验**：关键字段存在性、日期格式、空结果区分原因
6. **导出**：CSV / parquet，规范命名，记录元信息

## 时间默认值

- 用户未指定时间范围 → 优先和用户进行确认，如果用户未给出明确答案，默认近一年。
- 长区间 → 自动分段（日线按年、分钟按周、财务按报告期）

## 输出规范

- 文件命名：`{接口}_{标的}_{开始}_{结束}_{拉取日期}.csv`
  - 例：`daily_600519.SH_20240101_20241231_20260322.csv`
- **输出格式**：`--fmt` 指定 `csv` / `parquet` / `db`（默认 csv）
- **导入数据库**：默认表名 = 接口名（可用 `--table` 覆盖），默认 `replace` 覆盖、`--append` 追加；连接串取 .env 的 `DATABASE_URL`（`--db-url` 可覆盖）
- 默认输出目录：`./data/`（脚本 `--out` 可改）
- 每次导出尽量记录：接口名、请求参数、拉取时间、行数、失败分段

## 常用接口（核心集）

**行情**：`daily`、`pro_bar`（复权）、`weekly`、`monthly`、`adj_factor`
**基础信息**：`stock_basic`、`trade_cal`、`index_basic`、`fund_basic`
**财务**：`income`、`balancesheet`、`cashflow`、`fina_indicator`、`forecast`、`express`
**指数**：`index_daily`、`index_weekly`、`index_member_all`
**基金**：`fund_nav`、`fund_share`、`fund_portfolio`
**宏观**：`cn_cpi`、`cn_ppi`、`cn_pmi`、`cn_gdp`、`cn_m`

**完整接口列表**（ETF/可转债/期货/港股/美股/龙虎榜/资金流/宏观等全部）与参数见 `references/数据接口.md`。

## 脚本使用

优先使用 `scripts/` 下的现成脚本，不要现场写代码：

```bash
# 股票日线（可复权）
python scripts/download_stock.py daily 600519.SH 20240101 20241231 --adj qfq --out data

# 股票列表
python scripts/download_stock.py stock_basic --out data

# 财务指标
python scripts/download_stock.py fina_indicator 600519.SH 20231231 --out data

# 交易日历
python scripts/download_stock.py trade_cal 2024 --out data

# 基金列表 / 净值
python scripts/download_fund.py fund_list --out data
python scripts/download_fund.py fund_nav 159915.SZ 20240101 20241231 --out data

# 直接导入 PostgreSQL（自动建表，默认覆盖；--append 追加）
python scripts/download_stock.py stock_basic --fmt db --table stock_basic
python scripts/download_fund.py fund_nav 159915.SZ 20240101 20241231 --fmt db

# 导出 parquet
python scripts/download_stock.py daily 600519.SH 20240101 20241231 --fmt parquet --out data
```

脚本内部已处理：token 读取（.env / 环境变量 / `ts.get_token()`）、分段拉取、合并去重、按 `--fmt` 导出（csv / parquet / 导入 PostgreSQL）。

## 错误处理

- **token 缺失**：提示在 .env 配置 `TUSHARE_TOKEN`
- **积分/权限不足**：提示升级积分或换用有权限的接口
- **空结果**：区分非交易日 / 区间无数据 / 标的未上市 / 参数错误 / 无权限
- **分段失败**：明确告知哪些时间段失败，不要整体说"成功"

## 最佳实践

- 能少取就少取，先核心字段再扩展
- 长区间一定要分段，避免撞接口行数上限
- 重复拉取优先复用已有文件，避免浪费积分
- 输出文件规范命名并记录元信息，方便复用
- 大批量多标的：按标的分批 + 日期分段