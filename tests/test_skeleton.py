import pytest


def test_skeleton():
    """M0 骨架验证：空框架 pytest 可运行。随模块推进替换为真实单测。"""
    import core.context  # noqa: F401
    import core.http_client  # noqa: F401
    import core.case_loader  # noqa: F401
    import core.assertions  # noqa: F401
    import core.data_provider  # noqa: F401
