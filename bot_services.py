import os
import random


HELP_TEXT = (
    "🎂 Birthday Bot Guide\n\n"
    "Make every group celebration organized, cheerful, and easy to manage.\n\n"
    "✨ Personal Commands\n"
    "/start - Activate the bot in this chat\n"
    "/help - Show this guide\n"
    "/setbirthday YYYY-MM-DD - Save your birthday for this group\n"
    "/mybirthday - View your saved birthday in this group\n"
    "/removebirthday - Remove your birthday from this group\n"
    "/birthdays - See who is celebrating today in this group\n\n"
    "👑 Admin Commands\n"
    "/listbirthdays - Show all birthdays in this group, or use GROUP_NO in private chat\n"
    "/addbirthday @user YYYY-MM-DD [Full Name] - Add a birthday in the current group\n"
    "/removeuserbirthday @user - Remove a birthday from the current group\n\n"
    "🗂️ Cross-Group Admin Tools\n"
    "/mygroups - Show the groups you can manage, numbered for quick selection\n"
    "/addbirthdayto GROUP_NO @user YYYY-MM-DD [Full Name] - Add a birthday to a selected managed group\n"
    "/removebirthdayfrom GROUP_NO @user - Remove a birthday from a selected managed group\n"
    "/listallbirthdays - View birthdays across all groups you manage\n"
)

MESSAGES = [
    "🎈 Happy Birthday, {name}! Wishing you a day full of laughter and joy!",
    "🪅 Wishing you a festive and fun-filled birthday, {name}!",
    "🌟 Shine bright, {name}! Happy Birthday and best wishes for the year ahead!",
    "🎁 Wishing you lots of presents and happiness, {name}! Happy Birthday!",
    "🎂 Hope your birthday is as sweet as you, {name}! Enjoy your special day!",
    "🥳 Let's celebrate {name}'s birthday with smiles and good vibes!",
    "🎉 Happy Birthday, {name}! May your dreams come true this year!",
    "🌈 Wishing you a colorful and fun birthday, {name}!",
    "🍦 Hope your day is filled with treats and fun, {name}! Happy Birthday!",
    "🎶 May your birthday be filled with your favorite songs, {name}!",
    "🌻 Sending sunshine and smiles your way, {name}! Happy Birthday!",
    "🧁 Enjoy every moment of your special day, {name}! Happy Birthday!",
    "🎈 Balloons, cake, and lots of cheer for you, {name}!",
    "🌟 Another year, another adventure! Happy Birthday, {name}!",
    "🎊 Wishing you a year of happiness and success, {name}!",
    "🍰 Hope your birthday is layered with fun, {name}!",
    "🎂 Make a wish, {name}! Happy Birthday!",
    "🎉 Here's to you, {name}! Have a fantastic birthday!",
    "🌸 Wishing you a blooming year ahead, {name}! Happy Birthday!",
    "🎁 May your day be wrapped in happiness, {name}!",
    "🎈 Hope your birthday is a blast, {name}!",
    "🌞 Wishing you a bright and cheerful birthday, {name}!",
    "🍦 Treat yourself today, {name}! Happy Birthday!",
    "🎶 Dance and sing, it's your day, {name}!",
    "🌻 May your year be as lovely as you, {name}!",
    "🧁 Sweet wishes for a sweet person, {name}!",
    "🎊 Celebrate big, {name}! Happy Birthday!",
    "🎂 Hope your day is sprinkled with fun, {name}!",
    "🎉 Sending you smiles and hugs, {name}! Happy Birthday!",
    "🌟 Wishing you a magical birthday, {name}!",
    "🎁 Hope you get everything you wish for, {name}!",
    "🎈 Have a fantastic birthday, {name}!",
    "🌸 Enjoy your special day, {name}!",
    "🍰 Here's to cake and good times, {name}!",
    "🎂 Wishing you a year full of joy, {name}!",
    "🎉 Happy Birthday, {name}! Let's make it unforgettable!",
    "🌞 May your day be bright and happy, {name}!",
    "🍦 Celebrate with your favorite things, {name}!",
    "🎶 Hope your birthday is music to your soul, {name}!",
    "🌻 Wishing you a garden of happiness, {name}!",
    "🧁 Enjoy every bite of your birthday cake, {name}!",
    "🎊 Here's to another amazing year, {name}!",
    "🎂 Hope your birthday is full of surprises, {name}!",
    "🎉 Sending you lots of love, {name}! Happy Birthday!",
    "🌟 May your wishes come true, {name}!",
    "🎁 Have a gift-filled birthday, {name}!",
    "🎈 Wishing you a party to remember, {name}!",
    "🌸 May your day be as beautiful as you, {name}!",
    "🫶 Wishing you a heartwarming and joyful birthday, {name}!",
    "🎂 Happy Birthday, {name}! Enjoy every moment!",
]


