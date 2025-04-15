# Kuru SDK Integration Tests

## Setup

### For local development:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e /path/to/kuru-sdk-py  # Point to your local SDK copy
```

For regular installation:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-kuru-sdk.txt
```

Running Tests
```bash
pytest tests/
```