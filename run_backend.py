"""
CogniGap — Backend Launcher
=============================
Run this script to start the CogniGap FastAPI backend server.

Usage:
    python run_backend.py
"""

import sys
import os

# Ensure project root is in python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import uvicorn
from cognigap.config import FASTAPI_HOST, FASTAPI_PORT

if __name__ == "__main__":
    print()
    print("=" * 64)
    print("  COGNIGAP: AI-Powered Novelty and Overlap Detection Engine")
    print(f"  FastAPI Server: http://localhost:{FASTAPI_PORT}")
    print(f"  API Docs (Swagger): http://localhost:{FASTAPI_PORT}/docs")
    print(f"  Next.js Frontend: http://localhost:3000")
    print("=" * 64)
    print()

    uvicorn.run(
        "cognigap.api:app",
        host=FASTAPI_HOST,
        port=FASTAPI_PORT,
        reload=True,
    )
