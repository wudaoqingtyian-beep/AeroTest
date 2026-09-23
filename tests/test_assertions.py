"""M4 断言引擎单测：不依赖网络，构造 ApiResponse 直接验证"""
import pytest

from core.assertions import ASSERTERS, run
from core.http_client import ApiResponse


def make_resp(status=200, body='{"code": 0, "data": {"id": 42, "name": "tester"}}',
              elapsed_ms=100):
    return ApiResponse(status=status, text=body, elapsed_ms=elapsed_ms)


class TestRegistered:
    def test_registry_has_all_builtins(self):
        assert {"status_eq", "json_eq", "json_contains", "json_regex",
                "elapsed_lt", "db_eq"} <= set(ASSERTERS)

    def test_status_ok(self):
        run(make_resp(), [{"type": "status_eq", "expected": 200}])

    def test_json_eq(self):
        run(make_resp(), [{"type": "json_eq", "path": "$.data.id", "expected": 42}])

    def test_json_eq_missing_path(self):
        with pytest.raises(AssertionError, match="路径不存在"):
            run(make_resp(), [{"type": "json_eq", "path": "$.nope", "expected": 1}])

    def test_json_contains(self):
        run(make_resp(), [{"type": "json_contains", "path": "$.data.name",
                           "expected": "test"}])

    def test_json_regex(self):
        run(make_resp(), [{"type": "json_regex", "path": "$.data.name",
                           "expected": r"t\w+er"}])

    def test_elapsed_lt_fail_message(self):
        with pytest.raises(AssertionError, match=r"期望 '<500ms' / 实际"):
            run(make_resp(elapsed_ms=900),
                [{"type": "elapsed_lt", "expected": 500}])

    def test_unknown_type_raises_valueerror(self):
        with pytest.raises(ValueError, match="未知断言类型"):
            run(make_resp(), [{"type": "wat", "expected": 1}])

    def test_fail_message_contains_expected_and_actual(self):
        with pytest.raises(AssertionError) as ei:
            run(make_resp(), [{"type": "json_eq", "path": "$.data.id", "expected": 1}])
        assert "期望 1" in str(ei.value) and "实际 42" in str(ei.value)


class TestExtensibility:
    def test_register_new_asserter_without_engine_change(self):
        """开闭原则验证：注册即用，不改引擎代码"""
        from core.assertions import register

        @register("header_eq")
        def _header_eq(response, spec):
            if response.headers.get(spec["path"]) != spec["expected"]:
                raise AssertionError("header mismatch")

        assert "header_eq" in ASSERTERS
        resp = make_resp()
        resp.headers["X-Env"] = "test"
        run(resp, [{"type": "header_eq", "path": "X-Env", "expected": "test"}])
        del ASSERTERS["header_eq"]  # 清理，避免影响其他用例
