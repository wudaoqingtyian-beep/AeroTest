"""真实接口用例套件入口（M6/M7）

默认被 pytest.ini 的 `-m "not suite"` 排除；
执行真实套件：pytest -m suite -v（可加 --env dev 切换环境）
"""
import pytest

from core.runner import run_case

pytestmark = pytest.mark.suite


def test_api_case(yaml_case, client, ctx, data_provider):
    """通用执行器：每条 YAML 用例参数化为一个测试"""
    run_case(yaml_case, client, ctx, data_provider)
