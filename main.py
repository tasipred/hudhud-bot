#!/usr/bin/env python3
"""Hudhud Bot - Minimal Version"""

import os
import uvicorn
from fastapi import FastAPI

print("=== HUDHUD BOT STARTING ===", flush=True)

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok", "bot": "hudhud"}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"=== Starting on port {port} ===", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)
