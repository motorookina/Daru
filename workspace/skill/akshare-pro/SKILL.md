---
name: akshare-pro
description: 专用于从 AKShare 下载/导出金融数据的技能。当用户需要拉取、下载、导出期货主力连续、中债债券指数/收益率、回购利率、全市场/指数 PE/PB、申万行业指数、存款准备金率、央行基准利率等数据到本地文件（CSV/parquet）或 PostgreSQL 时使用。仅负责数据下载与导出，不包含投资分析。
---

# akshare-pro（数据下载）

专用于 **AKShare 数据下载与导出** 的技能。

## 前置条件

- **Python 3.7+**，需要安装 `akshare` 包（`pip install akshare`）
- **导入 PostgreSQL**：需要 `sqlalchemy` + PG 驱动（`psycopg`），并在 .env 配置 `DATABASE_URL`
- 需要网络访问各数据源：新浪财经、中债信息网、中国货币网、乐咕乐股、申万宏源研究、东方财富、金十数据等
- akshare 无需 token；数据源多为**公开网页抓取**，接口可能随上游改版失效，调用失败时按「错误处理」一节处理

## 这个技能用来做什么

- 下载期货主力连续合约日频行情（新浪）
- 下载中债综合指数、国债收益率曲线（中债信息网）
- 下载回购定盘利率历史（中国货币网）
- 下载全市场 / 指数的市盈率（PE）、市净率（PB）（乐咕乐股）
- 下载申万行业指数历史行情（申万宏源研究）
- 下载宏观数据：存款准备金率、央行基准利率
- 分段拉取、合并去重，导出 CSV / parquet 到本地，或直接导入 PostgreSQL（自动建表）

## 何时使用

当用户表达以下意图时优先使用：

- "把期货主力连续（PVC/铜/黄金）的日线数据下载下来"
- "导出中债综合指数 / 国债收益率到 CSV"
- "拉取上证 / 沪深300 的历史 PE、PB"
- "下载申万行业指数历史行情"
- "更新存款准备金率、央行基准利率"

## 何时不使用

- 需要 tushare / 理杏仁 特有数据（财务、股本、港股美股、估值细分等）→ 使用 `tushare-pro` / `lixinger-open-skill`
- 申万行业指数行情 → 本技能 `index_hist_sw` 与 tushare `sw_daily` **数据重叠**，落库注意去重
- 需要投资分析 / 选股 / 板块轮动 / 资金流解读 → 不负责投资分析
- 数据源接口失效且无法修复 → 明确告知，**不伪造数据**

## 环境检查

在请求数据前先确认：

1. `akshare` 包已安装（`pip install akshare`；import 失败按「错误处理」提示）
2. 若需落库，`.env` 已配置 `DATABASE_URL`
3. 接口参数严格遵守 `references/数据接口.md`：如 `bond_china_yield` / `repo_rate_hist` 区间**必须小于一年**、`stock_market_pe_lg` 的 `symbol` 注意"科创版"写法等

## 数据下载工作流

1. **解析任务**：接口名、标的/品种、时间范围、频率、字段、输出格式
2. **选接口**：从 `references/数据接口.md` 查找接口与参数（含可选值、字段、注意事项）
3. **分段拉取**：长区间自动分段（`futures_main_sina` 按年；`bond_china_yield` / `repo_rate_hist` 按 ~11 个月），规避单次区间上限
4. **合并去重**：分段结果 concat + drop_duplicates + 排序
5. **校验**：关键字段存在性、日期格式、空结果区分原因
6. **导出**：CSV / parquet / 落库，规范命名，记录元信息

## 时间默认值

- 用户未指定时间范围 → 优先和用户确认；未给出明确答案时，默认近一年。
- 长区间 → 自动分段（见工作流第 3 步）。

## 输出规范

- 文件命名：`{接口}_{关键参数}_{拉取日期}.csv`
  - 例：`futures_main_sina_V0_20260817.csv`、`stock_market_pe_lg_上证_20260817.csv`
- **输出格式**：`--fmt` 指定 `csv` / `parquet` / `db`（默认 csv）
- **导入数据库**：默认表名 = 接口名（可用 `--table` 覆盖），默认 `replace` 覆盖、`--append` 追加；连接串取 .env 的 `DATABASE_URL`（`--db-url` 可覆盖）
- 默认输出目录：`./data/`（脚本 `--out` 可改）
- 每次导出尽量记录：接口名、请求参数、拉取时间、行数、失败分段

## 常用接口（核心集）

