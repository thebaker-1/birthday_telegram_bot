import os
from dotenv import load_dotenv

load_dotenv()
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL is not set.")
    exit(1)

try:
    print(f"Connecting to: {DATABASE_URL}")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
            if version is not None:
                print(f"Connection successful! Postgres version: {version[0]}")
            else:
                print("Connection successful, but no version returned.")
except Exception as e:
    print(f"Connection failed: {e}")
    exit(2)
