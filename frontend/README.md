# Frontend — Position Explorer

Interactive chess board with live win/draw/loss rates by Elo bin from the processed database.

## Run

From project root (with DB build running or complete):

```bash
pip install -r requirements.txt
python -m uvicorn api.server:app --reload --port 8000
```

Open http://127.0.0.1:8000

## API

- `GET /api/health` — database build status
- `GET /api/position/stats?fen=...` — bin and move stats for a FEN
