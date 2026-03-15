"""
Hudhudbot - Main Application
التطبيق الرئيسي - Webhook + توجيه الرسائل
"""

import os
import asyncio
import time
from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
import uvicorn
from twilio.twiml.messaging_response import MessagingResponse

from services.twilio_service import twilio_service
from services.supabase_service import supabase_service
from agents import (
    reception_agent,
    provider_agent,
    ranking_agent,
    notification_agent,
    manager_agent
)
from config import APP_NAME, LOG_LEVEL, APP_URL

# ============================================
# FastAPI App
# ============================================
app = FastAPI(
    title=APP_NAME,
    description="Hudhudbot - منصة الخدمات الذكية",
    version="1.0.0"
)


# ============================================
# State Machine - حالات المحادثة
# ============================================
class ConversationState:
    """حالات المحادثة الممكنة"""
    NEW = "new"                      # أول رسالة
    COLLECTING = "collecting"         # جمع المعلومات
    CONFIRMING = "confirming"         # تأكيد المعلومات
    SEARCHING = "searching"           # البحث عن مزودين
    WAITING = "waiting"               # انتظار العروض
    PRESENTING = "presenting"         # تقديم العروض
    COMPLETED = "completed"           # مكتمل


# ============================================
# Message Handler
# ============================================
async def handle_message(
    from_number: str,
    message_body: str,
    conversation: Optional[dict] = None
) -> str:
    """
    معالجة الرسالة الواردة وإرجاع الرد المناسب
    
    Args:
        from_number: رقم المرسل
        message_body: نص الرسالة
        conversation: بيانات المحادثة الحالية (إن وجدت)
    
    Returns:
        نص الرد
    """
    start_time = time.time()
    print(f"📨 [Handler] From: {from_number} | Message: {message_body[:50]}...")
    
    # حالة جديدة - أول رسالة
    if not conversation:
        # إنشاء محادثة جديدة
        result = await supabase_service.create_conversation(
            customer_phone=from_number,
            initial_message=message_body
        )
        
        conversation_id = result.get("conversation_id")
        
        # حفظ الرسالة
        await supabase_service.save_message(
            conversation_id=conversation_id,
            sender="customer",
            content=message_body
        )
        
        # معالجة عبر وكيل الاستقبال
        agent_result = await reception_agent.process_message(
            customer_phone=from_number,
            message=message_body,
            conversation_id=conversation_id,
            conversation_history=[]  # محادثة جديدة
        )
        
        reply = agent_result["reply"]
        
        # حفظ الرد
        await supabase_service.save_message(
            conversation_id=conversation_id,
            sender="bot",
            content=reply
        )
        
        # تحديث حالة المحادثة
        await supabase_service.update_conversation(
            conversation_id=conversation_id,
            status=ConversationState.COLLECTING
        )
        
        # تسجيل في الإحصائيات
        response_time = time.time() - start_time
        await manager_agent.log_request(
            request_id=conversation_id,
            success=True,
            response_time=response_time
        )
        
        return reply
    
    # محادثة موجودة - متابعة
    status = conversation.get("status", ConversationState.NEW)
    context = conversation.get("context", {})
    conversation_id = conversation.get("id")
    
    # حفظ رسالة العميل
    await supabase_service.save_message(
        conversation_id=conversation_id,
        sender="customer",
        content=message_body
    )
    
    # جلب الرسائل السابقة
    messages = await supabase_service.get_messages(conversation_id)
    
    # حسب الحالة
    if status == ConversationState.COLLECTING:
        # جاري جمع المعلومات - معالجة عبر وكيل الاستقبال
        agent_result = await reception_agent.process_message(
            customer_phone=from_number,
            message=message_body,
            conversation_id=conversation_id,
            conversation_history=messages
        )
        
        reply = agent_result["reply"]
        
        # حفظ الرد
        await supabase_service.save_message(
            conversation_id=conversation_id,
            sender="bot",
            content=reply
        )
        
        # التحقق إذا كان جاهز للمطابقة
        if agent_result.get("ready_for_matching"):
            # تحديث الحالة
            await supabase_service.update_conversation(
                conversation_id=conversation_id,
                status=ConversationState.SEARCHING
            )
            
            # تشغيل وكيل المزودين
            request_id = agent_result.get("request_id")
            extracted_data = agent_result.get("extracted_data", {})
            
            provider_result = await provider_agent.find_and_contact_providers(
                request_id=request_id,
                service_type=extracted_data.get("service_type"),
                city=extracted_data.get("city"),
                details=extracted_data.get("details"),
                budget=extracted_data.get("budget"),
                customer_phone=from_number
            )
            
            # تحديث الحالة
            await supabase_service.update_conversation(
                conversation_id=conversation_id,
                status=ConversationState.WAITING,
                context={"request_id": request_id}
            )
        
        return reply
    
    elif status == ConversationState.CONFIRMING:
        # العميل يؤكد المعلومات
        if any(word in message_body.lower() for word in ["نعم", "صح", "صحيح", "أيوة", "تمام", "اكيد"]):
            # العميل أكد - ننتقل للبحث
            await supabase_service.update_conversation(
                conversation_id=conversation_id,
                status=ConversationState.SEARCHING
            )
            
            # TODO: تشغيل وكيل المزودين
            
            return "ممتاز! 🔍 جاري البحث عن أفضل المزودين في منطقتك...\n\nسيصلك رابط صفحة العروض خلال دقائق! ⏳"
        else:
            # العميل يريد تعديل
            await supabase_service.update_conversation(
                conversation_id=conversation_id,
                status=ConversationState.COLLECTING
            )
            return "لا مشكلة! أخبرني بالمعلومات الصحيحة، وش التعديل المطلوب؟"
    
    elif status == ConversationState.WAITING:
        # العميل ينتظر العروض
        request_id = context.get("request_id")
        
        # جلب العروض الحالية
        offers = await supabase_service.get_offers_for_request(request_id)
        
        if offers:
            # ترتيب العروض
            ranked = await ranking_agent.rank_offers(request_id)
            
            # تحديث الحالة
            await supabase_service.update_conversation(
                conversation_id=conversation_id,
                status=ConversationState.PRESENTING
            )
            
            return f"📊 لديك {len(offers)} عروض!\n\n{ranked.get('summary', 'شوف العروض على الرابط')}"
        
        return f"⏳ جاري انتظار العروض...\n\nيمكنك متابعة العروض على صفحتك:\n{APP_URL}/offers/{context.get('offer_slug', '')}"
    
    elif status == ConversationState.PRESENTING:
        # العميل يشوف العروض
        return "📋 العروض متاحة على صفحتك!\n\nاختر المزود المناسب وتواصل معه مباشرة 🤝"
    
    # رد افتراضي
    return "شكراً لرسالتك! فريق هدهد يهتم بخدمتك. كيف أقدر أساعدك؟"


