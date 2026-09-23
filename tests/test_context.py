"""M1 变量池单测 —— 按纪律亲手编写，逐条对应设计结论"""
import pytest

from core.context import Context, ExtractError


class TestRender:
    def test_full_placeholder_keeps_native_type(self):
        """设计结论1：整串单一占位符保留原生类型（int 不应变 '18'）"""
        ctx = Context()
        ctx.set("age", 18)
        assert ctx.render("${age}") == 18
        assert isinstance(ctx.render("${age}"), int)

    def test_mixed_returns_string(self):
        """设计结论1：混排统一转字符串拼接"""
        ctx = Context()
        ctx.set("name", "张三")
        ctx.set("age", 18)
        assert ctx.render("auto_${name}_${age}_01") == "auto_张三_18_01"

    def test_undefined_raises_keyerror(self):
        ctx = Context()
        with pytest.raises(KeyError, match="变量未定义"):
            ctx.render("${missing}")

    def test_multi_occurrence(self):
        ctx = Context()
        ctx.set("id", 7)
        assert ctx.render("${id}-${id}") == "7-7"


class TestRenderDeep:
    def test_nested_dict_list(self):
        """设计结论2：dict/list 递归，非字符串原样返回"""
        ctx = Context()
        ctx.set("x", "hello")
        ctx.set("y", 42)
        tpl = {"a": "${x}", "b": ["${y}", 1, None], "c": {"d": "${x}"}, "e": 3.14}
        result = ctx.render_deep(tpl)
        assert result == {"a": "hello", "b": [42, 1, None], "c": {"d": "hello"}, "e": 3.14}
        # 原模板不被污染
        assert tpl["a"] == "${x}"


class TestExtract:
    def test_extract_and_store(self):
        ctx = Context()
        resp = {"code": 0, "data": {"token": "abc", "list": [{"id": 1}]}}
        assert ctx.extract_from(resp, "$.data.token", "token") == "abc"
        assert ctx.get("token") == "abc"
        # 数组下标
        assert ctx.extract_from(resp, "$.data.list.0.id", "first_id") == 1

    def test_broken_path_raises(self):
        """设计结论3：路径断开必须报错，不静默"""
        ctx = Context()
        with pytest.raises(ExtractError, match="提取失败"):
            ctx.extract_from({"a": 1}, "$.a.b.c", "v")

    def test_none_result_raises(self):
        ctx = Context()
        with pytest.raises(ExtractError, match="None"):
            ctx.extract_from({"a": None}, "$.a", "v")
