"""M2 请求引擎单测：真实 HTTP（打本地假服务器），离线可跑"""
import pytest

from core.http_client import ApiResponse, HttpClient


def make_client(base_url, retry=0):
    return HttpClient(cfg={"base_url": base_url, "timeout": 5, "retry": retry,
                           "headers": {"X-Test": "1"}})


class TestBasic:
    def test_get_json(self, fake_base_url):
        client = make_client(fake_base_url)
        resp = client.get("/user", case_id="t1")
        assert resp.status == 200
        assert resp.json["data"]["id"] == 42
        assert resp.elapsed_ms >= 0

    def test_post_echo(self, fake_base_url):
        client = make_client(fake_base_url)
        resp = client.post("/echo", json={"name": "张三"})
        assert resp.json["echo"]["name"] == "张三"

    def test_urljoin(self, fake_base_url):
        client = make_client(fake_base_url + "/")
        assert client.get("/user").status == 200

    def test_404(self, fake_base_url):
        client = make_client(fake_base_url)
        assert client.get("/nope").status == 404

    def test_requires_env_or_cfg(self):
        with pytest.raises(ValueError, match="至少提供一个"):
            HttpClient()


class TestRetry:
    def test_get_retry_until_success(self, fake_base_url):
        """GET 幂等：前 2 次 500，第 3 次成功 → retry=2 应最终成功"""
        client = make_client(fake_base_url, retry=2)
        resp = client.get("/flaky")
        assert resp.status == 200
        assert resp.json["attempt"] == 3

    def test_post_never_retried(self, fake_base_url):
        """POST 非幂等：即使失败也不重放（写请求重放可能造成重复下单）"""
        client = make_client(fake_base_url, retry=3)
        resp = client.post("/flaky_post")
        assert resp.status == 500  # 只打了一次


class TestApiResponse:
    def test_invalid_json_raises(self):
        resp = ApiResponse(status=200, text="not json")
        with pytest.raises(ValueError, match="不是合法 JSON"):
            _ = resp.json