| 接口 | 说明 | 参数要点 |
|------|------|----------|
| `futures_main_sina` | 期货主力连续日频 | `symbol`（如 `V0`）+ `start_date` + `end_date`，品种表见参考文档 |
| `bond_new_composite_index_cbond` | 中债综合指数（**调用最密集，共33处**） | `indicator` + `period` |
| `bond_china_yield` | 中债国债收益率 | `start_date`/`end_date` 区间** <1 年** |
| `repo_rate_hist` | 回购定盘利率历史 | `start_date`/`end_date` 区间** <1 年** |
| `stock_market_pe_lg` | 全市场 PE | `symbol`：上证 / 深证 / 创业板 / **科创版** |
| `stock_market_pb_lg` | 全市场 PB | 同上 |
| `stock_index_pe_lg` | 指数 PE | `symbol`（12 个指数名） |
| `stock_index_pb_lg` | 指数 PB | 同上 |
| `index_hist_sw` | 申万行业指数历史 | `symbol` + `period`（day/week/month）；与 tushare `sw_daily` 去重 |
| `macro_china_reserve_requirement_ratio` | 存款准备金率 | 无参数 |
| `macro_bank_china_interest_rate` | 央行基准利率 | 无参数 |

**完整参数、可选值、输出字段、示例与注意事项见 `references/数据接口.md`。**

## 脚本使用

优先使用 `scripts/` 下的现成脚本，不要现场写代码：

```bash
# 期货主力连续（PVC，2020-2021）
python scripts/download_akshare.py futures_main_sina V0 20200101 20220101 --out data

# 中债综合指数（财富，总值）
python scripts/download_akshare.py bond_new_composite_index_cbond --indicator 财富 --period 总值 --out data

# 国债收益率（区间须 <1 年；超长自动分段）
python scripts/download_akshare.py bond_china_yield 20210201 20220201 --out data

# 回购定盘利率
python scripts/download_akshare.py repo_rate_hist 20231001 20240101 --out data

# 全市场 / 指数 PE、PB
python scripts/download_akshare.py stock_market_pe_lg 上证 --out data
python scripts/download_akshare.py stock_market_pb_lg 上证 --out data
python scripts/download_akshare.py stock_index_pe_lg 上证50 --out data
python scripts/download_akshare.py stock_index_pb_lg 上证50 --out data

# 申万行业指数（日频）
python scripts/download_akshare.py index_hist_sw 801193 --period day --out data

# 宏观：存款准备金率 / 央行基准利率（无参数）
python scripts/download_akshare.py macro_china_reserve_requirement_ratio --out data
python scripts/download_akshare.py macro_bank_china_interest_rate --out data

# 直接导入 PostgreSQL（自动建表，默认覆盖；--append 追加）
python scripts/download_akshare.py stock_market_pe_lg 上证 --fmt db --table stock_market_pe_lg

# 导出 parquet
python scripts/download_akshare.py futures_main_sina V0 20200101 20220101 --fmt parquet --out data
```

脚本内部已处理：akshare 懒加载、失败重试、分段拉取、合并去重、按 `--fmt` 导出（csv / parquet / 导入 PostgreSQL）。

## 错误处理

- **akshare 未安装**：提示 `pip install akshare`
- **数据源接口失效**：akshare 数据源多为公开网页抓取，可能随上游改版失效。给出可操作提示（重试、换日期范围、向维护者反馈），**不伪造数据**
- **空结果**：区分非交易日 / 区间无数据 / 参数错误（尤其 `symbol` 可选值写错，如"科创版"）
- **分段失败**：明确告知哪些时间段失败，不要整体说"成功"

## 最佳实践

- 先查已有数据范围，**增量更新**（配合 data-workflow / sql-pro），不整表重拉
- 长区间一定分段，避免撞接口区间上限
- 期货品种代码用 `ak.futures_display_main_sina()` 或参考文档品种表获取
- 申万指数 `index_hist_sw` 与 tushare `sw_daily` 重叠，落库注意去重
- 输出文件规范命名并记录元信息，方便复用
- 大批量多标的：按标的分批 + 日期分段，脚本一次跑完

## 与其它技能的关系

| 技能 | 负责 |
|------|------|
| `data-workflow` | 怎么安排：先查→增量→批量→幂等→收尾 |
| `sql-pro` | 怎么存：建表、批量写入、upsert、查询已有范围 |
| `tushare-pro` | 怎么拉 tushare 数据（与 akshare 互补；申万指数注意去重） |
| `akshare-pro`（本技能） | 怎么拉 akshare 数据 |
