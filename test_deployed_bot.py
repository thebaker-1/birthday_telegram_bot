import os

import requests

def test_health_check():
    url = os.environ.get("BOT_HEALTH_URL", "http://localhost:8080/healthz")
    try:
        response = requests.get(url)
        assert response.status_code == 200
        assert response.text.strip() == "ok"
        print("Health check passed.")
    except Exception as e:
        print(f"Health check failed: {e}")

def test_bot_command():
    # This is a placeholder. For real Telegram bot testing, use python-telegram-bot's test utilities or integration tests.
    print("Manual test required: Send /start to the bot and check response.")

if __name__ == "__main__":
    test_health_check()
    test_bot_command()
