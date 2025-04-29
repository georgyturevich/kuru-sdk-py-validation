# Structured Logging with structlog

This project uses `structlog` for structured, JSON-formatted logging, which replaces the previous ad-hoc use of `print()` statements.

## Features

- **JSON-formatted logs**: All logs are output as JSON, making them easily parseable by log aggregation tools
- **Structured data**: Logs include key-value pairs instead of just text messages
- **Automatic enrichment**: Each log entry automatically includes:
  - Timestamp in ISO format
  - Logger name (module name)
  - Log level
- **Integration with pytest**: Logging is configured to work seamlessly with pytest

## Usage

### Basic Logging

To log messages in your code:

```python
import structlog

# Get a logger for the current module
log = structlog.get_logger(__name__)

# Log at different levels with structured data
log.debug("Processing data", user_id=123, items_count=5)
log.info("User signed in", user_id=123, ip_address="192.168.1.1")
log.warning("Rate limit approaching", current=95, limit=100)
log.error("Database connection failed", error="Connection timeout", retries=3)
```

### Logging Exceptions

When catching exceptions, include them in structured logs:

```python
try:
    # Some code that might raise an exception
    result = process_data()
except Exception as e:
    log.error("Error processing data", 
              error=str(e),
              error_type=type(e).__name__)
    # Or with full traceback
    import sys
    import traceback
    exc_info = sys.exc_info()
    tb_string = ''.join(traceback.format_exception(*exc_info))
    log.error("Error with traceback", 
              error=str(e),
              traceback=tb_string)
```

### Best Practices

1. **Use key-value pairs**: Instead of formatting strings, use key-value pairs
   - Bad: `log.info(f"Processing item {item_id} for user {user_id}")`
   - Good: `log.info("Processing item", item_id=item_id, user_id=user_id)`

2. **Choose appropriate log levels**:
   - `debug`: Detailed information for debugging
   - `info`: Confirmation that things are working
   - `warning`: Indication that something unexpected happened
   - `error`: An error occurred but the application can continue
   - `critical`: A serious error that might prevent the program from continuing

3. **Include contextual information**: Add relevant data that would help debugging

## Configuration

The logging system is automatically configured in `lib/utils/logging_config.py`. The configuration:

1. Sets up structlog to use standard processors
2. Forwards logs to the Python standard logging library
3. Configures a standard logging handler with JSON rendering

You don't need to explicitly configure logging in your modules - just import and use the logger.

## pytest Integration

The pytest configuration in `pytest.ini` is set up to:

- Display logs in real-time during test runs (`log_cli = true`)
- Set console logging level to INFO (`log_cli_level = INFO`)
- Save detailed logs to a file (`log_file = test_run.log`)
- Use a simple format that preserves the JSON structure (`log_format = %(message)s`)

## Migrating from Print Statements

When replacing print statements, follow these guidelines:

1. Import structlog and get a logger: `log = structlog.get_logger(__name__)`
2. Replace `print()` with appropriate log level method
3. Convert printed variables to key-value pairs:
   - Before: `print(f"Processing item {item_id}")`
   - After: `log.info("Processing item", item_id=item_id)` 