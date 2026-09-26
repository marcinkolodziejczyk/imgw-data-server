import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import config, downloader, main
from app.store import store

ROWS = [
    '"254220090","OLECKO","2026","07","01","32.2","","16.8","","23.8","","16.4","","2.6","","W","","9"',
    '"254220090","OLECKO","2026","07","02","30.0","","15.0","","22.0","","14.0","","0.0","","","","9"',
    '"249190560","JABŁONKA","2026","07","01","29.3","","14.3","","20.9","","","8","2.3","","W","","9"',
]
ROWS_AUG = ['"254220090","OLECKO","2026","08","01","25.0","","12.0","","18.0","","10.0","","","8","","","9"']


def make_zip(name: str, rows: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, ("\r\n".join(rows) + "\r\n").encode("cp1250"))
    return buf.getvalue()


LISTING = '<a href="2026_07_k.zip">2026_07_k.zip</a> <a href="2026_08_k.zip">2026_08_k.zip</a>'
ZIPS = {
    "2026_07_k.zip": make_zip("k_d_07_2026.csv", ROWS),
    "2026_08_k.zip": make_zip("k_d_08_2026.csv", ROWS_AUG),
}


@pytest.fixture
def fake_remote(monkeypatch):
    calls = []

    def fake_fetch(url: str) -> bytes:
        calls.append(url)
        if url.endswith("/2026/"):
            return LISTING.encode()
        return ZIPS[url.rsplit("/", 1)[1]]

    monkeypatch.setattr(downloader, "_fetch", fake_fetch)
    return calls


@pytest.fixture
def csv_dir(tmp_path, monkeypatch):
    d = tmp_path / "csv"
    monkeypatch.setattr(config, "CSV_DIR", d)
    return d


def test_sync_downloads_only_missing_months(fake_remote, csv_dir):
    csv_dir.mkdir()
    (csv_dir / "k_d_07_2026.csv").write_bytes(("\r\n".join(ROWS) + "\r\n").encode("cp1250"))

    new = downloader.sync(2026)

    assert [p.name for p in new] == ["k_d_08_2026.csv"]
    assert not any(u.endswith("2026_07_k.zip") for u in fake_remote)
    assert downloader.sync(2026) == []


def test_extracted_csv_is_utf8(fake_remote, csv_dir):
    downloader.sync(2026)
    text = (csv_dir / "k_d_07_2026.csv").read_bytes().decode("utf-8")
    assert "JABŁONKA" in text


def test_convert_legacy_cp1250_files(csv_dir):
    csv_dir.mkdir()
    legacy = csv_dir / "k_d_06_2026.csv"
    legacy.write_bytes('"250190390","KROŚCIENKO","2026","06","01"\r\n'.encode("cp1250"))
    ascii_only = csv_dir / "k_d_05_2026.csv"
    ascii_only.write_bytes(b'"254220090","OLECKO","2026","05","01"\r\n')

    assert downloader.convert_legacy_files(csv_dir) == [legacy]
    assert "KROŚCIENKO" in legacy.read_bytes().decode("utf-8")
    assert downloader.convert_legacy_files(csv_dir) == []
    assert not list(csv_dir.glob("*.part"))


@pytest.fixture
def client(fake_remote, csv_dir, monkeypatch):
    monkeypatch.setattr(config, "SYNC_ON_STARTUP", True)
    with TestClient(main.app) as c:
        # Czekamy na zakończenie pierwszej synchronizacji uruchamianej w tle.
        for _ in range(100):
            if len(store.files()) == 2:
                break
            time.sleep(0.05)
        yield c


def test_stations(client):
    r = client.get("/api/stations")
    assert r.status_code == 200
    assert {"code": "249190560", "name": "JABŁONKA"} in r.json()


def test_station_whole_year(client):
    data = client.get("/api/data", params={"station": "254220090"}).json()
    assert [d["date"] for d in data] == ["2026-07-01", "2026-07-02", "2026-08-01"]


def test_station_month(client):
    data = client.get("/api/data", params={"station": "254220090", "month": 7}).json()
    assert len(data) == 2


def test_station_month_day(client):
    data = client.get("/api/data", params={"station": "254220090", "month": 7, "day": 1}).json()
    assert len(data) == 1
    rec = data[0]
    assert rec["tmax"] == 32.2 and rec["tmin_ground"] == 16.4 and rec["precipitation_type"] == "W"
    assert rec["snow_depth"] is None and rec["snow_depth_status"] == "9"


def test_missing_values_are_null(client):
    rec = client.get("/api/data", params={"station": "249190560", "month": 7, "day": 1}).json()[0]
    assert rec["tmin_ground"] is None and rec["tmin_ground_status"] == "8"


def test_day_requires_month(client):
    assert client.get("/api/data", params={"station": "254220090", "day": 1}).status_code == 400


def test_unknown_station(client):
    assert client.get("/api/data", params={"station": "000"}).status_code == 404


def test_invalid_month(client):
    assert client.get("/api/data", params={"station": "254220090", "month": 13}).status_code == 422
