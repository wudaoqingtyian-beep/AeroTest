"""assertions.py —— 断言引擎（M4）

职责：
    断言注册表（策略模式，与项目1 规则注册表同构）。
    新增断言 = register 装饰器注册一个函数，不改引擎（开闭原则）。

失败输出统一格式：断言失败 [type] path: 期望 x / 实际 y（禁止裸 raise）。
"""
import re

from core.jsonpath import resolve

ASSERTERS: dict = {}


def register(name: str):
    def deco(fn):
        ASSERTERS[name] = fn
        return fn
    return deco


def _fail(ctype: str, spec: dict, expected, actual) -> AssertionError:
    path = spec.get("path", "-")
    return AssertionError(
        f"断言失败 [{ctype}] {path}: 期望 {expected!r} / 实际 {actual!r}"
    )


@register("status_eq")
def _status_eq(response, spec: dict):
    expected = spec["expected"]
    if response.status != expected:
        raise _fail("status_eq", spec, expected, response.status)


@register("json_eq")
def _json_eq(response, spec: dict):
    expected = spec["expected"]
    try:
        actual = resolve(response.json, spec["path"])
    except KeyError as e:
        raise _fail("json_eq", spec, expected, f"路径不存在({e})")
    if actual != expected:
        raise _fail("json_eq", spec, expected, actual)


@register("json_contains")
def _json_contains(response, spec: dict):
    expected = spec["expected"]
    try:
        actual = resolve(response.json, spec["path"])
    except KeyError as e:
        raise _fail("json_contains", spec, expected, f"路径不存在({e})")
    if expected not in actual:
        raise _fail("json_contains", spec, expected, actual)


@register("json_regex")
def _json_regex(response, spec: dict):
    pattern = spec["expected"]
    try:
        actual = resolve(response.json, spec["path"])
    except KeyError as e:
        raise _fail("json_regex", spec, pattern, f"路径不存在({e})")
    if not re.search(pattern, str(actual)):
        raise _fail("json_regex", spec, pattern, actual)


@register("elapsed_lt")
def _elapsed_lt(response, spec: dict):
    expected = spec["expected"]
    if response.elapsed_ms >= expected:
        raise _fail("elapsed_lt", spec, f"<{expected}ms", f"{response.elapsed_ms}ms")


@register("db_eq")
def _db_eq(response, spec: dict):
    """数据库断言：验证落库结果。spec: {sql, expected, field?}"""
    expected = spec["expected"]
    row = _fetch_one(spec["sql"])
    if row is None:
        raise _fail("db_eq", spec, expected, "查询无结果")
    field = spec.get("field")
    actual = row[field] if field else next(iter(row.values()))
    if actual != expected:
        raise _fail("db_eq", spec, expected, actual)


def _fetch_one(sql: str) -> dict | None:
    import yaml
    import pymysql

    with open("config/config.yaml", encoding="utf-8") as f:
        db = (yaml.safe_load(f) or {}).get("db") or {}
    conn = pymysql.connect(
        host=db.get("host", "127.0.0.1"), port=int(db.get("port", 3306)),
        user=db.get("user", "root"), password=db.get("password", ""),
        database=db.get("database"), charset="utf8mb4",
    )
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql)
            return cur.fetchone()
    finally:
        conn.close()


def run(response, assertions: list) -> None:
    """统一执行入口：依次执行断言列表，第一个失败即抛 AssertionError。"""
    for spec in assertions or []:
        ctype = spec.get("type")
        if ctype not in ASSERTERS:
            raise ValueError(f"未知断言类型: {ctype}（已注册: {sorted(ASSERTERS)}）")
        ASSERTERS[ctype](response, spec)
