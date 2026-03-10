# Render Free Web Service + Supabase Deployment

This bot runs on a Render web service, stores data in Supabase Postgres, and receives Telegram updates through a webhook.

## Why this setup exists

- Render free web services are cheaper than background workers.
- Render web services must bind an HTTP port on `0.0.0.0:$PORT`.
- Free web services spin down after 15 minutes without inbound traffic.
- Telegram polling causes `getUpdates` conflicts when another instance or stale process touches the same bot token.
- Webhooks remove the polling conflict by letting Telegram push updates to your Render URL.

## 1. Create Supabase Postgres

1. Create a Supabase project.
2. Open Project Settings -> Database.
3. Copy the server-side Postgres connection string.
4. Use the exact connection string Supabase provides.

## 2. Prepare Render

1. Push this repository to GitHub.
2. In Render, create a new Web Service.
3. Connect the repository.
4. Render can use the existing [render.yaml](render.yaml) file.

Current web service settings:

- Type: `web`
- Plan: `free`
- Build command: `pip install -r requirements.txt`
- Start command: `python bot.py`
- Health check path: `/healthz`
- Required env vars: `BOT_TOKEN`, `DATABASE_URL`, `WEBHOOK_BASE_URL`
- Delivery mode: `BOT_DELIVERY_MODE=webhook`
- Safety flag: `REQUIRE_DATABASE=true`

## 3. Set Environment Variables in Render

Add these variables in the Render dashboard:

- `BOT_TOKEN`: your Telegram bot token
- `DATABASE_URL`: your Supabase Postgres connection string
- `WEBHOOK_BASE_URL`: your public Render URL, for example `https://birthday-telegram-bot-zh50.onrender.com`
- `WEBHOOK_SECRET_TOKEN`: optional but recommended shared secret for Telegram webhook requests

`PORT` is provided by Render automatically. `REQUIRE_DATABASE=true` and `BOT_DELIVERY_MODE=webhook` are defined in [render.yaml](render.yaml), so the service starts in webhook mode on Render.

## 4. Deploy

1. Trigger the first deploy.
2. Open the Render logs.
3. Confirm startup logs show the HTTP server, Postgres backend, webhook registration, and scheduler startup.

Expected startup flow:

- `[store] Using Postgres backend.`
- `[main] Building Application...`
- `[main] Application started.`
- `[webhook] Registered webhook: https://your-service.onrender.com/telegram/webhook`
- `[http] Listening on 0.0.0.0:PORT.`
- `[main] Scheduler started.`
- `[main] Webhook bot is running...`

## 5. Verify the Web Endpoint

Open your Render URL and check one of these paths:

- `/`
- `/healthz`

Either endpoint should respond with `ok`.

## 6. Verify the Telegram Webhook

After deployment, send `/start` to the bot and check the Render logs.

Expected log behavior:

- Render receives a `POST` on `/telegram/webhook`
- The bot logs `[webhook] Accepted update ...`
- The command handler runs without any `getUpdates` conflict

This deployment no longer uses polling, so the Telegram conflict `terminated by other getUpdates request` should stop once the webhook deployment is live.

## 7. Optional Keepalive Cron for Free Tier

Use a free external cron service such as cron-job.org.

Recommended setup:

- Method: `GET`
- URL: `https://your-service-name.onrender.com/healthz`
- Interval: every 14 minutes

This keeps the free Render web service from idling out after 15 minutes of inactivity.

Note: webhook delivery fixes Telegram update conflicts, but it does not stop Render free-tier sleep. If the service sleeps, scheduled birthday jobs can still be delayed until the service wakes up again.

## 8. Verify the Database

The bot creates these tables automatically on first startup:

- `birthdays`
- `active_chats`

You can verify them from the Supabase SQL editor.

## 9. Smoke Test from Telegram

1. Start a private chat with the bot and run `/start`.
2. Run `/setbirthday 2000-01-01`.
3. Run `/mybirthday`.
4. Add the bot to a test group and run `/start` there.
5. Confirm no database errors appear in Render logs.

## 10. Restart Test

Redeploy or restart the Render service, then run `/mybirthday` again. If the birthday is still present, persistence is working correctly.

## Limitations

- This remains a hobby-grade deployment.
- If the keepalive cron stops, the service can sleep and scheduled birthday messages can be delayed.
- Free Render services can still restart unexpectedly.
- Do not rely on `birthdays.db` or `chat_ids.json` in production.
- `.env` is for local development only.
