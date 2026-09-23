"""M3 数据驱动单测：加载/校验/参数化展开"""
import textwrap

import pytest

from core.case_loader import load_case, load_case_with_params

VALID = textwrap.dedent("""
    name: 查询用户
    request:
      method: GET
      path: /user
      params:
        id: "${user_id}"
    assertions:
      - type: status_eq
        expected: 200
      - type: json_eq
        path: $.data.id
        expected: 42
    extract:
      token: $.data.token
    params:
      - user_id: 1
      - user_id: 2
""")


def write(tmp_path, content, name="case.yaml"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestLoad:
    def test_valid_case(self, tmp_path):
        case = load_case(write(tmp_path, VALID))
        assert case.name == "查询用户"
        assert case.request["method"] == "GET"
        assert len(case.assertions) == 2

    def test_missing_method(self, tmp_path):
        p = write(tmp_path, "request:\n  path: /user\n")
        with pytest.raises(ValueError, match="method 和 path"):
            load_case(p)

    def test_unknown_asserter(self, tmp_path):
        bad = VALID.replace("status_eq", "status_equals")
        with pytest.raises(ValueError, match="未知断言类型"):
            load_case(write(tmp_path, bad))

    def test_unknown_placeholder_rejected_at_load(self, tmp_path):
        """占位符无来源 → 加载期报错，不带病运行"""
        bad = VALID.replace("${user_id}", "${who_am_i}")
        with pytest.raises(ValueError, match="无数据来源"):
            load_case(write(tmp_path, bad))

    def test_setup_shorthand_provides_var(self, tmp_path):
        ok = VALID.replace("${user_id}", "${user}")
        ok = ok.replace("extract:", "setup:\n  - template: user\nextract:")
        case = load_case(write(tmp_path, ok))
        assert case.setup[0]["template"] == "user"


class TestExpandParams:
    def test_expand_two_groups(self, tmp_path):
        cases = load_case_with_params(write(tmp_path, VALID))
        assert len(cases) == 2
        assert cases[0].name == "查询用户[0]"
        assert cases[1].param == {"user_id": 2}

    def test_no_params_single(self, tmp_path):
        simple = VALID.split("params:")[0]
        cases = load_case_with_params(write(tmp_path, simple))
        assert len(cases) == 1 and cases[0].param is None
