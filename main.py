"""
Sovereign AI Core — Entry Point
Run with:  uvicorn main:app --host 127.0.0.1 --port 8000
Or simply: python main.py
"""

import uvicorn
from backend.app.core.engine import app
from backend.app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
