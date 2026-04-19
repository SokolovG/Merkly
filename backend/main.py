"""Backend entry point.

Run (after 19-04 sets up backend/pyproject.toml):
    cd backend && uvicorn main:app --host 0.0.0.0 --port 8080
"""

from backend.src.presentation.routes import create_app

app = create_app()
