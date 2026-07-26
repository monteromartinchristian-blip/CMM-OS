from collections.abc import Iterator

import pytest

from kernel.llm.model_catalog import clear_model_catalog


@pytest.fixture(autouse=True)
def isolate_model_catalog() -> Iterator[None]:
    """Keep model catalog mutations isolated between tests."""

    clear_model_catalog()
    yield
    clear_model_catalog()