# ============================================
# Webhook Endpoint
# ============================================
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Webhook endpoint لاستقبال رسائل واتساب من Twilio
    """
    try:
        # قراءة البيانات
        form_data = await request.form()
        
        from_number = form_data.get("From", "")
        message_body = form_data.get("Body", "")
        
        print(f"📱 [Webhook] From: {from_number}")
        print(f"💬 [Webhook] Message: {message_body}")
        
        # التحقق من وجود رسالة
        if not from_number or not message_body:
            return PlainTextResponse("Missing data", status_code=400)
        
        # البحث عن محادثة موجودة
        conversation = await supabase_service.get_conversation_by_phone(from_number)
        
        # معالجة الرسالة
        reply = await handle_message(
            from_number=from_number,
            message_body=message_body,
            conversation=conversation
        )
        
        # بناء TwiML Response
        twiml_response = MessagingResponse()
        twiml_response.message(reply)
        
        return Response(
            content=str(twiml_response),
            media_type="application/xml"
        )
        
    except Exception as e:
        print(f"❌ [Webhook] Error: {e}")
        import traceback
        traceback.print_exc()
        
        twiml_response = MessagingResponse()
        twiml_response.message("عذراً، حدث خطأ تقني. يرجى المحاولة لاحقاً.")
        return Response(
            content=str(twiml_response),
            media_type="application/xml"
        )


# ============================================
# Provider Webhook (ردود المزودين)
# ============================================
@app.post("/webhook/provider")
async def provider_webhook(request: Request):
    """
    Webhook لاستقبال ردود المزودين على طلبات العروض
    """
    try:
        form_data = await request.form()
        
        from_number = form_data.get("From", "")
        message_body = form_data.get("Body", "")
        
        print(f"👷 [Provider Webhook] From: {from_number}")
        print(f"💬 [Provider Webhook] Message: {message_body}")
        
        # معالجة رد المزود
        result = await provider_agent.process_provider_response(
            provider_phone=from_number,
            message=message_body
        )
        
        if result.get("success"):
            # تسجيل العرض
            await manager_agent.log_offer(result.get("offer_id", ""))
            
            # إشعار العميل إذا كان أول عرض
            # TODO: جلب بيانات العميل وإرسال إشعار
        
        # بناء الرد
        twiml_response = MessagingResponse()
        if result.get("success"):
            twiml_response.message("✅ تم استلام عرضك بنجاح!")
        else:
            twiml_response.message(f"❌ {result.get('error', 'حدث خطأ')}")
        
        return Response(
            content=str(twiml_response),
            media_type="application/xml"
        )
        
    except Exception as e:
        print(f"❌ [Provider Webhook] Error: {e}")
        twiml_response = MessagingResponse()
        twiml_response.message("حدث خطأ تقني.")
        return Response(
            content=str(twiml_response),
            media_type="application/xml"
        )


# ============================================
# Health Check & Status
# ============================================
@app.get("/")
async def root():
    """فحص صحة الخادم"""
    return {
        "status": "healthy",
        "service": APP_NAME,
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """فحص صحة الخادم"""
    return {"status": "ok"}


@app.get("/status")
async def status():
    """حالة النظام الكاملة"""
    system_status = await manager_agent.get_system_status()
    return JSONResponse(content=system_status)


@app.get("/report")
async def daily_report():
    """التقرير اليومي"""
    report = await manager_agent.get_daily_report()
    return JSONResponse(content=report)


# ============================================
# Run Server
# ============================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting {APP_NAME} on port {port}")
    print(f"📱 WhatsApp: +966596268690")
    print(f"🔗 Webhook: /webhook/whatsapp")
    uvicorn.run(app, host="0.0.0.0", port=port)
