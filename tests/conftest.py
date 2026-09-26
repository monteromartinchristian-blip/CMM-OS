import os
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

#: Environment override honoured by ``cmm.events.storage.resolve_data_directory``.
#: Tests must never persist into a real per-user application data location, so the
#: whole suite is redirected to a session-scoped temporary directory.  Production
#: runtime composition is unaffected: it never runs under pytest.
DATA_DIRECTORY_ENV = "CMM_OS_DATA_DIR"


@pytest.fixture(scope="session", autouse=True)
def isolated_application_data_directory(tmp_path_factory):
    """Redirect application data storage away from the real user location."""

    directory = tmp_path_factory.mktemp("cmm-os-data")
    previous = os.environ.get(DATA_DIRECTORY_ENV)
    os.environ[DATA_DIRECTORY_ENV] = str(directory)
    try:
        yield directory
    finally:
        if previous is None:
            os.environ.pop(DATA_DIRECTORY_ENV, None)
        else:
            os.environ[DATA_DIRECTORY_ENV] = previous


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
