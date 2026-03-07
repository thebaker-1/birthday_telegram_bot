# Render Free Web Service + Supabase Deployment

This bot runs on a Render web service, stores data in Supabase Postgres, and keeps the free instance awake with an external cron ping.

## Why this setup exists

- Render free web services are cheaper than background workers.
- Render web services must bind an HTTP port on `0.0.0.0:$PORT`.
- Free web services spin down after 15 minutes without inbound traffic.
- This project still uses Telegram polling, so an external cron ping is needed to reduce missed scheduled jobs.

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
- Required env vars: `BOT_TOKEN`, `DATABASE_URL`
- Safety flag: `REQUIRE_DATABASE=true`

## 3. Set Environment Variables in Render

Add these variables in the Render dashboard:

- `BOT_TOKEN`: your Telegram bot token
- `DATABASE_URL`: your Supabase Postgres connection string

`PORT` is provided by Render automatically. `REQUIRE_DATABASE=true` is defined in [render.yaml](render.yaml), so the service fails fast if `DATABASE_URL` is missing.

## 4. Deploy

1. Trigger the first deploy.
2. Open the Render logs.
3. Confirm startup logs show the health server, Postgres backend, and Telegram bot startup.

Expected startup flow:

- `[store] Using Postgres backend.`
- `[health] Listening on 0.0.0.0:PORT.`
- `[main] Building Application...`
- `[main] Application built.`
- `[main] Scheduler started.`

## 5. Verify the Web Endpoint

Open your Render URL and check one of these paths:

- `/`
- `/healthz`

Either endpoint should respond with `ok`.

## 6. Set Up the Keepalive Cron

Use a free external cron service such as cron-job.org.

Recommended setup:

- Method: `GET`
- URL: `https://your-service-name.onrender.com/healthz`
- Interval: every 14 minutes

This keeps the free Render web service from idling out after 15 minutes of inactivity.

## 7. Verify the Database

The bot creates these tables automatically on first startup:

- `birthdays`
- `active_chats`

You can verify them from the Supabase SQL editor.

## 8. Smoke Test from Telegram

1. Start a private chat with the bot and run `/start`.
2. Run `/setbirthday 2000-01-01`.
3. Run `/mybirthday`.
4. Add the bot to a test group and run `/start` there.
5. Confirm no database errors appear in Render logs.

## 9. Restart Test

Redeploy or restart the Render service, then run `/mybirthday` again. If the birthday is still present, persistence is working correctly.

## Limitations

- This remains a hobby-grade deployment.
- If the keepalive cron stops, the service can sleep and scheduled birthday messages can be delayed.
- Free Render services can still restart unexpectedly.
- Do not rely on `birthdays.db` or `chat_ids.json` in production.
- `.env` is for local development only.
