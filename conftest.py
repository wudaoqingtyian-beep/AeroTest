"""pytest 集成层（M6/M7）

- --env / --config-dir 命令行选项
- pytest_generate_tests：收集 testcases/**/*.yaml 参数化为可执行用例
- fixtures：client（session 级连接复用）、ctx（function 级隔离，
  保证用例间变量不串扰——并发安全的基础）
- 真实用例套件标记为 suite：默认跑框架自身单测，`pytest -m suite` 跑套件
"""
import pathlib

import pytest

from core.case_loader import load_case_with_params
from core.data_provider import DataProvider
from core.http_client import HttpClient
from core.runner import run_case


def pytest_addoption(parser):
    parser.addoption("--env", default="test", help="环境名（config/envs/下）")
    parser.addoption("--config-dir", default="config")


def pytest_configure(config):
    config.addinivalue_line("markers", "suite: 真实接口用例套件")


def pytest_generate_tests(metafunc):
    if "yaml_case" not in metafunc.fixturenames:
        return
    root = pathlib.Path(metafunc.config.rootdir)
    cases, ids = [], []
    case_dir = root / "testcases"
    if case_dir.exists():
        for path in sorted(case_dir.rglob("*.yaml")):
            try:
                cases.extend(load_case_with_params(str(path)))
            except Exception as e:  # 坏用例也要可见，不能静默吞掉
                cases.append(("__load_error__", f"用例加载失败 {path.name}: {e}"))
            ids.append(path.stem)
    metafunc.parametrize("yaml_case", cases, ids=ids)


@pytest.fixture(scope="session")
def env_config(request):
    from core.config import load_env_config
    return load_env_config(
        request.config.getoption("--env"),
        request.config.getoption("--config-dir"),
    )


@pytest.fixture(scope="session")
def client(request, env_config):
    return HttpClient(env=request.config.getoption("--env"),
                      config_dir=request.config.getoption("--config-dir"))


@pytest.fixture(scope="session")
def data_provider(request, env_config):
    factory = (env_config or {}).get("data_factory") or {}
    return DataProvider(base_url=factory.get("base_url", "http://127.0.0.1:8000"),
                        fallback_dir=factory.get("fallback_dir",
                                                 "testcases/fallback_data"))


@pytest.fixture()
def ctx():
    """function 级隔离：每条用例独立变量池"""
    from core.context import Context
    return Context()


@pytest.fixture()
def yaml_case(request):
    """参数化产物：正常为 Case 对象；加载失败的用例为 (标记, 错误信息) 元组，
    在运行期转为失败（不能在 collection 期 abort 整个套件）。"""
    if isinstance(request.param, tuple) and request.param[0] == "__load_error__":
        pytest.fail(request.param[1])
    return request.param
