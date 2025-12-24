import shutil
from pathlib import Path

import pytest


def create_temp_dir_fixture(subdir_name: str):
    @pytest.fixture
    def temp_dir_fixture():
        temp_path = Path("tests", "temp") / subdir_name
        if temp_path.exists():
            shutil.rmtree(temp_path)
        temp_path.mkdir(parents=True, exist_ok=True)

        yield temp_path

    return temp_dir_fixture
