# SQL Pro - 代码示例与模式

## 层级数据的递归 CTE

**场景**：组织架构 - 查找某经理下的所有员工（含间接下属）

```sql
-- 创建员工表
CREATE TABLE employees (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100),
  manager_id INTEGER REFERENCES employees(id),
  title VARCHAR(100),
  salary DECIMAL(10,2)
);

-- 查找 Bob 副总裁(id=2) 下的所有员工（含间接下属）
WITH RECURSIVE org_tree AS (
  -- 锚点：起点（Bob 副总裁本人）
  SELECT 
    id,
    name,
    manager_id,
    title,
    salary,
    0 as depth,  -- 记录层级深度
    ARRAY[id] as path,  -- 记录从根开始的路径（防止循环）
    name::TEXT as hierarchy  -- 可视化层级
  FROM employees
  WHERE id = 2  -- 起点：Bob 副总裁
  
  UNION ALL
  
  -- 递归：查找当前层的直接下属
  SELECT 
    e.id,
    e.name,
    e.manager_id,
    e.title,
    e.salary,
    ot.depth + 1,
    ot.path || e.id,  -- 追加到路径
    ot.hierarchy || ' > ' || e.name  -- 构建可视化层级
  FROM employees e
  INNER JOIN org_tree ot ON e.manager_id = ot.id
  WHERE NOT (e.id = ANY(ot.path))  -- 防止无限循环（环检测）
)

SELECT 
  id,
  REPEAT('  ', depth) || name as indented_name,  -- 可视化缩进
  title,
  salary,
  depth,
  hierarchy
FROM org_tree
ORDER BY path;  -- 深度优先遍历
```

## 带总数的分页

```sql
-- 模板：用窗口函数在单条查询中同时实现分页与总数
WITH paginated_users AS (
  SELECT 
    id,
    name,
    email,
    created_at,
    COUNT(*) OVER () as total_count  -- 无需额外查询即可得到总数
  FROM users
  WHERE status = 'active'
  ORDER BY created_at DESC
  LIMIT 20 OFFSET 40  -- 第 3 页（每页 20 条）
)
SELECT * FROM paginated_users;

/*
每行都带 total_count，无需单独 COUNT 查询：
id  | name  | email       | created_at | total_count
----|-------|-------------|------------|------------
123 | Alice | a@email.com | 2024-03-15 | 5432
124 | Bob   | b@email.com | 2024-03-14 | 5432
*/
```

## 条件聚合（透视表）

```sql
-- 不用 PIVOT 语法实现透视（跨所有数据库通用）
SELECT 
  EXTRACT(YEAR FROM sale_date) as year,
  SUM(CASE WHEN EXTRACT(QUARTER FROM sale_date) = 1 THEN amount ELSE 0 END) as q1_sales,
  SUM(CASE WHEN EXTRACT(QUARTER FROM sale_date) = 2 THEN amount ELSE 0 END) as q2_sales,
  SUM(CASE WHEN EXTRACT(QUARTER FROM sale_date) = 3 THEN amount ELSE 0 END) as q3_sales,
  SUM(CASE WHEN EXTRACT(QUARTER FROM sale_date) = 4 THEN amount ELSE 0 END) as q4_sales,
  SUM(amount) as total_sales
FROM sales
WHERE sale_date >= '2024-01-01'
GROUP BY EXTRACT(YEAR FROM sale_date);

/*
输出：
year | q1_sales | q2_sales | q3_sales | q4_sales | total_sales
-----|----------|----------|----------|----------|------------
2024 | 125000   | 145000   | 167000   | 189000   | 626000
*/
```

## 索引覆盖检查

