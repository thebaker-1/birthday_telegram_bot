# Render + Supabase Deployment

This bot is designed to run as a Render worker and persist data in Supabase Postgres.

## 1. Create Supabase Postgres

1. Create a Supabase project.
2. Open Project Settings -> Database.
3. Copy the server-side Postgres connection string.
4. Use the exact connection string Supabase provides. Do not rewrite it unless Supabase explicitly instructs you to.

## 2. Prepare Render

1. Push this repository to GitHub.
2. In Render, create a new Background Worker.
3. Connect the repository.
4. Render can use the existing [render.yaml](render.yaml) file.

Current worker settings:

- Build command: `pip install -r requirements.txt`
- Start command: `python bot.py`
- Required env vars: `BOT_TOKEN`, `DATABASE_URL`
- Safety flag: `REQUIRE_DATABASE=true`

## 3. Set Environment Variables in Render

Add these variables in the Render dashboard:

- `BOT_TOKEN`: your Telegram bot token
- `DATABASE_URL`: your Supabase Postgres connection string

`REQUIRE_DATABASE=true` is already defined in [render.yaml](render.yaml), so the worker will fail fast if `DATABASE_URL` is missing.

## 4. Deploy

1. Trigger the first deploy.
2. Open the Render logs.
3. Confirm startup logs show the app booted and the store selected Postgres.

Expected startup flow:

- `[store] Using Postgres backend.`
- `[main] Building Application...`
- `[main] Application built.`
- `[main] Scheduler started.`

## 5. Verify the Database

The bot creates these tables automatically on first startup:

- `birthdays`
- `active_chats`

You can verify them from the Supabase SQL editor.

## 6. Smoke Test from Telegram

1. Start a private chat with the bot and run `/start`.
2. Run `/setbirthday 2000-01-01`.
3. Run `/mybirthday`.
4. Add the bot to a test group and run `/start` there.
5. Confirm the worker keeps running and no database errors appear in Render logs.

## 7. Restart Test

Redeploy or restart the Render worker, then run `/mybirthday` again. If the birthday is still present, persistence is working correctly.

## Notes

- Do not rely on `birthdays.db` or `chat_ids.json` in production. Render storage is ephemeral.
- `.env` is for local development only.
- The current bot uses Telegram polling, so it should stay a worker, not a web service.
