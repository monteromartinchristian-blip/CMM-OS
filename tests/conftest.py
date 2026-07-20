import shutil
from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_python_file(tmp_path):

    def factory(filename):

        source = FIXTURES / filename

        destination = tmp_path / filename

        shutil.copy(
            source,
            destination,
        )

        return destination

    return factory