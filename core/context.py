"""context.py —— 变量池（M1）

职责：
    用例级上下文：存储变量、渲染 ${var} 占位符、extract 提取写入。
    与项目1 的 ${rule(args)} 渲染引擎同一套正则思路。

设计结论（评审定稿）：
    1. 类型边界：整串单一占位符保留原生类型（${age} -> 18）；
       混排统一转字符串（"a_${age}" -> "a_18"）。项目1 踩坑迁移。
    2. render_deep 递归处理 dict/list/str，其他类型原样返回。
    3. extract 失败抛 ExtractError，不静默跳过——
       宁可早死，不可带病运行（静默空值会造成更难查的假失败）。

约束：
    纯 Python 逻辑，不依赖 requests/pytest，保证可独立单测。
"""
import re


class ExtractError(Exception):
    """JSONPath 提取失败（命中不了路径/目标为 None）"""


class Context:
    """变量池"""

    VAR_PATTERN = re.compile(r"^\$\{(\w+)\}$")          # 整串单一占位符
    VAR_SCAN = re.compile(r"\$\{(\w+)\}")               # 混排扫描

    def __init__(self) -> None:
        self._store: dict = {}

    # ---------- 存取 ----------
    def set(self, key: str, value) -> None:
        self._store[key] = value

    def get(self, key: str, default=None):
        return self._store.get(key, default)

    # ---------- 渲染 ----------
    def render(self, text: str):
        """渲染字符串中的 ${var}。

        - 整串恰好是 ${var}：返回变量的原生类型值
        - 混排：全部替换为字符串并拼接
        - 出现未定义变量：抛 KeyError，变量名给出明确提示
        """
        full = self.VAR_PATTERN.match(text)
        if full:
            key = full.group(1)
            if key not in self._store:
                raise KeyError(f"变量未定义: ${{{key}}}（整串占位符保留原生类型）")
            return self._store[key]

        def _sub(m: re.Match) -> str:
            key = m.group(1)
            if key not in self._store:
                raise KeyError(f"变量未定义: ${{{key}}}")
            return str(self._store[key])

        return self.VAR_SCAN.sub(_sub, text)

    def render_deep(self, obj):
        """递归渲染：dict 渲染 values，list 渲染元素，str 走 render，
        其余类型（int/bool/None/float...）原样返回。"""
        if isinstance(obj, str):
            return self.render(obj)
        if isinstance(obj, dict):
            return {k: self.render_deep(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.render_deep(v) for v in obj]
        return obj

    # ---------- 提取 ----------
    def extract_from(self, response_json, expr: str, var_name: str):
        """按 JSONPath（简化版 $.a.b.0 形式）从响应提取值并写入变量池。

        失败抛 ExtractError：
            - 路径中途缺失 / 下标越界 / 最终值为 None
        成功则 self.set(var_name, value) 并返回 value。
        """
        current = response_json
        tokens = expr.lstrip("$").lstrip(".").split(".") if expr.startswith("$.") else expr.split(".")
        walked = "$"
        for token in tokens:
            if isinstance(current, dict) and token in current:
                current = current[token]
            elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
                current = current[int(token)]
            else:
                raise ExtractError(f"JSONPath 提取失败: {expr}（在 {walked} 处断开）")
            walked += f".{token}"
        if current is None:
            raise ExtractError(f"JSONPath 提取结果为 None: {expr}")
        self.set(var_name, current)
        return current
