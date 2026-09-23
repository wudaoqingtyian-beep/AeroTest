"""data_provider.py —— 造数联动（M5，核心创新点）

职责：
    用例前后置钩子：调项目1 造数服务 → 数据回填变量池 → finally 回滚。

流程：
    setup    → POST /api/v1/data/generate → batch_id + rows 回填变量池
    teardown → POST /api/v1/data/rollback(batch_id)   # pytest finalizer 保证执行

降级设计：
    GET /api/v1/health 失败 → 切本地文件造数模式（fallback_dir 下
    {template}.json 为行列表），测试基建不得成为测试阻塞点。

接口契约（见 PRD §5）：
    POST /api/v1/data/generate  {template, count, boundary} -> {batch_id, rows}
    POST /api/v1/data/rollback  {batch_id} -> {deleted_rows}
    GET  /api/v1/health -> {"status": "ok"}
"""
import json
import logging
import os

import requests

from core.context import Context

logger = logging.getLogger("data_provider")


class DataProvider:
    def __init__(self, base_url: str, fallback_dir: str = "testcases/fallback_data",
                 timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.fallback_dir = fallback_dir
        self.timeout = timeout

    # ---------- 健康检查 ----------
    def healthy(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/v1/health", timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ---------- 前置造数 ----------
    def setup(self, declarations: list, ctx: Context) -> str | None:
        """执行 setup 声明列表，返回批次号（None = 降级模式）。

        declaration 形式：
            {template: user, count: 5, boundary: false, var: users}
            简写："user"（等价于 {template: user, var: user}）
        """
        batch_ids = []
        for decl in declarations:
            d = {"template": decl} if isinstance(decl, str) else dict(decl)
            template = d["template"]
            var = d.get("var") or template
            if self.healthy():
                resp = requests.post(
                    f"{self.base_url}/api/v1/data/generate",
                    json={"template": template,
                          "count": d.get("count", 1),
                          "boundary": d.get("boundary", False)},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
                batch_ids.append(payload["batch_id"])
                ctx.set(var, payload.get("rows"))
            else:
                rows = self._fallback_rows(template)
                ctx.set(var, rows)
                logger.info("造数服务不可用，已降级为本地文件造数: %s（%s 行）",
                            template, len(rows))
        return batch_ids[0] if batch_ids else None

    def _fallback_rows(self, template: str) -> list:
        path = os.path.join(self.fallback_dir, f"{template}.json")
        if not os.path.exists(path):
            logger.warning("降级数据缺失: %s，返回空列表", path)
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ---------- 后置回滚 ----------
    def teardown(self, batch_id: str | None) -> dict:
        """按批次精确回滚（None = 降级模式，无需回滚）。"""
        if not batch_id:
            return {"skipped": True}
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/data/rollback",
                json={"batch_id": batch_id}, timeout=self.timeout,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info("批次 %s 回滚完成: %s", batch_id, result)
            return result
        except requests.RequestException as e:
            # 回滚失败必须大声报出来——数据残留是环境事故
            logger.error("批次 %s 回滚失败，存在数据残留风险: %s", batch_id, e)
            raise
