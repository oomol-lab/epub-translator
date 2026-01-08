import sys

import pytest

try:
    # 使用 pytest 来运行测试，支持 unittest 和 pytest 风格
    exit_code = pytest.main(
        [
            "tests/",
            "-v",
            "--tb=short",
        ]
    )
    sys.exit(exit_code)

# pylint: disable=broad-exception-caught
except Exception as e:
    print(e)
    sys.exit(1)
