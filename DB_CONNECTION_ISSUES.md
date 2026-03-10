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

- Only run one instance of the bot per token when using polling. Stop all other running instances before starting a new one.
- On Render, prefer Telegram webhooks instead of polling. Webhooks remove the `getUpdates` conflict entirely because Telegram pushes updates to your service URL.

**Render Fix:**

- Set `BOT_DELIVERY_MODE=webhook`
- Set `WEBHOOK_BASE_URL=https://your-service.onrender.com`
- Redeploy so the bot registers `https://your-service.onrender.com/telegram/webhook`

## Problem 4: VS Code Import Warnings

**Symptom:**

- `Import "requests" could not be resolved from source`

**Solution:**

- Ensure the correct Python interpreter is selected in VS Code.
- Install all dependencies in your virtual environment.

## Problem 5: Free Instance Spin Down (Cold Start Delay)

**Symptom:**

- The first request after a period of inactivity takes 30–60 seconds (or more) to respond.
- Subsequent requests are fast until another period of inactivity.

**Root Cause:**

- Free hosting providers (like Render, Heroku, etc.) put your server to sleep after inactivity to save resources. When a new request comes in, the server must "wake up" (cold start), causing a long delay.

**Solution:**

- This is expected behavior for free plans. To avoid cold start delays, upgrade to a paid plan or use a provider that does not spin down idle instances.
- This is not a bug in your code or deployment.

---
Refer to this file for common database and deployment issues and their solutions.
