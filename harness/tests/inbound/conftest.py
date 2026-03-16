from __future__ import annotations

import asyncio
import inspect

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "asyncio: run async test functions with the local inbound event loop hook")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    if pyfuncitem.get_closest_marker("asyncio") is None:
        return None
    test_function = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_function):
        return None
    signature = inspect.signature(test_function)
    kwargs = {
        name: value
        for name, value in pyfuncitem.funcargs.items()
        if name in signature.parameters
    }
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(test_function(**kwargs))
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    return True