```sql
-- 模板：检查查询能否使用仅索引扫描
-- 1. 识别 WHERE、JOIN、ORDER BY 中的列
-- 2. 识别 SELECT 中的列
-- 3. 创建覆盖索引

-- 示例查询：
SELECT user_id, created_at, total 
FROM orders 
WHERE status = 'completed' AND created_at >= '2024-01-01'
ORDER BY created_at DESC;

-- 覆盖索引设计：
CREATE INDEX idx_orders_status_created_covering
  ON orders (status, created_at DESC)  -- 过滤 + 排序列
  INCLUDE (user_id, total);  -- SELECT 列（PostgreSQL）

-- MySQL 等价写法：
CREATE INDEX idx_orders_status_created_covering
  ON orders (status, created_at DESC, user_id, total);

-- 用 EXPLAIN 验证：查找 "Index Only Scan"（PostgreSQL）或 "Using index"（MySQL）
```

## 反模式与修复

### 反模式：生产代码中使用 SELECT *

**差：**
```sql
-- 选择了所有列（即使只需 3 列）
SELECT * FROM users WHERE id = 123;

-- 用 SELECT * 做连接
SELECT * FROM orders o
JOIN users u ON o.user_id = u.id
WHERE o.status = 'pending';
```

**为什么不好：**
- **性能**：取回不必要的数据（网络传输、内存开销）
- **索引覆盖**：无法使用仅索引扫描（必须访问堆表）
- **破坏性变更**：Schema 变化会破坏应用代码
- **歧义**：连接时列名冲突（究竟是哪个表的 'id'？）

**好：**
```sql
-- 只选择所需列
SELECT id, email, name, created_at 
FROM users 
WHERE id = 123;

-- 连接时显式列名（用表别名限定）
SELECT 
  o.id as order_id,
  o.total,
  o.status,
  u.email,
  u.name
FROM orders o
JOIN users u ON o.user_id = u.id
WHERE o.status = 'pending';

-- 额外收益：可以使用覆盖索引
CREATE INDEX idx_users_id_covering 
  ON users (id) 
  INCLUDE (email, name, created_at);  -- 可实现仅索引扫描
```

### 反模式：WHERE 子句中的隐式类型转换

**差：**
```sql
-- user_id 是 INTEGER，却用字符串比较
SELECT * FROM orders WHERE user_id = '12345';

-- created_at 是 TIMESTAMP，却用字符串比较
SELECT * FROM orders WHERE created_at = '2024-03-15';

-- phone_number 是 VARCHAR，却用数字比较
SELECT * FROM users WHERE phone_number = 1234567890;
```

**为什么不好：**
- **索引失效**：类型不匹配导致无法使用索引（退化为全表扫描）
- **隐式转换开销**：数据库要转换每一行的值（变慢）
- **行为不一致**：不同数据库对转换的处理方式不同

**好：**
```sql
-- 使用正确的数据类型
SELECT * FROM orders WHERE user_id = 12345;  -- INTEGER

-- 必要时显式类型转换
SELECT * FROM orders WHERE created_at = '2024-03-15'::DATE;

-- 或使用正确的时间戳范围
SELECT * FROM orders WHERE created_at >= '2024-03-15 00:00:00'::TIMESTAMP
  AND created_at < '2024-03-16 00:00:00'::TIMESTAMP;

-- VARCHAR 用字符串比较
SELECT * FROM users WHERE phone_number = '1234567890';

-- 用 EXPLAIN 验证索引使用
EXPLAIN SELECT * FROM orders WHERE user_id = 12345;
-- 应显示 "Index Scan" 或 "Index Seek"，而非 "Seq Scan"
```

## 查询优化示例

```sql
-- 优化前：多次扫描、低效连接
SELECT o.order_id, c.customer_name, SUM(oi.quantity * oi.price) as total
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_date >= '2024-01-01'
GROUP BY o.order_id, c.customer_name;

-- 优化后：覆盖索引 + CTE
WITH recent_orders AS (
  SELECT order_id, customer_id, order_date
  FROM orders
  WHERE order_date >= '2024-01-01'
)
SELECT ro.order_id, c.customer_name, SUM(oi.quantity * oi.price) as total
FROM recent_orders ro
JOIN customers c ON ro.customer_id = c.customer_id
JOIN order_items oi ON ro.order_id = oi.order_id
GROUP BY ro.order_id, c.customer_name;

-- 覆盖索引
CREATE INDEX idx_orders_date_customer ON orders(order_date, customer_id) INCLUDE (order_id);
```
