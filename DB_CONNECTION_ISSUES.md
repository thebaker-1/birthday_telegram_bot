---
# Database Connection Issues and Solutions

## Problem 1: Persistent Connection Loss

**Symptom:**

- Errors like `psycopg.OperationalError: the connection is lost` or `server closed the connection unexpectedly`.
- Bot fails to respond to commands that require database access.

**Root Cause:**

- The bot holds a persistent connection to the database. If the connection is dropped (due to network, server restart, timeout, or resource limits), all subsequent queries fail.

**Solution:**

- Add retry logic to all database operations. If a `psycopg.OperationalError` is raised, reconnect and retry the operation once.
- Only retry on connection errors, not on all exceptions.

**Code Pattern:**

```python
for attempt in range(2):
    try:
        # ...db operation...
        break
    except OperationalError:
        if attempt == 1:
            raise
        self.reconnect()
    except Exception:
        raise
```

## Problem 2: DATABASE_URL Not Set

**Symptom:**

- Script fails with `TypeError: expected str, got NoneType` or similar.

**Solution:**

- Always check that `DATABASE_URL` is set before using it. Exit or raise an error if not set.

**Code Pattern:**

```python
if not DATABASE_URL:
    print("DATABASE_URL is not set.")
    exit(1)
```

## Problem 3: Multiple Bot Instances (Polling Conflict)

**Symptom:**

- `telegram.error.Conflict: terminated by other getUpdates request; make sure that only one bot instance is running`

**Solution:**

- Only run one instance of the bot per token. Stop all other running instances before starting a new one.

## Problem 4: VS Code Import Warnings

**Symptom:**

- `Import "requests" could not be resolved from source`

**Solution:**

- Ensure the correct Python interpreter is selected in VS Code.
- Install all dependencies in your virtual environment.

---
Refer to this file for common database and deployment issues and their solutions.