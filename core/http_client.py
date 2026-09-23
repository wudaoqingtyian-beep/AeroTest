"""http_client.py —— 请求引擎（M2）

职责：
    封装 requests.Session：统一超时/重试/结构化日志/多环境 base_url。
    用例层永远不直接 import requests（case_loader/runner 不碰 requests）。

设计要点（白皮书 §3.1）：
    - ApiResponse 统一包装，解耦"请求怎么发"和"结果怎么验"
    - 重试自实现：仅幂等方法（GET/HEAD/OPTIONS）重试；带 body 的写请求不重放，
      区别于 urllib3 retry（后者不区分幂等性）
    - 构造函数支持直接注入 cfg（依赖注入），便于单测脱离配置文件运行
"""
import json
import logging
import time

import requests

from core.config import load_env_config

logger = logging.getLogger("http_client")

IDEMPOTENT = {"GET", "HEAD", "OPTIONS"}


class ApiResponse:
    """统一响应包装"""

    def __init__(self, status: int, headers: dict | None = None,
                 text: str = "", elapsed_ms: int = 0):
        self.status = status
        self.headers = headers or {}
        self.text = text
        self.elapsed_ms = elapsed_ms

    @classmethod
    def from_response(cls, resp: requests.Response) -> "ApiResponse":
        return cls(
            status=resp.status_code,
            headers=dict(resp.headers),
            text=resp.text,
            elapsed_ms=int(resp.elapsed.total_seconds() * 1000),
        )

    @property
    def json(self):
        try:
            return json.loads(self.text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"响应体不是合法 JSON（status={self.status}）: {self.text[:200]!r}"
            ) from e


class HttpClient:
    """请求引擎"""

    def __init__(self, env: str | None = None, cfg: dict | None = None,
                 config_dir: str = "config"):
        if cfg is None:
            if env is None:
                raise ValueError("env 与 cfg 至少提供一个")
            cfg = load_env_config(env, config_dir)
        self.env = env
        self.base_url = str(cfg.get("base_url", "")).rstrip("/")
        self.timeout = cfg.get("timeout", 10)
        self.retry = int(cfg.get("retry", 0))
        self.session = requests.Session()
        self.session.headers.update(cfg.get("headers") or {})

    def request(self, method: str, path: str, params=None, json=None,
                headers=None, case_id: str = "") -> ApiResponse:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        attempts = 1 + (self.retry if method.upper() in IDEMPOTENT else 0)
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                resp = self.session.request(
                    method.upper(), url, params=params, json=json,
                    headers=headers, timeout=self.timeout,
                )
                api = ApiResponse.from_response(resp)
                logger.info(
                    "case=%s %s %s -> %s elapsed=%sms attempt=%s",
                    case_id, method.upper(), url, api.status, api.elapsed_ms, attempt,
                )
                # 5xx 视为临时故障，幂等方法继续重试
                if api.status < 500 or method.upper() not in IDEMPOTENT \
                        or attempt == attempts:
                    return api
                last_resp = api
            except requests.RequestException as e:
                last_exc = e
                last_resp = None
                logger.warning("case=%s %s %s 请求异常(attempt=%s): %s",
                               case_id, method.upper(), url, attempt, e)
        if last_resp is not None:
            return last_resp
        raise last_exc  # type: ignore[misc]

    def get(self, path: str, **kw) -> ApiResponse:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw) -> ApiResponse:
        return self.request("POST", path, **kw)
