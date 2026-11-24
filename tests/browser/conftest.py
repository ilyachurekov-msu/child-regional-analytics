import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "args": ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    }
