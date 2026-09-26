import os
from pathlib import Path

BASE_URL = os.getenv(
    "IMGW_BASE_URL",
    "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/klimat/",
)
DATA_DIR = Path(os.getenv("IMGW_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
CSV_DIR = DATA_DIR / "csv"
SYNC_INTERVAL_HOURS = float(os.getenv("IMGW_SYNC_INTERVAL_HOURS", "24"))
SYNC_ON_STARTUP = os.getenv("IMGW_SYNC_ON_STARTUP", "1") == "1"
CORS_ORIGINS = [o.strip() for o in os.getenv("IMGW_CORS_ORIGINS", "http://localhost:4200").split(",") if o.strip()]
HTTP_TIMEOUT = 60
SOURCE_ENCODING = "cp1250"
CSV_ENCODING = "utf-8"
