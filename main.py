"""
Hudhudbot - Main Application
التطبيق الرئيسي - Webhook + توجيه الرسائل + إرسال للمزودين
"""

import os
import asyncio
from typing import Optional, Dict, List
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
import uvicorn
from twilio.twiml.messaging_response import MessagingResponse

from services.twilio_service import twilio_service
from services.deepseek_service import deepseek_service, RECEPTION_AGENT_PROMPT
from services.supabase_service import supabase_service
from config import APP_NAME, APP_URL, MAX_PROVIDERS_PER_REQUEST

# ============================================
# FastAPI App
# ============================================
app = FastAPI(
    title=APP_NAME,
    description="Hudhudbot - منصة الخدمات الذكية",
    version="2.0.0"
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
# استخراج المعلومات من الرسائل
# ============================================
async def extract_request_info(messages: List[Dict]) -> Dict:
    """
    استخراج معلومات الطلب من سجل المحادثة
    """
    # بناء نص المحادثة
    conversation_text = "\n".join([
        f"{'العميل' if m['sender'] == 'customer' else 'البوت'}: {m['content']}"
        for m in messages[-10:]  # آخر 10 رسائل
    ])
    
    # طلب من AI استخراج المعلومات
    extraction_prompt = """
أنت مساعد ذكي متخصص في استخراج المعلومات من المحادثات.

من المحادثة التالية، استخرج المعلومات التالية بتنسيق JSON فقط:
{
    "service_type": "نوع الخدمة (سباكة، كهرباء، تكييف، تنظيف، نقل عفش، صباغة، نجارة)",
    "city": "المدينة",
    "details": "تفاصيل المشكلة أو الطلب",
    "budget": "الميزانية إن وجدت أو null",
    "is_complete": true/false (هل المعلومات كاملة؟)
}

أعد JSON فقط بدون أي نص إضافي.
"""
    
    result = await deepseek_service.chat(
        messages=[{"role": "user", "content": conversation_text}],
        system_prompt=extraction_prompt
    )
    
    if result["success"]:
        try:
            import json
            content = result["content"].strip()
            # إزالة ```json إن وجدت
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            
            return json.loads(content)
        except:
            pass
    
    return {"is_complete": False}


# ============================================
# البحث عن المزودين وإرسال الطلبات
# ============================================
async def search_and_notify_providers(
    request_id: str,
    service_type: str,
    city: str,
    details: str,
    customer_phone: str
) -> Dict:
    """
    البحث عن مزودين وإرسال طلبات لهم
    """
    print(f"🔍 [ProviderAgent] Searching for: {service_type} in {city}")
    
    # البحث عن مزودين
    providers = await supabase_service.search_providers(
        service_type=service_type,
        city=city,
        limit=MAX_PROVIDERS_PER_REQUEST
    )
    
    if not providers:
        print(f"⚠️ [ProviderAgent] No providers found")
        return {
            "success": False,
            "providers_found": 0,
            "providers_contacted": 0,
            "error": "لا يوجد مزودين متاحين في منطقتك حالياً"
        }
    
    print(f"✅ [ProviderAgent] Found {len(providers)} providers")
    
    # إرسال طلبات للمزودين
    contacted_count = 0
    
    for provider in providers:
        provider_phone = provider.get("whatsapp", "")
        provider_id = provider.get("id")
        provider_name = provider.get("business_name", "مزود")
        
        if not provider_phone:
            continue
        
        # تنسيق رقم الهاتف
        if not provider_phone.startswith("whatsapp:"):
            provider_phone = f"whatsapp:+966{provider_phone.lstrip('0')}"
        
        # إرسال طلب العرض
        message = f"""
🔔 *طلب جديد من هدهد!*

📋 *الخدمة:* {service_type}
📍 *المدينة:* {city}

📝 *التفاصيل:*
{details or 'لا توجد تفاصيل إضافية'}

━━━━━━━━━━━━━━━

💡 *للتقدم بعرض:*
رد على هذه الرسالة بالتنسيق التالي:

السعر: [مبلغك]
ملاحظات: [إن وجدت]

مثال:
السعر: 500 ريال
ملاحظات: متفرغ غداً صباحاً

⏰ العرض مفتوح لمدة ساعتين
        """.strip()
        
        result = twilio_service.send_whatsapp(
            to_number=provider_phone,
            body=message
        )
        
        if result.get("status") in ["sent", "mocked"]:
            contacted_count += 1
            # تسجيل أن الطلب أُرسل للمزود
            await supabase_service.log_provider_request(
                request_id=request_id,
                provider_id=provider_id
            )
            print(f"📤 [ProviderAgent] Sent to: {provider_name}")
    
    return {
        "success": contacted_count > 0,
        "providers_found": len(providers),
        "providers_contacted": contacted_count
    }


# ============================================
# معالجة رد المزود
# ============================================
async def handle_provider_response(
    provider_phone: str,
    message_body: str
) -> str:
    """
    معالجة رد المزود على طلب عرض
    """
    print(f"📥 [ProviderResponse] From: {provider_phone}")
    
    # استخراج معلومات العرض من الرسالة
    extraction_prompt = """
استخرج معلومات العرض من رسالة المزود بتنسيق JSON:
{
    "price": "السعر المقدم (مثل: 500 ريال) أو null",
    "notes": "ملاحظات المزود أو null",
    "is_rejection": true/false (هل المزود يرفض الطلب؟)
}

أعد JSON فقط.
"""
    
    result = await deepseek_service.chat(
        messages=[{"role": "user", "content": message_body}],
        system_prompt=extraction_prompt
    )
    
    if not result["success"]:
        return "عذراً، لم أفهم رسالتك. يرجى إرسال العرض بالتنسيق:\n\nالسعر: [مبلغك]\nملاحظات: [إن وجدت]"
    
    try:
        import json
        content = result["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        
        offer_data = json.loads(content)
        
        if offer_data.get("is_rejection"):
            return "شكراً لإعلامنا. سيتم إبلاغك بالطلبات القادمة."
        
        price = offer_data.get("price")
        if not price:
            return "يرجى تحديد السعر في عرضك."
        
        # الحصول على بيانات المزود
        provider = await supabase_service.get_provider_by_phone(provider_phone)
        
        if not provider:
            return "عذراً، رقمك غير مسجل كمزود في المنصة. للتسجيل: https://hudhud-platform-coral.vercel.app/register"
        
        # الحصول على الطلب النشط للمزود
        # للتبسيط، نستخدم طريقة بديلة - البحث عن آخر طلب غير مكتمل
        # TODO: تحسين هذا لاحقاً
        
        return f"""
✅ *تم استلام عرضك!*

💰 السعر: {price}
📝 الملاحظات: {offer_data.get('notes') or 'لا توجد'}

سيتم إشعار العميل بعرضك قريباً.

شكراً لاستخدامك هدهد! 🦦
        """.strip()
        
    except json.JSONDecodeError:
        return "عذراً، لم أفهم رسالتك. يرجى إرسال العرض بالتنسيق:\n\nالسعر: [مبلغك]\nملاحظات: [إن وجدت]"
    except Exception as e:
        print(f"❌ [ProviderResponse] Error: {e}")
        return "حدث خطأ تقني. يرجى المحاولة مرة أخرى."


# ============================================
# Message Handler - للعملاء
# ============================================
async def handle_customer_message(
    from_number: str,
    message_body: str,
    conversation: Optional[dict] = None
) -> str:
    """
    معالجة رسالة العميل وإرجاع الرد المناسب
    """
    print(f"📨 [CustomerHandler] From: {from_number} | Message: {message_body[:50]}...")
    
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
        
        # إرسال للـ AI للفهم
        ai_response = await deepseek_service.chat(
            messages=[{"role": "user", "content": message_body}],
            system_prompt=RECEPTION_AGENT_PROMPT
        )
        
        if ai_response["success"]:
            reply = ai_response["content"]
            
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
            
            return reply
        else:
            return "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى."
    
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
    
    # حسب الحالة
    if status == ConversationState.COLLECTING:
        # جاري جمع المعلومات
        messages = await supabase_service.get_messages(conversation_id)
        
        # بناء السياق للـ AI
        chat_history = []
        for msg in messages:
            role = "user" if msg["sender"] == "customer" else "assistant"
            chat_history.append({"role": role, "content": msg["content"]})
        
        # إضافة الرسالة الحالية
        chat_history.append({"role": "user", "content": message_body})
        
        # إرسال للـ AI
        ai_response = await deepseek_service.chat(
            messages=chat_history,
            system_prompt=RECEPTION_AGENT_PROMPT
        )
        
        if ai_response["success"]:
            reply = ai_response["content"]
            
            # حفظ الرد
            await supabase_service.save_message(
                conversation_id=conversation_id,
                sender="bot",
                content=reply
            )
            
            # التحقق إذا جمعنا كل المعلومات
            request_info = await extract_request_info(messages + [{"sender": "customer", "content": message_body}])
            
            if request_info.get("is_complete") and request_info.get("service_type") and request_info.get("city"):
                # تحديث السياق
                await supabase_service.update_conversation(
                    conversation_id=conversation_id,
                    status=ConversationState.CONFIRMING,
                    context={
                        "service_type": request_info.get("service_type"),
                        "city": request_info.get("city"),
                        "details": request_info.get("details"),
                        "budget": request_info.get("budget")
                    }
                )
            
            return reply
    
    elif status == ConversationState.CONFIRMING:
        # العميل يؤكد المعلومات
        if any(word in message_body.lower() for word in ["نعم", "صح", "صحيح", "أيوة", "تمام", "أكد", "ابدأ", "ابحث"]):
            # العميل أكد - ننتقل للبحث
            await supabase_service.update_conversation(
                conversation_id=conversation_id,
                status=ConversationState.SEARCHING
            )
            
            # إنشاء طلب الخدمة
            service_type = context.get("service_type", "")
            city = context.get("city", "")
            details = context.get("details", "")
            budget = context.get("budget")
            
            request_result = await supabase_service.create_service_request(
                conversation_id=conversation_id,
                customer_phone=from_number,
                service_type=service_type,
                city=city,
                details=details,
                budget=budget
            )
            
            if request_result.get("success"):
                request_id = request_result.get("request_id")
                offers_url = request_result.get("offers_url")
                
                # تحديث السياق
                await supabase_service.update_conversation(
                    conversation_id=conversation_id,
                    status=ConversationState.WAITING,
                    context={**context, "request_id": request_id, "offer_page_url": offers_url}
                )
                
                # البحث عن المزودين وإرسال الطلبات
                asyncio.create_task(
                    search_and_notify_providers(
                        request_id=request_id,
                        service_type=service_type,
                        city=city,
                        details=details or "",
                        customer_phone=from_number
                    )
                )
                
                return f"""✅ *تم استلام طلبك!*

📋 *الخدمة:* {service_type}
📍 *المدينة:* {city}
{f"📝 *التفاصيل:* {details}" if details else ''}

🔍 جاري البحث عن أفضل المزودين...

🔗 *صفحة العروض:*
{offers_url}

⏰ صلاحية الصفحة: ساعتين

سيصلك إشعار عند وصول عروض جديدة! 📬"""
            else:
                return "عذراً، حدث خطأ أثناء إنشاء الطلب. يرجى المحاولة مرة أخرى."
        else:
            # العميل يريد تعديل
            await supabase_service.update_conversation(
                conversation_id=conversation_id,
                status=ConversationState.COLLECTING
            )
            return "لا مشكلة! أخبرني بالمعلومات الصحيحة، وش التعديل المطلوب؟"
    
    elif status == ConversationState.WAITING:
        # العميل ينتظر العروض
        offers_url = context.get("offer_page_url", f"{APP_URL}/offers")
        return f"""⏳ *جاري انتظار العروض...*

🔗 *صفحة العروض:*
{offers_url}

📊 الصفحة تتحدث تلقائياً عند وصول عروض جديدة!

هل تحتاج مساعدة أخرى؟"""
    
    # رد افتراضي
    return "شكراً لرسالتك! فريق هدهد يهتم بخدمتك. كيف أقدر أساعدك؟"


# ============================================
# Webhook Endpoint - للعملاء
# ============================================
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Webhook endpoint لاستقبال رسائل واتساب من Twilio
    """
    try:
        form_data = await request.form()
        
        from_number = form_data.get("From", "")
        message_body = form_data.get("Body", "")
        
        print(f"📱 [Webhook] From: {from_number}")
        print(f"💬 [Webhook] Message: {message_body}")
        
        if not from_number or not message_body:
            return PlainTextResponse("Missing data", status_code=400)
        
        # تنظيف رقم المرسل
        clean_phone = from_number.replace("whatsapp:", "").replace("+", "")
        
        # التحقق إذا كان المرسل مزود خدمة
        provider = await supabase_service.get_provider_by_phone(clean_phone)
        
        if provider:
            # هذا مزود خدمة
            reply = await handle_provider_response(
                provider_phone=clean_phone,
                message_body=message_body
            )
        else:
            # هذا عميل
            conversation = await supabase_service.get_conversation_by_phone(clean_phone)
            reply = await handle_customer_message(
                from_number=clean_phone,
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
# Webhook Endpoint - للمزودين
# ============================================
@app.post("/webhook/provider")
async def provider_webhook(request: Request):
    """
    Webhook مخصص لردود المزودين
    """
    try:
        form_data = await request.form()
        
        from_number = form_data.get("From", "")
        message_body = form_data.get("Body", "")
        
        print(f"📤 [ProviderWebhook] From: {from_number}")
        print(f"📤 [ProviderWebhook] Message: {message_body}")
        
        if not from_number or not message_body:
            return PlainTextResponse("Missing data", status_code=400)
        
        clean_phone = from_number.replace("whatsapp:", "").replace("+", "")
        
        reply = await handle_provider_response(
            provider_phone=clean_phone,
            message_body=message_body
        )
        
        twiml_response = MessagingResponse()
        twiml_response.message(reply)
        
        return Response(
            content=str(twiml_response),
            media_type="application/xml"
        )
        
    except Exception as e:
        print(f"❌ [ProviderWebhook] Error: {e}")
        twiml_response = MessagingResponse()
        twiml_response.message("حدث خطأ تقني.")
        return Response(
            content=str(twiml_response),
            media_type="application/xml"
        )


# ============================================
# Health Check
# ============================================
@app.get("/")
async def root():
    """فحص صحة الخادم"""
    return {
        "status": "healthy",
        "service": APP_NAME,
        "version": "2.0.0"
    }


@app.get("/health")
async def health():
    """فحص صحة الخادم"""
    return {"status": "ok", "version": "2.0.0"}


# ============================================
# Debug Endpoints
# ============================================
@app.get("/debug/supabase")
async def debug_supabase():
    """اختبار الاتصال بـ Supabase"""
    import httpx
    
    result = {
        "version": "2.0.0",
        "url": supabase_service.url,
        "has_key": bool(supabase_service.key)
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
    
    return result


# ============================================
# Run Server
# ============================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting {APP_NAME} v2.0.0 on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
