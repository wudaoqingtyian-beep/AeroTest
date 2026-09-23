"""jsonpath.py —— 简化版 JSONPath 求值（M4 支撑）

支持 $.a.b.0.c 形式（点号路径 + 数组下标），满足接口断言的绝大多数场景。
失败抛 KeyError 并带断开位置，方便定位。
"""


def resolve(obj, expr: str):
    tokens = expr[2:].split(".") if expr.startswith("$.") else expr.split(".")
    current, walked = obj, "$"
    for token in tokens:
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise KeyError(f"JSONPath 解析失败: {expr}（在 {walked} 处断开）")
        walked += f".{token}"
    return current
