from pathlib import Path
import os
from dotenv import load_dotenv
from server.store import MarketStore

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
path = os.getenv("DATABASE_PATH", "./data/market.sqlite")
store = MarketStore(path)
try:
    print(f"SQLite initialized: {path}")
    print(store.stats())
finally:
    store.close()
