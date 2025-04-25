import pytest
from dotenv import load_dotenv
from pydantic import ValidationError
from tests.settings import Settings

@pytest.fixture(scope="session", autouse=True)
def settings():
    load_dotenv()

    try:
        v = Settings()
        return v
    except ValidationError as e:
        pytest.exit(f"Configuration error: {e}", returncode=1)
        return None
