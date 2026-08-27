---
name: sql-pro
description: 当用户需要 SQL 开发、数据库设计、查询优化、性能调优，或跨 PostgreSQL、MySQL、SQL Server、Oracle 平台的数据库管理时使用。
---

# SQL Pro

## 目的

提供跨主流数据库平台（PostgreSQL、MySQL、SQL Server、Oracle）的专业 SQL 开发能力，专注于复杂查询设计、性能优化与数据库架构。精通 ANSI SQL 标准、各平台特性优化以及现代数据处理模式，注重效率与可扩展性。

## 何时使用

- 编写包含 JOIN、CTE、窗口函数或递归查询的复杂 SQL 查询
- 为新应用设计数据库 Schema 或重构现有 Schema
- 通过执行计划分析优化慢 SQL 查询
- 不同数据库平台间的数据迁移（如 MySQL → PostgreSQL）
- 实现存储过程、函数或触发器
- 使用高级聚合和窗口函数构建分析报表
- 将业务需求转化为 SQL 查询逻辑
- 跨平台 SQL 兼容性问题（不同方言）

## 快速开始

**应调用此技能当：**
- 编写包含 CTE、窗口函数或递归模式的复杂查询
- 设计或重构数据库 Schema
- 通过执行计划分析优化慢查询
- 在不同数据库平台间迁移数据
- 实现存储过程、函数或触发器
- 构建使用高级聚合的分析报表

**不应调用当：**
- 需要 PostgreSQL 专属特性 → 使用 postgres-pro
- MySQL 专属管理 → 使用 database-administrator
- 简单增删改查操作 → 使用 backend-developer
- ORM 查询模式 → 使用相应的语言技能

## 决策框架

### CTE vs 子查询 vs JOIN 决策树

```
查询需求分析
│
├─ 需要多次引用同一结果集？
│  └─ 是 → 使用 CTE（避免子查询重复计算）
│     WITH user_totals AS (SELECT ...)
│     SELECT * FROM user_totals WHERE ...
│     UNION ALL
│     SELECT * FROM user_totals WHERE ...
│
├─ 递归数据遍历（层级、图结构）？
│  └─ 是 → 使用递归 CTE（递归的唯一方案）
│     WITH RECURSIVE tree AS (
│       SELECT ... -- 锚点
│       UNION ALL
│       SELECT ... FROM tree ... -- 递归
│     )
│
├─ 简单查找或过滤？
│  └─ 使用 JOIN（查询优化器最易优化）
│     SELECT u.*, o.total
│     FROM users u
│     JOIN orders o ON u.id = o.user_id
│
├─ WHERE 子句中的关联子查询？
│  ├─ 判断是否存在 → 使用 EXISTS（命中即停止）
│  │  WHERE EXISTS (SELECT 1 FROM orders WHERE user_id = u.id)
│  │
│  └─ 数值比较 → 改用 JOIN
│     -- 差：WHERE (SELECT COUNT(*) FROM orders WHERE user_id = users.id) > 5
│     -- 好：JOIN (SELECT user_id, COUNT(*) as cnt FROM orders GROUP BY user_id)
│
└─ 可读性 vs 性能权衡？
   ├─ 逻辑复杂、可读性优先 → CTE
   │  （更易理解、调试、维护）
   │
   └─ 性能优先、逻辑简单 → 子查询或 JOIN
      （查询优化器可内联并优化）
```

### 窗口函数 vs GROUP BY 决策矩阵

| 需求 | 方案 | 示例 |
|------|------|------|
| 需要聚合 + 行级明细 | 窗口函数 | `SELECT name, salary, AVG(salary) OVER () as avg_salary FROM employees` |
| 仅需聚合结果 | GROUP BY | `SELECT dept, AVG(salary) FROM employees GROUP BY dept` |
| 排名/行号 | 窗口函数（ROW_NUMBER、RANK、DENSE_RANK） | `ROW_NUMBER() OVER (ORDER BY sales DESC)` |
| 累计值/移动平均 | 带窗口框架的窗口函数 | `SUM(amount) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)` |
| LAG/LEAD（访问前后行） | 窗口函数 | `LAG(price, 1) OVER (ORDER BY date) as prev_price` |
| 百分位 / NTILE | 窗口函数 | `NTILE(4) OVER (ORDER BY score) as quartile` |
| 按组简单计数/求和/平均 | GROUP BY（更高效） | `SELECT category, COUNT(*) FROM products GROUP BY category` |

### 危险信号 → 升级处理

| 现象 | 为何需要升级 | 示例 |
|------|--------------|------|
| 执行计划中出现笛卡尔积 | 非预期交叉连接导致行数指数级膨胀 | "查询返回数百万行" |
| 复杂多层递归 CTE 出现性能问题 | 需要高级优化手段 | "递归 CTE 遍历 10+ 层、10 万个节点" |
| 跨平台迁移存在不兼容特性 | 需要平台特性映射 | "将 Oracle CONNECT BY 迁移到 PostgreSQL 递归 CTE" |
| 10+ 连接的复杂查询 | 架构异味，可能需重新设计 | "单条查询连接 15 张表" |
| 复杂时间序列逻辑的时序查询 | 高级分析模式 | "SCD Type 2 带历史快照" |

## 核心能力

### 高级查询模式
- 公共表表达式（CTE）与递归查询
- 窗口函数：ROW_NUMBER、RANK、LEAD、LAG、聚合窗口
- PIVOT/UNPIVOT 数据转换操作
- 树/图结构的层级查询
- 基于时间的时序分析查询

### 查询优化
- 执行计划分析与解读
- 索引选择策略与覆盖索引
- 统计信息管理与维护
- 查询提示与计划指南（必要时）
- 并行查询执行调优

### 索引设计模式
- 聚集索引与非聚集索引
- 用于查询优化的覆盖索引
- 选择性查询的过滤/部分索引
- 基于函数/表达式的索引
- 复合索引列顺序

## 质量检查清单

**查询性能：**
- [ ] 执行时间满足要求（OLTP: <100ms，分析型: <5s）
- [ ] 所有复杂查询均检查过 EXPLAIN ANALYZE
- [ ] 大表上无顺序扫描（除非有意为之）
- [ ] 索引被有效利用（检查执行计划）
- [ ] 无 N+1 查询模式（已消除关联子查询）

**SQL 质量：**
- [ ] SELECT 只包含必要列（不用 SELECT *）
- [ ] 多表查询使用显式表别名
- [ ] 正确处理 NULL（使用 COALESCE、IS NULL 而非 = NULL）
- [ ] 比较时数据类型匹配（无隐式转换）
- [ ] 使用参数化查询（防 SQL 注入）

**优化：**
- [ ] 适用处用窗口函数替代自连接
- [ ] 用 EXISTS 替代 NOT IN 以获得更好的 NULL 处理
- [ ] 对高频查询建议覆盖索引
- [ ] 重写查询以消除关联子查询

**文档：**
- [ ] 复杂查询逻辑用注释说明
- [ ] CTE 命名具描述性、自解释
- [ ] 记录预期输出格式
- [ ] 记录性能特征

## 其他资源

- **详细技术参考**：见 [REFERENCE.md](REFERENCE.md)
- **代码示例与模式**：见 [EXAMPLES.md](EXAMPLES.md)
