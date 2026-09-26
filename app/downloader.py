"""Pobieranie miesięcznych archiwów ZIP z IMGW i rozpakowywanie brakujących plików CSV."""

import io
import logging
import re
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

ZIP_NAME_RE = re.compile(r'href="((\d{4})_(\d{2})_k\.zip)"')


def expected_csv_name(year: int, month: int) -> str:
    return f"k_d_{month:02d}_{year}.csv"


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "imgw-klimat-api/1.0"})
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as resp:
        return resp.read()


def list_remote_months(year: int) -> list[tuple[int, str]]:
    """Zwraca listę (miesiąc, nazwa_zip) dostępnych na serwerze dla danego roku."""
    html = _fetch(f"{config.BASE_URL}{year}/").decode("utf-8", errors="replace")
    months = {int(m): name for name, y, m in ZIP_NAME_RE.findall(html) if int(y) == year}
    return sorted(months.items())


def _write_utf8(dest: Path, text: str) -> None:
    tmp = dest.with_suffix(".csv.part")
    tmp.write_bytes(text.encode(config.CSV_ENCODING))
    tmp.replace(dest)


def extract_csv(zip_bytes: bytes, target_dir: Path) -> list[Path]:
    """Rozpakowuje CSV z archiwum, przekodowując je z cp1250 (IMGW) na UTF-8."""
    target_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            # Tylko nazwa pliku – chroni przed ścieżkami typu "../" w archiwum.
            name = Path(member).name
            if not name.lower().endswith(".csv"):
                continue
            dest = target_dir / name
            _write_utf8(dest, zf.read(member).decode(config.SOURCE_ENCODING))
            written.append(dest)
    return written


def convert_legacy_files(csv_dir: Path | None = None) -> list[Path]:
    """Przekodowuje na UTF-8 pliki CSV zapisane wcześniej w oryginalnym kodowaniu cp1250."""
    csv_dir = csv_dir or config.CSV_DIR
    converted = []
    for path in sorted(csv_dir.glob("*.csv")) if csv_dir.exists() else []:
        raw = path.read_bytes()
        try:
            raw.decode(config.CSV_ENCODING)
            continue
        except UnicodeDecodeError:
            pass
        _write_utf8(path, raw.decode(config.SOURCE_ENCODING))
        converted.append(path)
    if converted:
        log.info("Przekodowano na UTF-8: %s", ", ".join(p.name for p in converted))
    return converted


def sync(year: int | None = None, csv_dir: Path | None = None) -> list[Path]:
    """Pobiera miesiące, których CSV nie ma jeszcze na dysku. Zwraca listę nowych plików."""
    year = year or date.today().year
    csv_dir = csv_dir or config.CSV_DIR
    csv_dir.mkdir(parents=True, exist_ok=True)

    try:
        remote = list_remote_months(year)
    except Exception:
        log.exception("Nie udało się pobrać listy plików dla roku %s", year)
        return []

    new_files: list[Path] = []
    for month, zip_name in remote:
        if (csv_dir / expected_csv_name(year, month)).exists():
            continue
        url = f"{config.BASE_URL}{year}/{zip_name}"
        try:
            log.info("Pobieram %s", url)
            new_files += extract_csv(_fetch(url), csv_dir)
        except Exception:
            log.exception("Błąd pobierania/rozpakowania %s", url)
    if new_files:
        log.info("Nowe pliki: %s", ", ".join(p.name for p in new_files))
    else:
        log.info("Brak nowych plików dla roku %s", year)
    return new_files
