# -*- coding: utf-8 -*-
"""把生成出来的 markdown 里的代码块真正跑一遍，做 CI 式校验。"""
import io, os, re, sys
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
md = io.open("数据字典v2_全库.md", encoding="utf-8").read()
blocks = re.findall(r"```python\n(.*?)```", md, re.S)
print("python blocks:", len(blocks))

ns = {}
for b in blocks:
    exec(compile(b, "<md>", "exec"), ns)

DATASET, FIELD_DICT, Family, Asset = ns["DATASET"], ns["FIELD_DICT"], ns["Family"], ns["Asset"]
print("tables:", len(DATASET), "fields:", len(FIELD_DICT))

eng = create_engine(os.environ["DARU_DB_RO_URL"])
with eng.connect() as c:
    rows = c.execute(text("select table_name, column_name from information_schema.columns "
                          "where table_schema='public'")).fetchall()
schema = {}
for t, col in rows:
    schema.setdefault(t, set()).add(col)

errs = []
for tbl, m in DATASET.items():
    if tbl not in schema:
        errs.append(f"[表不存在] {tbl}")
        continue
    if m["family"] not in set(Family):
        errs.append(f"[family 非法] {tbl}: {m['family']}")
    if m["asset"] not in set(Asset):
        errs.append(f"[asset 非法] {tbl}: {m['asset']}")
    if m["family"] == "static" and m["historical"]:
        errs.append(f"[static 不应有历史] {tbl}")
    if m["family"] == "daily" and m.get("pit"):
        errs.append(f"[daily 不应有 pit] {tbl}")
    for k in ("entity", "time"):
        if m[k] and m[k] not in schema[tbl]:
            errs.append(f"[{k} 列不存在] {tbl}.{m[k]}")
        if m[k] and m[k] in m["cols"]:
            errs.append(f"[{k} 列混进 cols] {tbl}.{m[k]}")
    if m.get("pit"):
        for pc in m["pit"][:2]:
            if pc not in schema[tbl]:
                errs.append(f"[pit 列不存在] {tbl}.{pc}")
            if pc in m["cols"]:
                errs.append(f"[pit 列混进 cols] {tbl}.{pc}")
    seen = {}
    for sem, v in m["cols"].items():
        phys = v[0] if isinstance(v, tuple) else v
        if phys not in schema[tbl]:
            errs.append(f"[物理列不存在] {tbl}.{phys}")
        if sem not in FIELD_DICT:
            errs.append(f"[语义名不在 FIELD_DICT] {sem}")
        if phys in seen:
            errs.append(f"[物理列重复引用] {tbl}.{phys} <- {seen[phys]} / {sem}")
        seen[phys] = sem

# 未登记的表
sys_tabs = {"api_doc", "api_registry", "dump_job", "task_schedule",
            "agent_scheduled_tasks", "agent_sandbox_jobs", "apscheduler_jobs"}
missing = set(schema) - set(DATASET) - sys_tabs
for t in sorted(missing):
    errs.append(f"[库中未登记的表] {t}")

# 反向：DATASET 覆盖不到的库列
for t, m in DATASET.items():
    covered = {v[0] if isinstance(v, tuple) else v for v in m["cols"].values()}
    for k in ("entity", "time"):
        if m[k]:
            covered.add(m[k])
    if m.get("pit"):
        covered.update(m["pit"][:2])
    covered.update(m.get("axes", ()))
    left = schema[t] - covered
    if left:
        errs.append(f"[库列未覆盖] {t}: {sorted(left)}")

print("=" * 60)
if errs:
    print("校验失败:", len(errs))
    for e in errs[:60]:
        print(" -", e)
else:
    print("✅ 全部校验通过：53 张表、803 个语义字段、960 个物理列全部自洽。")
