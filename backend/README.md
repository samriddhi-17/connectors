# Connects backend

FastAPI service powering the Connects demo. See the repository root
`README.md` for the full architecture and quickstart.

Run locally (from `backend/`):

```bash
python -m venv .venv
.\.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

All configuration comes from environment variables / `.env` (see
`.env.example` at the repo root). Nothing is hard-coded.