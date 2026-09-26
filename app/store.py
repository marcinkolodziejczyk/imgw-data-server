"""Dane z plików CSV trzymane w pamięci, z indeksem po stacji."""

import csv
import logging
import threading
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

# Kolumny wg k_d_format.txt (IMGW): wartość i jej status pomiaru.
NUMERIC_FIELDS = [
    ("tmax", 5),
    ("tmin", 7),
    ("tavg", 9),
    ("tmin_ground", 11),
    ("precipitation", 13),
]


def _num(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _str(value: str) -> str | None:
    return value.strip() or None


def parse_row(row: list[str]) -> dict | None:
    if len(row) < 18:
        return None
    try:
        year, month, day = int(row[2]), int(row[3]), int(row[4])
    except ValueError:
        return None
    rec: dict = {
        "station_code": row[0].strip(),
        "station_name": row[1].strip(),
        "date": f"{year:04d}-{month:02d}-{day:02d}",
        "year": year,
        "month": month,
        "day": day,
    }
    for name, idx in NUMERIC_FIELDS:
        rec[name] = _num(row[idx])
        rec[f"{name}_status"] = _str(row[idx + 1])
    rec["precipitation_type"] = _str(row[15])
    rec["snow_depth"] = _num(row[16])
    rec["snow_depth_status"] = _str(row[17])
    return rec


class DataStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_station: dict[str, list[dict]] = {}
        self._stations: dict[str, str] = {}
        self._files: list[str] = []

    def load(self, csv_dir: Path | None = None) -> None:
        csv_dir = csv_dir or config.CSV_DIR
        by_station: dict[str, list[dict]] = {}
        stations: dict[str, str] = {}
        files = sorted(csv_dir.glob("*.csv")) if csv_dir.exists() else []
        for path in files:
            with path.open(encoding=config.CSV_ENCODING, newline="") as f:
                for row in csv.reader(f):
                    rec = parse_row(row)
                    if rec is None:
                        continue
                    by_station.setdefault(rec["station_code"], []).append(rec)
                    stations[rec["station_code"]] = rec["station_name"]
        for recs in by_station.values():
            recs.sort(key=lambda r: r["date"])
        with self._lock:
            self._by_station, self._stations, self._files = by_station, stations, [p.name for p in files]
        log.info("Wczytano %d plików, %d stacji", len(files), len(stations))

    def stations(self) -> list[dict]:
        with self._lock:
            items = self._stations.items()
            return sorted(({"code": c, "name": n} for c, n in items), key=lambda s: s["name"])

    def files(self) -> list[str]:
        with self._lock:
            return list(self._files)

    def has_station(self, code: str) -> bool:
        with self._lock:
            return code in self._by_station

    def query(self, station: str, year: int | None = None, month: int | None = None, day: int | None = None) -> list[dict]:
        with self._lock:
            recs = self._by_station.get(station, [])
        return [
            r
            for r in recs
            if (year is None or r["year"] == year)
            and (month is None or r["month"] == month)
            and (day is None or r["day"] == day)
        ]


store = DataStore()