class BirthdayService:
    def __init__(self, base_dir):
        self.image_dir = os.path.join(base_dir, "assets", "birthday_images")
        self.sent_notifications = {}

    def get_birthday_image_paths(self):
        if not os.path.isdir(self.image_dir):
            return []
        image_names = [
            name for name in sorted(os.listdir(self.image_dir))
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        ]
        return [os.path.join(self.image_dir, name) for name in image_names]

    def get_random_birthday_image_path(self):
        image_paths = self.get_birthday_image_paths()
        return random.choice(image_paths) if image_paths else None

    def format_birthday_name(self, display_name, username):
        clean_display_name = (display_name or "").strip()
        clean_username = (username or "").strip().lstrip("@")
        if clean_display_name and clean_username:
            return f"{clean_display_name}, @{clean_username}"
        if clean_display_name:
            return clean_display_name
        if clean_username:
            return f"@{clean_username}"
        return "birthday star"

    def format_birthday_intro(self, display_name, username):
        clean_display_name = (display_name or "").strip()
        clean_username = (username or "").strip().lstrip("@")
        if clean_display_name and clean_username:
            return f"🎂 Hey there, {clean_display_name}, @{clean_username}. 🎉"
        if clean_display_name:
            return f"🎂 Hey there, {clean_display_name}. 🎉"
        if clean_username:
            return f"🎂 Hey there, @{clean_username}. 🎉"
        return "🎂 Hey there, birthday star. 🎉"

    def build_birthday_message(self, display_name, username):
        intro = self.format_birthday_intro(display_name, username)
        message_name = (display_name or "").strip() or self.format_birthday_name(display_name, username)
        body = random.choice(MESSAGES).format(name=message_name)
        return f"{intro}\n\n{body}"

    def is_birthday_today(self, birthday_text, today_month_day):
        return birthday_text[5:] == today_month_day

    def ensure_day_tracking(self, today_key):
        if today_key not in self.sent_notifications:
            self.sent_notifications[today_key] = set()

    def was_sent_today(self, today_key, username):
        self.ensure_day_tracking(today_key)
        return username in self.sent_notifications[today_key]

    def mark_sent_today(self, today_key, username):
        self.ensure_day_tracking(today_key)
        self.sent_notifications[today_key].add(username)

    async def send_birthday_to_chat(self, bot, chat_id, message_text, image_path):
        if image_path:
            with open(image_path, "rb") as image_file:
                await bot.send_photo(chat_id, image_file, caption=message_text)
            return
        await bot.send_message(chat_id, message_text)

    def get_announcement_chat_ids(self, active_chat_ids, source_chat):
        target_chat_ids = set(active_chat_ids)
        if source_chat and source_chat.type == "private":
            target_chat_ids.discard(source_chat.id)
        if not target_chat_ids and source_chat:
            target_chat_ids.add(source_chat.id)
        return sorted(target_chat_ids)

    async def announce_birthday(self, bot, chat_ids, display_name, username, fallback_chat=None):
        message_text = self.build_birthday_message(display_name, username)
        image_path = self.get_random_birthday_image_path()
        delivered = False
        for chat_id in sorted(chat_ids):
            try:
                await self.send_birthday_to_chat(bot, chat_id, message_text, image_path)
                delivered = True
            except Exception as error:
                print(f"Failed to send birthday announcement to {chat_id}: {error}")

        if delivered or fallback_chat is None:
            return delivered

        try:
            await self.send_birthday_to_chat(bot, fallback_chat.id, message_text, image_path)
            return True
        except Exception as error:
            print(f"Failed to send fallback birthday announcement to {fallback_chat.id}: {error}")
            return False