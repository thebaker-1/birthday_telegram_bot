import asyncio, json, os, threading, traceback
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CallbackContext, ChatMemberHandler, CommandHandler, ContextTypes, MessageHandler, filters
from bot_services import BirthdayService, HELP_TEXT
from bot_store import BotStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
TOKEN = os.getenv("BOT_TOKEN", "")
BOT_DELIVERY_MODE = os.getenv("BOT_DELIVERY_MODE", "").strip().lower()
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").strip().rstrip("/")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/telegram/webhook").strip() or "/telegram/webhook"
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "").strip()
service = BirthdayService(BASE_DIR)
store = BotStore(BASE_DIR)


def log(message: str):
    print(message, flush=True)


def normalize_webhook_path(path: str):
    return path if path.startswith("/") else f"/{path}"


WEBHOOK_PATH = normalize_webhook_path(WEBHOOK_PATH)


class HealthCheckHandler(BaseHTTPRequestHandler):
    application: ClassVar[Application | None] = None
    update_loop: ClassVar[asyncio.AbstractEventLoop | None] = None

    def do_GET(self):
        if self.path not in {"/", "/healthz"}:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found\n")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "3")
        self.end_headers()
        self.wfile.write(b"ok\n")

    def do_POST(self):
        if self.path != WEBHOOK_PATH:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found\n")
            return

        if WEBHOOK_SECRET_TOKEN:
            received_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if received_secret != WEBHOOK_SECRET_TOKEN:
                log("[webhook] Rejected request with invalid secret token.")
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"forbidden\n")
                return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            if self.application is None or self.update_loop is None:
                raise RuntimeError("Webhook server is not initialized.")
            payload = json.loads(raw_body.decode("utf-8"))
            update = Update.de_json(payload, self.application.bot)
            future = asyncio.run_coroutine_threadsafe(self.application.update_queue.put(update), self.update_loop)
            future.result(timeout=10)
            update_id = payload.get("update_id", "unknown")
            log(f"[webhook] Accepted update {update_id}.")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok\n")
        except Exception:
            log("[webhook] Failed to process incoming update:")
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"error\n")

    def log_message(self, format, *args):
        return


def start_http_server(application: Application, update_loop: asyncio.AbstractEventLoop):
    port_text = os.getenv("PORT", "").strip()
    if not port_text:
        print("[health] PORT is not set. Skipping HTTP health server.")
        return None

    try:
        port = int(port_text)
    except ValueError as error:
        raise RuntimeError(f"Invalid PORT value: {port_text}") from error

    HealthCheckHandler.application = application
    HealthCheckHandler.update_loop = update_loop
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, name="health-server", daemon=True)
    thread.start()
    log(f"[http] Listening on 0.0.0.0:{port}.")
    log(f"[http] Health endpoint ready at /healthz.")
    log(f"[http] Telegram webhook endpoint ready at {WEBHOOK_PATH}.")
    return server


def should_use_webhooks():
    if BOT_DELIVERY_MODE == "webhook":
        return True
    if BOT_DELIVERY_MODE == "polling":
        return False
    return bool(WEBHOOK_BASE_URL)

def chat_id_of(update: Update):
    return update.effective_chat.id if update.effective_chat else 0

def next_birthday(birthday: str, today: datetime):
    date = datetime.strptime(birthday, "%Y-%m-%d").replace(year=today.year)
    return date if date >= today else date.replace(year=today.year + 1)

def render_birthdays(rows, today: datetime):
    rows = sorted(rows, key=lambda row: next_birthday(row[1], today))
    return "\n".join(
        f"{service.format_birthday_name(display_name, username)} - {birthday}"
        for username, birthday, display_name in rows
    )

