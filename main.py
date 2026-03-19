"""
Hudhudbot - Main Application
التطبيق الرئيسي - Webhook + توجيه الرسائل + إرسال للمزودين
"""

import os
import sys

# Force flush all output
sys.stdout = sys.stderr

print("="*50, flush=True)
print("🚀 Hudhud Bot Starting...", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"PORT env: {os.getenv('PORT', 'NOT SET')}", flush=True)
print("="*50, flush=True)

from typing import Optional, Dict, List
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
import uvicorn

# ============================================
# FastAPI App
# ============================================
app = FastAPI(
    title="Hudhudbot",
    description="Hudhudbot - منصة الخدمات الذكية",
    version="2.2.0"
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Hudhud Bot is running!"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ============================================
# Run Server
# ============================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting server on port {port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)
