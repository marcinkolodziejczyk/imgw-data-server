# IMGW – API dobowych danych klimatycznych

Aplikacja raz dziennie sprawdza
[katalog IMGW](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/klimat/)
dla bieżącego roku. Pobiera ZIP-y tych miesięcy, których CSV nie ma jeszcze w `data/csv/`, rozpakowuje je
i udostępnia dane w formacie JSON. Dane są trzymane w pamięci i przeładowywane po pobraniu nowego pliku.

IMGW publikuje CSV w kodowaniu cp1250. Przy rozpakowaniu pliki są przekodowywane i zapisywane w `data/csv/`
jako UTF-8 (bez BOM). Pliki cp1250 zapisane przez wcześniejsze wersje aplikacji są przekodowywane przy starcie.

## Uruchomienie

```powershell
cd imgw-data-server
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Dokumentacja Swagger: http://localhost:8000/docs

## Endpointy

| Endpoint | Opis |
|---|---|
| `GET /api/stations` | Lista stacji `[{code, name}]` |
| `GET /api/data?station=254220090` | Cały dostępny rok dla stacji |
| `GET /api/data?station=254220090&month=7` | Wybrany miesiąc |
| `GET /api/data?station=254220090&month=7&day=15` | Wybrany dzień |
| `GET /api/status` | Czas ostatniej synchronizacji i wczytane pliki |

Opcjonalny parametr `year` przydaje się, gdy na dysku są dane z więcej niż jednego roku.
`day` bez `month` zwraca 400, a nieznana stacja zwraca 404.

Przykładowy rekord:

```json
{
  "station_code": "254220090", "station_name": "OLECKO", "date": "2026-07-31",
  "year": 2026, "month": 7, "day": 31,
  "tmax": 32.2, "tmax_status": null, "tmin": 16.8, "tmin_status": null,
  "tavg": 23.8, "tavg_status": null, "tmin_ground": 16.4, "tmin_ground_status": null,
  "precipitation": 2.6, "precipitation_status": null, "precipitation_type": "W",
  "snow_depth": null, "snow_depth_status": "9"
}
```

Statusy pomiaru wg IMGW: `"8"` – brak pomiaru, `"9"` – brak zjawiska. `precipitation_type`: `S` – śnieg,
`W` – deszcz.

## Konfiguracja (zmienne środowiskowe)

| Zmienna | Domyślnie |
|---|---|
| `IMGW_DATA_DIR` | `data` w katalogu projektu (CSV trafiają do `data/csv`) |
| `IMGW_SYNC_INTERVAL_HOURS` | `24` |
| `IMGW_SYNC_ON_STARTUP` | `1` |
| `IMGW_CORS_ORIGINS` | `http://localhost:4200` (lista po przecinku) |

## Testy

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
```