async def chat_name(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try: return (await context.bot.get_chat(chat_id)).title or str(chat_id)
    except Exception: return str(chat_id)

async def is_group_admin(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int):
    try: return (await context.bot.get_chat_member(chat_id, user_id)).status in {"administrator", "creator"}
    except Exception: return False

async def admin_groups(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    groups = []
    for chat_id in sorted(store.active_chat_ids):
        if await is_group_admin(context, user_id, chat_id): groups.append(chat_id)
    return groups

async def pick_group(context: ContextTypes.DEFAULT_TYPE, user_id: int, selector: str):
    groups = await admin_groups(context, user_id)
    if selector.isdigit() and 1 <= int(selector) <= len(groups): return groups[int(selector) - 1]
    return 0

async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    user = update.effective_user
    if not user:
        await reply(update, "No user info available.")
        return False
    if not await is_group_admin(context, user.id, chat_id if chat_id is not None else chat_id_of(update)):
        await reply(update, "Admin only command.")
        return False
    return True

async def reply(update: Update, text: str):
    if update.message: await update.message.reply_text(text)
    elif update.effective_chat: await update.effective_chat.send_message(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_chat:
            store.track_chat_id(update.effective_chat.id, "start")
        await celebrate(context.application)
        await reply(update, "🎂 Birthday Bot is active!\nUse /help to see commands.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        await reply(update, f"❌ Error in /start: {e}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, HELP_TEXT)

async def setbirthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user, args = update.effective_user, context.args or []
        if not user: return await reply(update, "No user info available.")
        if not args: return await reply(update, "Usage: /setbirthday YYYY-MM-DD")
        birthday = args[0]
        try:
            datetime.strptime(birthday, "%Y-%m-%d")
        except ValueError:
            return await reply(update, "Usage: /setbirthday YYYY-MM-DD")
        username = user.username or ""
        store.save_birthday(chat_id_of(update), user.id, username, birthday, user.full_name or username)
        await reply(update, "✅ Birthday saved!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        await reply(update, f"❌ Error in /setbirthday: {e}")

async def mybirthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if not user:
            return await reply(update, "No user info available.")
        row = store.get_birthday_for_user(chat_id_of(update), user.id)
        await reply(update, f"🎂 Your birthday: {row[0]}" if row else "No birthday saved.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        await reply(update, f"❌ Error in /mybirthday: {e}")

async def removebirthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if not user:
            return await reply(update, "No user info available.")
        store.delete_birthday_for_user(chat_id_of(update), user.id)
        await reply(update, "Birthday removed.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        await reply(update, f"❌ Error in /removebirthday: {e}")

async def birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        today = datetime.now().strftime("%m-%d")
        people = [service.format_birthday_name(display_name, username) for username, birthday, display_name in store.get_all_birthdays(chat_id_of(update)) if service.is_birthday_today(birthday, today)]
        await reply(update, "🎉 Today's birthdays:\n" + "\n".join(people) if people else "No birthdays today.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        await reply(update, f"❌ Error in /birthdays: {e}")

async def listbirthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user, args, current_chat = update.effective_user, context.args or [], update.effective_chat
        if not user:
            return await reply(update, "No user info available.")
        chat_id = chat_id_of(update) if current_chat and current_chat.type != "private" else await pick_group(context, user.id, args[0] if args else "")
        if not chat_id:
            return await reply(update, "Usage: /listbirthdays GROUP_NO in private chat, or run it inside the group.")
        if not await require_admin(update, context, chat_id):
            return
        rows = store.get_all_birthdays(chat_id)
        if not rows:
            return await reply(update, "No birthdays saved in this group.")
        await reply(update, f"🎂 Birthdays in {await chat_name(context, chat_id)}:\n" + render_birthdays(rows, datetime.now()))
    except Exception as e:
        import traceback
        traceback.print_exc()
        await reply(update, f"❌ Error in /listbirthdays: {e}")

async def addbirthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = chat_id_of(update)
    args = context.args or []
    if not await require_admin(update, context): return
    if len(args) < 2: return await reply(update, "Usage: /addbirthday @user YYYY-MM-DD [Full Name]")
    username, birthday = args[0].replace("@", ""), args[1]
    display_name = " ".join(args[2:]).strip() or username
    store.save_birthday(chat_id, 0, username, birthday, display_name)
    await reply(update, "Birthday added.")
    today = datetime.now().strftime("%Y-%m-%d")
    if service.is_birthday_today(birthday, today[5:]) and await service.announce_birthday(context.application.bot, [chat_id], display_name, username):
        service.mark_sent_today(today, f"{chat_id}:{username}")

async def mygroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return await reply(update, "No user info available.")
    groups = await admin_groups(context, user.id)
    if not groups: return await reply(update, "No manageable groups found.")
    lines = [f"{index}. {await chat_name(context, chat_id)}" for index, chat_id in enumerate(groups, start=1)]
    await reply(update, "🗂️ Your groups:\n" + "\n".join(lines))

async def addbirthdayto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, args = update.effective_user, context.args or []
    if not user: return await reply(update, "No user info available.")
    if len(args) < 3: return await reply(update, "Usage: /addbirthdayto GROUP_NO @user YYYY-MM-DD [Full Name]")
    chat_id = await pick_group(context, user.id, args[0])
    if not chat_id: return await reply(update, "Unknown group number. Use /mygroups first.")
    if not await require_admin(update, context, chat_id): return
    username, birthday = args[1].replace("@", ""), args[2]
    try: datetime.strptime(birthday, "%Y-%m-%d")
    except ValueError: return await reply(update, "Usage: /addbirthdayto GROUP_NO @user YYYY-MM-DD [Full Name]")
    display_name = " ".join(args[3:]).strip() or username
    store.save_birthday(chat_id, 0, username, birthday, display_name)
    await reply(update, f"Birthday added to {await chat_name(context, chat_id)}.")
    today = datetime.now().strftime("%Y-%m-%d")
    if service.is_birthday_today(birthday, today[5:]) and await service.announce_birthday(context.application.bot, [chat_id], display_name, username):
        service.mark_sent_today(today, f"{chat_id}:{username}")

async def removeuserbirthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not await require_admin(update, context): return
    if not args: return await reply(update, "Usage: /removeuserbirthday @user")
    removed = store.delete_birthday_for_username(chat_id_of(update), args[0].replace("@", ""))
    await reply(update, "Birthday removed." if removed else "No birthday found for that user in this group.")

async def removebirthdayfrom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, args = update.effective_user, context.args or []
    if not user: return await reply(update, "No user info available.")
    if len(args) < 2: return await reply(update, "Usage: /removebirthdayfrom GROUP_NO @user")
    chat_id = await pick_group(context, user.id, args[0])
    if not chat_id: return await reply(update, "Unknown group number. Use /mygroups first.")
    if not await require_admin(update, context, chat_id): return
    removed = store.delete_birthday_for_username(chat_id, args[1].replace("@", ""))
    await reply(update, f"Birthday removed from {await chat_name(context, chat_id)}." if removed else "No birthday found for that user in the selected group.")

async def listallbirthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return await reply(update, "No user info available.")
    groups = await admin_groups(context, user.id)
    if not groups: return await reply(update, "No manageable groups found.")
    today, sections = datetime.now(), []
    for chat_id in groups:
        rows = store.get_all_birthdays(chat_id)
        if rows: sections.append(f"{await chat_name(context, chat_id)}:\n{render_birthdays(rows, today)}")
    await reply(update, "\n\n".join(sections) if sections else "No birthdays saved in your groups.")

async def celebrate(app: Application):
    today = datetime.now().strftime("%Y-%m-%d")
    print("Active chat IDs:", store.active_chat_ids)
    print("Checking birthdays for today:", today)
    print("sent_birthday_notification:", service.sent_notifications)
    service.ensure_day_tracking(today)
    sent_any = False
    for chat_id in store.active_chat_ids:
        for username, birthday, display_name in store.get_all_birthdays(chat_id):
            print(f"Checking chat {chat_id} user {username} with birthday {birthday}")
            if not service.is_birthday_today(birthday, today[5:]): continue
            if service.was_sent_today(today, f"{chat_id}:{username}"):
                print(f"Already sent notification for {username} in {chat_id} today.")
                continue
            print(f"Birthday match for {username} in {chat_id}!")
            if await service.announce_birthday(app.bot, [chat_id], display_name, username):
                service.mark_sent_today(today, f"{chat_id}:{username}")
                sent_any = True
            else: print(f"No birthday announcement was delivered for {username} in {chat_id}.")
    print("Birthday notification(s) sent for today." if sent_any else "No birthdays to notify today.")

async def weekly(app: Application):
    today, week = datetime.now(), datetime.now() + timedelta(days=7)
    for chat_id in store.active_chat_ids:
        upcoming = []
        for username, birthday, display_name in store.get_all_birthdays(chat_id):
            this_year = datetime.strptime(birthday, "%Y-%m-%d").replace(year=today.year)
            if today <= this_year <= week: upcoming.append(service.format_birthday_name(display_name, username))
        if upcoming:
            await app.bot.send_message(chat_id, "📅 Upcoming birthdays this week:\n" + "".join(f"🎂 {person}\n" for person in upcoming))

async def track_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat: store.track_chat_id(update.effective_chat.id, "message")

async def track_group_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.my_chat_member.chat if update.my_chat_member else None
    status = update.my_chat_member.new_chat_member.status if update.my_chat_member else None
    if chat and chat.type in ["group", "supergroup"] and status in ["administrator", "member"]: store.track_chat_id(chat.id, "my_chat_member")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log("[error] Unhandled exception while processing update.")
    if isinstance(update, Update):
        log(f"[error] Update id: {update.update_id}")
    if context.error is not None:
        traceback.print_exception(type(context.error), context.error, context.error.__traceback__)

def build_application():
    app = Application.builder().token(TOKEN).build()
    for command, handler in (("start", start), ("help", help_cmd), ("setbirthday", setbirthday), ("mybirthday", mybirthday), ("removebirthday", removebirthday), ("birthdays", birthdays), ("listbirthdays", listbirthdays), ("addbirthday", addbirthday), ("mygroups", mygroups), ("addbirthdayto", addbirthdayto), ("listallbirthdays", listallbirthdays), ("removeuserbirthday", removeuserbirthday), ("removebirthdayfrom", removebirthdayfrom)):
        app.add_handler(CommandHandler(command, handler))
    app.add_handler(MessageHandler(filters.ALL, track_chat), group=1)
    app.add_handler(ChatMemberHandler(track_group_add, ChatMemberHandler.MY_CHAT_MEMBER), group=0)
    app.add_error_handler(error_handler)
    return app

def start_scheduler(app: Application, update_loop: asyncio.AbstractEventLoop | None = None):
    scheduler = BackgroundScheduler()

    def run_async_job(name: str, coro):
        try:
            log(f"[scheduler] Running job: {name}")
            if update_loop is None:
                asyncio.run(coro)
            else:
                future = asyncio.run_coroutine_threadsafe(coro, update_loop)
                future.result()
            log(f"[scheduler] Completed job: {name}")
        except Exception:
            log(f"[scheduler] Job failed: {name}")
            traceback.print_exc()

    scheduler.add_job(lambda: run_async_job("celebrate", celebrate(app)), "cron", hour=0, minute=0)
    scheduler.add_job(lambda: run_async_job("weekly", weekly(app)), "cron", day_of_week="sun", hour=9)
    scheduler.start()
    return scheduler


async def run_webhook_app():
    if not WEBHOOK_BASE_URL:
        raise RuntimeError("WEBHOOK_BASE_URL is required when BOT_DELIVERY_MODE=webhook.")

    app = build_application()
    server = None
    scheduler = None
    started = False
    webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

    try:
        log("[main] Building Application...")
        await app.initialize()
        await app.start()
        started = True
        log("[main] Application started.")
        await app.bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET_TOKEN or None,
            allowed_updates=Update.ALL_TYPES,
        )
        log(f"[webhook] Registered webhook: {webhook_url}")
        scheduler = start_scheduler(app, asyncio.get_running_loop())
        log("[main] Scheduler started.")
        server = start_http_server(app, asyncio.get_running_loop())
        log("[main] Webhook bot is running...")
        await asyncio.Event().wait()
    finally:
        log("[main] Shutting down...")
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        if server is not None:
            server.shutdown()
            server.server_close()
        if started:
            await app.stop()
        await app.shutdown()

def main():
    try:
        if not TOKEN:
            raise RuntimeError("BOT_TOKEN is missing. Set it in the environment or .env for local development.")
        if should_use_webhooks():
            asyncio.run(run_webhook_app())
            return
        log("[main] Starting in polling mode.")
        app = build_application()
        log("[main] Application built.")
        start_scheduler(app)
        log("[main] Scheduler started.")
        log("[main] Bot running with polling...")
        app.run_polling()
    except Exception:
        print("[main] Exception during startup:")
        traceback.print_exc()

if __name__ == "__main__": main()
