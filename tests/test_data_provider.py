"""M5 造数联动单测：mock 服务 + 降级模式"""
import json

import pytest
import requests

from core.context import Context
from core.data_provider import DataProvider


class FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self._payload


def make_provider(tmp_path, health=True):
    dp = DataProvider(base_url="http://fake", fallback_dir=str(tmp_path / "fb"))
    if health:
        requests.get = lambda *a, **kw: FakeResp(200, {"status": "ok"})
    else:
        def _boom(*a, **kw):
            raise requests.ConnectionError("down")
        requests.get = _boom
    return dp


class TestSetup:
    def test_service_mode_returns_batch_and_fills_ctx(self, tmp_path, monkeypatch):
        posted = {}

        def fake_post(url, json=None, timeout=None):
            posted["url"], posted["json"] = url, json
            return FakeResp(200, {"batch_id": "B001", "rows": [{"id": 1}]})

        monkeypatch.setattr(requests, "post", fake_post)
        dp = make_provider(tmp_path, health=True)
        ctx = Context()
        batch = dp.setup([{"template": "user", "count": 5, "var": "users"}], ctx)
        assert batch == "B001"
        assert ctx.get("users") == [{"id": 1}]
        assert posted["json"] == {"template": "user", "count": 5, "boundary": False}

    def test_shorthand_declaration(self, tmp_path, monkeypatch):
        monkeypatch.setattr(requests, "post",
                            lambda *a, **kw: FakeResp(200, {"batch_id": "B2",
                                                            "rows": []}))
        ctx = Context()
        dp = make_provider(tmp_path, health=True)
        assert dp.setup(["order"], ctx) == "B2"
        assert ctx.get("order") == []

    def test_fallback_mode_when_service_down(self, tmp_path, monkeypatch):
        fb = tmp_path / "fb"
        fb.mkdir()
        (fb / "user.json").write_text(json.dumps([{"id": 9}, {"id": 10}]),
                                      encoding="utf-8")
        dp = make_provider(tmp_path, health=False)
        ctx = Context()
        batch = dp.setup(["user"], ctx)
        assert batch is None            # 降级模式无批次号
        assert ctx.get("user") == [{"id": 9}, {"id": 10}]

    def test_fallback_missing_file_returns_empty(self, tmp_path):
        dp = make_provider(tmp_path, health=False)
        ctx = Context()
        dp.setup(["ghost"], ctx)
        assert ctx.get("ghost") == []


class TestTeardown:
    def test_rollback_called_with_batch(self, tmp_path, monkeypatch):
        rolled = {}

        def fake_post(url, json=None, timeout=None):
            rolled["batch_id"] = json["batch_id"]
            return FakeResp(200, {"deleted_rows": 5})

        monkeypatch.setattr(requests, "post", fake_post)
        dp = make_provider(tmp_path, health=True)
        result = dp.teardown("B001")
        assert rolled["batch_id"] == "B001"
        assert result == {"deleted_rows": 5}

    def test_none_batch_skipped(self, tmp_path):
        dp = make_provider(tmp_path, health=False)
        assert dp.teardown(None) == {"skipped": True}
