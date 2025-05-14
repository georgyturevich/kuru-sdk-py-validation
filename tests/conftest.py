import pytest
from dotenv import load_dotenv
from pydantic import ValidationError

from lib.utils import configure_logging
from tests.settings import Settings

# Configure structlog at the very beginning
configure_logging()


@pytest.fixture(scope="session", autouse=True)
def settings():
    load_dotenv()

    try:
        v = Settings()
        return v
    except ValidationError as e:
        pytest.exit(f"Configuration error: {e}", returncode=1)
        return None
