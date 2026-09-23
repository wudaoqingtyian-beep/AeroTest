"""M6 集成测试：假服务器 + YAML 用例 + 造数 mock 全链路跑通 runner"""
import textwrap

import pytest
import requests

from core.context import Context
from core.data_provider import DataProvider
from core.http_client import HttpClient
from core.runner import run_case

CASE = textwrap.dedent("""
    name: 查询用户-集成
    setup:
      - template: user
        count: 1
        var: user_rows
    request:
      method: GET
      path: /user
      params:
        id: "${uid}"
    extract:
      token: $.data.token
    assertions:
      - type: status_eq
        expected: 200
      - type: json_eq
        path: $.data.id
        expected: 42
    params:
      - uid: 42
""")


@pytest.fixture
def setup_rollback_recorder(monkeypatch):
    """把 DataProvider 的 HTTP 调用替换为记录器，验证 setup/teardown 闭环"""
    calls = {"generate": 0, "rollback": []}

    def fake_get(url, timeout=None):
        return type("R", (), {"status_code": 200})()

    def fake_post(url, json=None, timeout=None):
        if url.endswith("/generate"):
            calls["generate"] += 1
            return FakeR(200, {"batch_id": "B900", "rows": [{"id": 42}]})
        calls["rollback"].append(json["batch_id"])
        return FakeR(200, {"deleted_rows": 1})

    class FakeR:
        def __init__(self, code, payload):
            self.status_code, self._p = code, payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._p

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)
    return calls


def write_case(tmp_path, content):
    p = tmp_path / "integration.yaml"
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestEndToEnd:
    def test_full_lifecycle_success(self, tmp_path, fake_base_url,
                                    setup_rollback_recorder):
        from core.case_loader import load_case_with_params
        case = load_case_with_params(write_case(tmp_path, CASE))[0]

        client = HttpClient(cfg={"base_url": fake_base_url, "timeout": 5,
                                 "retry": 0, "headers": {}})
        dp = DataProvider(base_url="http://fake", fallback_dir=str(tmp_path))
        ctx = Context()
        run_case(case, client, ctx, dp)  # 不抛即通过

        calls = setup_rollback_recorder
        assert calls["generate"] == 1                      # setup 造数发生
        assert calls["rollback"] == ["B900"]               # teardown 回滚发生
        assert ctx.get("token") == "tok123"                # extract 已回填变量池

    def test_assertion_failure_still_rolls_back(self, tmp_path, fake_base_url,
                                                setup_rollback_recorder):
        """验收红线：断言失败时 teardown 依然执行（finally 语义）"""
        bad = CASE.replace("expected: 42", "expected: 999")
        from core.case_loader import load_case_with_params
        case = load_case_with_params(write_case(tmp_path, bad))[0]

        client = HttpClient(cfg={"base_url": fake_base_url, "timeout": 5,
                                 "retry": 0, "headers": {}})
        dp = DataProvider(base_url="http://fake", fallback_dir=str(tmp_path))
        with pytest.raises(AssertionError):
            run_case(case, client, ctx := Context(), dp)

        assert setup_rollback_recorder["rollback"] == ["B900"]  # 失败也回滚 ✓
