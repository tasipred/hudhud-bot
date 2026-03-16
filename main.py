"""
Hudhudbot - Main Application
النسخة المحسنة مع دعم قاعدة البيانات
"""

import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
import uvicorn
from twilio.twiml.messaging_response import MessagingResponse

from agents import reception_agent, provider_agent, ranking_agent, notification_agent, manager_agent
from config import APP_NAME, APP_URL

# Version for deployment tracking
VERSION = "2.0.0"

app = FastAPI(title=APP_NAME, version=VERSION)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Webhook لرسائل واتساب"""
    try:
        form_data = await request.form()
        from_number = form_data.get("From", "")
        message_body = form_data.get("Body", "")
        
        print(f"📱 [Webhook] From: {from_number}")
        print(f"💬 [Webhook] Message: {message_body}")
        print(f"🔖 [Webhook] Version: {VERSION}")
        
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
    return {"status": "healthy", "service": APP_NAME, "version": VERSION}


@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}


@app.get("/debug/supabase")
async def debug_supabase():
    """اختبار الاتصال بـ Supabase"""
    from services.supabase_service import supabase_service
    import httpx

    result = {
        "version": VERSION,
        "url": supabase_service.url,
        "key_prefix": supabase_service.key[:20] + "..." if supabase_service.key else "NOT SET",
        "headers_set": bool(supabase_service.headers),
    }

    # Test connection
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{supabase_service.url}/rest/v1/categories?select=name&limit=1",
                headers=supabase_service.headers,
                timeout=10.0
            )
            result["connection_test"] = {
                "status_code": response.status_code,
                "success": response.status_code == 200
            }
    except Exception as e:
        result["connection_test"] = {
            "success": False,
            "error": str(e)
        }

    return JSONResponse(content=result)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting {APP_NAME} v{VERSION} on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
