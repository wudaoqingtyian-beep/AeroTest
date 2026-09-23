"""case_loader.py —— 数据驱动（M3）

职责：
    YAML 用例：加载 → 静态校验 → 参数化展开。
    原则：宁可启动时报错，不要运行到一半才崩（项目1 loader 同思路）。

用例结构约定：
    name: 用例名
    request: {method, path, params?, json?}
    assertions: [{type, path?, expected}]   # type 必须命中断言注册表
    setup: [{template, count?, boundary?, var?}]   # M5 造数声明
    params: [{变量组1}, {变量组2}]           # 参数化：每组展开一条用例
    extract: {变量名: $.jsonpath}            # 响应提取回填变量池

占位符静态校验：
    request 中出现的 ${var} 必须能从 params/extract/setup(var) 获得来源，
    否则加载期即报错。
"""
import re
import yaml

from core.assertions import ASSERTERS

VAR_SCAN = re.compile(r"\$\{(\w+)\}")

ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


class Case:
    """单条用例的内存对象（加载产物）"""

    def __init__(self, name, request, assertions=None, setup=None,
                 teardown=None, extract=None, param=None, source=""):
        self.name = name
        self.request = request
        self.assertions = assertions or []
        self.setup = setup or []
        self.teardown = teardown or []
        self.extract = extract or {}
        self.param = param          # 参数化展开后该条用例对应的变量组
        self.source = source


def _validate(raw: dict, source: str) -> None:
    if not isinstance(raw, dict):
        raise ValueError(f"{source}: 用例必须是 YAML 映射")
    req = raw.get("request")
    if not isinstance(req, dict) or "method" not in req or "path" not in req:
        raise ValueError(f"{source}: request 必须包含 method 和 path")
    if str(req["method"]).upper() not in ALLOWED_METHODS:
        raise ValueError(f"{source}: 非法 method: {req['method']}")
    for spec in raw.get("assertions") or []:
        if not isinstance(spec, dict) or "type" not in spec:
            raise ValueError(f"{source}: assertions 每项必须含 type")
        if spec["type"] not in ASSERTERS:
            raise ValueError(
                f"{source}: 未知断言类型 {spec['type']}（已注册: {sorted(ASSERTERS)}）")
    # 占位符静态校验：used ⊆ provided
    provided = set((raw.get("extract") or {}).keys())
    for group in raw.get("params") or []:
        provided |= set(group.keys())
    for decl in raw.get("setup") or []:
        d = {"template": decl} if isinstance(decl, str) else decl
        provided.add(d.get("var") or d["template"])

    def _scan(obj):
        if isinstance(obj, str):
            yield from VAR_SCAN.findall(obj)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                yield from _scan(k)
                yield from _scan(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from _scan(v)

    unknown = set(_scan(raw.get("request") or {})) - provided
    if unknown:
        raise ValueError(
            f"{source}: 占位符无数据来源（params/extract/setup 均未提供）: {sorted(unknown)}")


def load_case(path: str) -> Case:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    _validate(raw if isinstance(raw, dict) else {}, path)
    name = raw.get("name") or path.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".yaml")
    return Case(
        name=name,
        request=raw["request"],
        assertions=raw.get("assertions") or [],
        setup=raw.get("setup") or [],
        teardown=raw.get("teardown") or [],
        extract=raw.get("extract") or {},
        source=path,
    )


def load_case_with_params(path: str) -> list:
    """加载用例并按 params 展开为多条（无 params 返回单条）。"""
    case = load_case(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    groups = raw.get("params") or []
    if not groups:
        return [case]
    return [
        Case(name=f"{case.name}[{i}]", request=case.request,
             assertions=case.assertions, setup=case.setup,
             teardown=case.teardown, extract=case.extract,
             param=group, source=case.source)
        for i, group in enumerate(groups)
    ]
