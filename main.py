"""
Hudhudbot - Main Application
النسخة المبسطة - تعمل بدون DB للسياق
"""

import os
import time
from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
import uvicorn
from twilio.twiml.messaging_response import MessagingResponse

from agents import reception_agent, provider_agent, ranking_agent, notification_agent, manager_agent
from config import APP_NAME, APP_URL

app = FastAPI(title=APP_NAME, version="1.0.0")


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Webhook لرسائل واتساب"""
    try:
        form_data = await request.form()
        from_number = form_data.get("From", "")
        message_body = form_data.get("Body", "")
        
        print(f"📱 [Webhook] From: {from_number}")
        print(f"💬 [Webhook] Message: {message_body}")
        
        if not from_number or not message_body:
            return PlainTextResponse("Missing data", status_code=400)
        
        # معالجة الرسالة مباشرة عبر الوكيل
        agent_result = await reception_agent.process_message(
            customer_phone=from_number,
            message=message_body,
            conversation_id="local",
            conversation_history=[],
            current_context=None
        )
        
        reply = agent_result["reply"]
        
        # بناء الرد
        twiml_response = MessagingResponse()
        twiml_response.message(reply)
        
        return Response(content=str(twiml_response), media_type="application/xml")
        
    except Exception as e:
        print(f"❌ [Webhook] Error: {e}")
        import traceback
        traceback.print_exc()
        
        twiml_response = MessagingResponse()
        twiml_response.message("عذراً، حدث خطأ تقني. يرجى المحاولة لاحقاً.")
        return Response(content=str(twiml_response), media_type="application/xml")


@app.get("/")
async def root():
    return {"status": "healthy", "service": APP_NAME, "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
async def status():
    return JSONResponse(content={
        "status": "healthy",
        "uptime": "active",
        "metrics": {"total_requests": 0},
        "active_alerts": 0
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting {APP_NAME} on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
