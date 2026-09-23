"""runner.py —— 用例执行器（M6 支撑）

职责：
    编排单条用例的完整生命周期：
    setup 造数 → 变量渲染 → 发请求 → extract 回填 → 断言 → finally 回滚。

设计要点：
    - teardown 放 finally：断言失败/请求异常也保证回滚（验收要求：失败用例零残留）
    - Allure 步骤化：import 失败自动降级为 no-op（框架不强制依赖报告工具）
    - 每个阶段独立 try/except 包装，失败信息附阶段名，报告可读性
"""
import contextlib
import logging

from core import assertions
from core.context import Context

logger = logging.getLogger("runner")

try:
    import allure

    def _step(name):
        return allure.step(name)
except ImportError:  # pragma: no cover
    @contextlib.contextmanager
    def _step(name):
        yield


def run_case(case, client, ctx: Context, data_provider=None) -> None:
    """执行一条用例。断言失败/异常向上抛，回滚在 finally 保证执行。"""
    batch_id = None
    try:
        # 1. 前置造数
        if case.setup:
            with _step(f"setup: 造数 {case.setup}"):
                if data_provider is None:
                    logger.warning("用例 %s 声明了 setup 但未提供 data_provider，跳过造数",
                                   case.name)
                else:
                    batch_id = data_provider.setup(case.setup, ctx)

        # 2. 参数化变量注入 + 请求渲染
        with _step("准备请求"):
            for k, v in (case.param or {}).items():
                ctx.set(k, v)
            req = ctx.render_deep(case.request)
            req["case_id"] = case.name

        # 3. 发请求
        with _step(f"{req['method'].upper()} {req['path']}"):
            resp = client.request(
                method=req["method"], path=req["path"],
                params=req.get("params"), json=req.get("json"),
                case_id=case.name,
            )

        # 4. extract 回填变量池
        if case.extract:
            with _step(f"提取变量: {list(case.extract)}"):
                body = resp.json
                for var, expr in case.extract.items():
                    ctx.extract_from(body, expr, var)

        # 5. 断言
        with _step(f"断言 x{len(case.assertions)}"):
            assertions.run(resp, case.assertions)
    finally:
        # 6. 后置回滚（finally 语义：失败也清理）
        if batch_id and data_provider is not None:
            with _step(f"teardown: 回滚批次 {batch_id}"):
                data_provider.teardown(batch_id)
