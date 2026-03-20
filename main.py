"""
Hudhudbot - Main Application
التطبيق الرئيسي - Webhook + توجيه الرسائل + إرسال للمزودين
Version: 2.2.1 - Full Bot
"""

# Force flush output
import sys
sys.stdout.reconfigure(line_buffering=True)

print("=" * 50, flush=True)
print("🚀 Hudhud Bot v2.2.1 Starting...", flush=True)
print("=" * 50, flush=True)

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
from services.memory_service import memory_service, log_customer_request, get_user_context, get_smart_suggestion
from config import APP_NAME, APP_URL, MAX_PROVIDERS_PER_REQUEST

# ============================================
# FastAPI App
# ============================================
app = FastAPI(
    title=APP_NAME,
    description="Hudhudbot - منصة الخدمات الذكية",
    version="2.1.0"
)


# ============================================
# Startup Event - تهيئة الذاكرة
# ============================================
@app.on_event("startup")
async def startup_event():
    """تهيئة الخدمات عند بدء التشغيل"""
    try:
        print("🔧 تهيئة الخدمات...")
        
        # تهيئة خدمة الذاكرة (غير حاسمة - يمكن العمل بدونها)
        try:
            memory_initialized = await memory_service.initialize()
            if memory_initialized:
                print("✅ [Memory] Memory service initialized")
            else:
                print("⚠️ [Memory] Memory service not available (tables may not exist)")
        except Exception as mem_err:
            print(f"⚠️ [Memory] Initialization skipped: {mem_err}")
        
        print("✅ Bot ready!")
    except Exception as e:
        print(f"❌ Startup error: {e}")
        # لا نرمي الخطأ - نريد أن يعمل التطبيق حتى لو فشلت التهيئة


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

# استخراج محلي (بدون AI)
def extract_info_locally(messages: List[Dict]) -> Dict:
    """
    استخراج محلي للمعلومات من الرسائل (أسرع وأكثر موثوقية)
    """
    # دمج كل رسائل العميل
    customer_messages = " ".join([
        m['content'] for m in messages 
        if m.get('sender') == 'customer' or m.get('direction') == 'inbound'
    ])
    
    result = {
        "service_type": None,
        "city": None,
        "details": None,
        "budget": None,
        "is_complete": False
    }
    
    # استخراج الخدمة
    services = {
        "سباك": "سباكة", "سباكة": "سباكة", "تسريب": "سباكة",
        "كهرب": "كهرباء", "كهرباء": "كهرباء",
        "تنظيف": "تنظيف", "نظاف": "تنظيف",
        "تكييف": "تكييف", "مكيف": "تكييف",
        "نقل": "نقل عفش", "عفش": "نقل عفش", "أثاث": "نقل عفش",
        "صباغ": "صباغة", "دهان": "صباغة",
        "نجار": "نجارة", "نجارة": "نجارة"
    }
    
    for keyword, service in services.items():
        if keyword in customer_messages:
            result["service_type"] = service
            break
    
    # استخراج المدينة
    cities = ["الرياض", "جدة", "مكة", "المدينة", "الدمام", "الخبر", "الطائف", 
              "تبوك", "بريدة", "خميس مشيط", "حائل", "نجران", "أبها", "جازان"]
    
    for city in cities:
        if city in customer_messages:
            result["city"] = city
            break
    
    # استخراج الميزانية
    import re
    budget_match = re.search(r'(\d+)\s*(ريال|ر\.س)', customer_messages)
    if budget_match:
        result["budget"] = f"{budget_match.group(1)} ريال"
    
    # التحقق من الاكتمال
    if result["service_type"] and result["city"]:
        result["is_complete"] = True
        result["details"] = customer_messages
    
    return result


async def extract_request_info(messages: List[Dict]) -> Dict:
    """
    استخراج معلومات الطلب من سجل المحادثة
    """
    # أولاً نجرب الاستخراج المحلي (أسرع وأكثر موثوقية)
    local_result = extract_info_locally(messages)
    if local_result["is_complete"]:
        return local_result
    
    # إذا لم يكتمل، نستخدم AI كـ fallback
    conversation_text = "\n".join([
        f"{'العميل' if m.get('sender') == 'customer' or m.get('direction') == 'inbound' else 'البوت'}: {m['content']}"
        for m in messages[-10:]
    ])
    
    extraction_prompt = """
أنت مساعد ذكي متخصص في استخراج المعلومات من المحادثات العربية.

من المحادثة التالية، استخرج المعلومات التالية بتنسيق JSON فقط:
{
    "service_type": "نوع الخدمة (سباكة، كهرباء، تكييف، تنظيف، نقل عفش، صباغة، نجارة)",
    "city": "المدينة",
    "details": "تفاصيل المشكلة أو الطلب",
    "budget": "الميزانية إن وجدت أو null",
    "is_complete": true/false (هل المعلومات كاملة؟)
}

⚠️ قواعد مهمة:
- "نقل عفش" هي الخدمة الأساسية إذا ذكر العميل النقل
- "تغليف وتفريغ" هي خدمات إضافية لا تغيّر نوع الخدمة
- إذا ذكرت المدينة مسبقاً، احتفظ بها
- لا تغيّر نوع الخدمة المذكور سابقاً

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
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            
            return json.loads(content)
        except:
            pass
    
    return local_result


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
    البحث عن مزودين وإرسال طلبات لهم مع روابط فريدة
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
    
    # استخراج معرفات المزودين
    provider_ids = [p.get("id") for p in providers if p.get("id")]
    
    # إنشاء روابط فريدة لكل مزود
    print(f"🔗 [ProviderAgent] Creating unique links for {len(provider_ids)} providers...")
    offer_links = await supabase_service.create_provider_offer_links(
        request_id=request_id,
        provider_ids=provider_ids,
        expiry_hours=2
    )
    
    if not offer_links:
        print(f"⚠️ [ProviderAgent] Failed to create offer links")
        return {
            "success": False,
            "providers_found": len(providers),
            "providers_contacted": 0,
            "error": "فشل في إنشاء روابط العروض"
        }
    
    # بناء خريطة الرابط -> المزود
    link_map = {link["provider_id"]: link for link in offer_links}
    
    # إرسال طلبات للمزودين
    contacted_count = 0
    
    for provider in providers:
        provider_phone = provider.get("whatsapp", "")
        provider_id = provider.get("id")
        provider_name = provider.get("business_name", "مزود")
        provider_rating = provider.get("rating", "جديد")
        
        if not provider_phone:
            continue
        
        # الحصول على رابط المزود
        provider_link = link_map.get(provider_id)
        if not provider_link:
            print(f"⚠️ [ProviderAgent] No link for provider {provider_id}")
            continue
        
        offer_url = provider_link.get("link_url")
        
        # تنسيق رقم الهاتف
        if not provider_phone.startswith("whatsapp:"):
            # إذا كان الرقم يبدأ بـ 966، نستخدمه مباشرة
            if provider_phone.startswith("966"):
                provider_phone = f"whatsapp:+{provider_phone}"
            # إذا كان يبدأ بـ 0، نزيله ونضيف 966
            elif provider_phone.startswith("0"):
                provider_phone = f"whatsapp:+966{provider_phone.lstrip('0')}"
            # وإلا نضيف 966
            else:
                provider_phone = f"whatsapp:+966{provider_phone}"
        
        # إرسال طلب العرض مع الرابط
        message = f"""
🔔 *طلب جديد من هدهد!*

📋 *الخدمة:* {service_type}
📍 *المدينة:* {city}

📝 *التفاصيل:*
{details or 'لا توجد تفاصيل إضافية'}

━━━━━━━━━━━━━━━

🔗 *للتقدم بعرضك، اضغط هنا:*
{offer_url}

⏰ *الرابط صالح لمدة ساعتين*

💡 ملاحظة: رقم العميل محجوب للحفاظ على الخصوصية
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
            print(f"📤 [ProviderAgent] Sent to: {provider_name} | Link: {offer_url[:50]}...")
    
    return {
        "success": contacted_count > 0,
        "providers_found": len(providers),
        "providers_contacted": contacted_count,
        "offer_links_created": len(offer_links)
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
    
    التدفق:
    1. التحقق من تسجيل المزود
    2. إيجاد الطلب النشط للمزود
    3. استخراج معلومات العرض
    4. حفظ العرض في قاعدة البيانات
    5. إشعار العميل
    """
    print(f"📥 [ProviderResponse] From: {provider_phone}")
    
    # 1. التحقق من المزود
    provider = await supabase_service.get_provider_by_phone(provider_phone)
    
    if not provider:
        return "عذراً، رقمك غير مسجل كمزود في المنصة. للتسجيل: https://hudhud-platform-coral.vercel.app/register"
    
    provider_id = provider.get("id")
    provider_name = provider.get("business_name", "مزود")
    
    print(f"✅ [ProviderResponse] Provider found: {provider_name}")
    
    # 2. إيجاد الطلب النشط
    active_request = await supabase_service.get_active_request_for_provider(provider_id)
    
    if not active_request:
        print(f"⚠️ [ProviderResponse] No active request for provider")
        return f"""
عذراً، لا يوجد طلبات جديدة بانتظار عرضك حالياً.

💡 عندما يصل طلب جديد يطابق تخصصك، ستصلك رسالة فوراً.

شكراً لكونك جزءاً من هدهد! 🦦
        """.strip()
    
    request_id = active_request.get("request_id")
    customer_phone = active_request.get("customer_phone", "")
    
    print(f"📋 [ProviderResponse] Active request: {request_id} | Customer: {customer_phone}")
    
    # 3. استخراج معلومات العرض
    extraction_prompt = """
استخرج معلومات العرض من رسالة المزود بتنسيق JSON فقط:
{
    "price": "السعر المقدم (مثل: 500 ريال) أو null",
    "notes": "ملاحظات المزود أو null",
    "estimated_time": "الوقت المتوقع (مثل: غداً صباحاً) أو null",
    "is_rejection": true/false (هل المزود يرفض الطلب؟)
}

أعد JSON فقط بدون أي نص إضافي.
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
        
        # إذا المزود يرفض
        if offer_data.get("is_rejection"):
            return "شكراً لإعلامنا. سيتم إبلاغك بالطلبات القادمة."
        
        price = offer_data.get("price")
        if not price:
            return "يرجى تحديد السعر في عرضك.\n\nمثال:\nالسعر: 500 ريال\nملاحظات: متفرغ غداً"
        
        # 4. حفظ العرض
        save_result = await supabase_service.save_provider_offer(
            request_id=request_id,
            provider_id=provider_id,
            price=price,
            notes=offer_data.get("notes"),
            estimated_time=offer_data.get("estimated_time")
        )
        
        if not save_result.get("success"):
            print(f"❌ [ProviderResponse] Failed to save offer: {save_result.get('error')}")
            return "حدث خطأ أثناء حفظ العرض. يرجى المحاولة مرة أخرى."
        
        print(f"✅ [ProviderResponse] Offer saved: {price}")
        
        # 5. إشعار العميل
        offers_url = f"{APP_URL}/offers/{request_id}"
        
        # التحقق من عدد العروض
        request_with_offers = await supabase_service.get_request_with_offers(request_id)
        offers_count = len(request_with_offers.get("offers", [])) if request_with_offers else 1
        
        # إرسال إشعار للعميل
        customer_notification = f"""
🎉 *وصل عرض جديد!*

👤 *المزود:* {provider_name}
⭐ *التقييم:* {provider.get('rating', 'جديد')} ({provider.get('review_count', 0)} تقييم)
💰 *السعر:* {price}

📝 *ملاحظات:*
{offer_data.get('notes') or 'لا توجد ملاحظات'}

━━━━━━━━━━━━━━━

📊 *عدد العروض المستلمة:* {offers_count}

🔗 *شوف كل العروض:*
{offers_url}

💡 يمكنك قبول العرض أو انتظار عروض أخرى!
        """.strip()
        
        # إرسال الإشعار للعميل
        if customer_phone:
            twilio_service.send_whatsapp(
                to_number=f"whatsapp:+{customer_phone}",
                body=customer_notification
            )
            print(f"📤 [ProviderResponse] Customer notified: {customer_phone}")
        
        # رد للمزود
        return f"""
✅ *تم استلام عرضك بنجاح!*

💰 *السعر:* {price}
📝 *الملاحظات:* {offer_data.get('notes') or 'لا توجد'}

تم إرسال عرضك للعميل. سيتم إشعارك إذا تم قبول عرضك.

شكراً لاستخدامك هدهد! 🦦
        """.strip()
        
    except json.JSONDecodeError:
        return "عذراً، لم أفهم رسالتك. يرجى إرسال العرض بالتنسيق:\n\nالسعر: [مبلغك]\nملاحظات: [إن وجدت]"
    except Exception as e:
        print(f"❌ [ProviderResponse] Error: {e}")
        import traceback
        traceback.print_exc()
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
    
    # الحصول على سياق المستخدم من الذاكرة (إذا كانت متاحة)
    memory_context = await get_user_context(from_number, message_body)
    user_profile = memory_context.get("user_profile")
    
    # الحصول على اقتراح ذكي من بيانات التدريب
    smart_suggestion = await get_smart_suggestion(message_body)
    
    # إذا كان لدى المستخدم تاريخ، نضيفه للسياق
    memory_context_str = ""
    if user_profile:
        print(f"📋 [Memory] Found profile for {from_number}")
        memory_context_str = f"""
## 🧠 ذاكرة المستخدم:
- المدينة المفضلة: {user_profile.get('preferred_city', 'غير محددة')}
- الخدمات السابقة: {', '.join(user_profile.get('most_requested_services', []))}
- عدد الطلبات: {user_profile.get('request_count', 0)}
"""
    
    # إضافة الاقتراح الذكي إذا وُجد
    if smart_suggestion:
        print(f"💡 [Memory] Smart suggestion: {smart_suggestion.get('suggested_service')} in {smart_suggestion.get('suggested_city')}")
        memory_context_str += f"""
## 💡 اقتراح ذكي من الذاكرة:
- الخدمة المتوقعة: {smart_suggestion.get('suggested_service', 'غير محدد')}
- المدينة المتوقعة: {smart_suggestion.get('suggested_city', 'غير محددة')}
- النمط المطابق: "{smart_suggestion.get('matched_pattern', '')}"
- الثقة: {int(smart_suggestion.get('confidence', 0) * 100)}%

⚠️ استخدم هذا الاقتراح إذا كان منطقياً ويساعد في فهم الطلب بشكل أسرع.
"""
    
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
    # new و collecting نفس المرحلة (جمع المعلومات)
    if status in [ConversationState.NEW, ConversationState.COLLECTING]:
        # جاري جمع المعلومات
        messages = await supabase_service.get_messages(conversation_id)
        
        # استخراج المعلومات المحلية للسياق
        local_info = extract_info_locally(messages + [{"sender": "customer", "content": message_body}])
        
        # بناء سياق enrich
        context_enrichment = memory_context_str
        if local_info.get("service_type") or local_info.get("city"):
            context_enrichment += f"""
## 📋 المعلومات المستخرجة من المحادثة:
- نوع الخدمة: {local_info.get('service_type', 'غير محدد بعد')}
- المدينة: {local_info.get('city', 'غير محددة بعد')}
- الميزانية: {local_info.get('budget', 'غير محددة')}

⚠️ مهم: استخدم هذه المعلومات ولا تكرر سؤالها. إذا كانت مذكورة، لا تسأل عنها!
"""
        
        # بناء system prompt enriched
        enriched_prompt = RECEPTION_AGENT_PROMPT + context_enrichment
        
        # بناء السياق للـ AI
        chat_history = []
        for msg in messages:
            role = "user" if msg.get("sender") == "customer" or msg.get("direction") == "inbound" else "assistant"
            chat_history.append({"role": role, "content": msg["content"]})
        
        # إضافة الرسالة الحالية
        chat_history.append({"role": "user", "content": message_body})
        
        # إرسال للـ AI
        ai_response = await deepseek_service.chat(
            messages=chat_history,
            system_prompt=enriched_prompt
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
            
            # تسجيل التفاعل في الذاكرة
            asyncio.create_task(
                log_customer_request(
                    phone=from_number,
                    message=message_body,
                    service_type=request_info.get("service_type"),
                    city=request_info.get("city"),
                    ai_response=reply
                )
            )
            
            return reply
    
    elif status == ConversationState.CONFIRMING:
        # العميل يؤكد المعلومات
        if any(word in message_body.lower() for word in ["نعم", "صح", "صحيح", "أيوة", "تمام", "أكد", "ابدأ", "ابحث"]):
            # العميل أكد - ننتقل للبحث
            
            # ⚠️ التحقق من وجود طلب نشط أولاً
            can_create = await supabase_service.can_create_new_request(from_number)
            
            if not can_create.get("can_create"):
                # يوجد طلب نشط بالفعل
                active_request_id = can_create.get("active_request_id")
                expires_at = can_create.get("expires_at")
                offers_count = can_create.get("offers_count", 0)
                
                return f"""⚠️ *لديك طلب نشط بالفعل!*

📋 *رقم الطلب:* {active_request_id[:8] if active_request_id else 'غير متاح'}
📊 *عدد العروض:* {offers_count}
⏰ *ينتهي في:* {expires_at[:16] if expires_at else 'غير محدد'}

🔗 *صفحة العروض:*
{APP_URL}/offers/{active_request_id}

💡 يجب أن تنتهي صلاحية الطلب الحالي أو إغلاقه قبل إنشاء طلب جديد.
"""
            
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
        
        # التحقق من إلغاء الطلب
        cancel_keywords = ["الغاء", "إلغاء", "الغي", "إلغ", "كانسل", "لا أريد", "لا اريد", "مابي", "ما أبي"]
        is_cancel_request = any(keyword in message_body.lower() for keyword in cancel_keywords)
        
        if is_cancel_request:
            # إلغاء الطلب
            request_id = context.get("request_id")
            
            if request_id:
                cancel_result = await supabase_service.cancel_service_request(request_id, from_number)
                
                if cancel_result.get("success"):
                    # إعادة تعيين المحادثة
                    await supabase_service.update_conversation(
                        conversation_id=conversation_id,
                        status=ConversationState.NEW,
                        context={}
                    )
                    
                    # إذا كان الطلب منتهي الصلاحية
                    if cancel_result.get("already_expired"):
                        return f"""✅ *انتهت صلاحية الطلب*

📋 رقم الطلب: {request_id[:8]}...

💡 يمكنك الآن إنشاء طلب جديد.

كيف أقدر أساعدك؟ 🦦"""
                    
                    return f"""✅ *تم إلغاء الطلب بنجاح*

📋 رقم الطلب: {request_id[:8]}...

💡 يمكنك إنشاء طلب جديد في أي وقت.
شكراً لاستخدامك هدهد! 🦦"""
                else:
                    # حتى لو فشل الإلغاء، نعيد تعيين المحادثة إذا كان الطلب expired
                    # لكي يستطيع العميل إنشاء طلب جديد
                    return f"""⚠️ {cancel_result.get('error', 'حدث خطأ')}

💡 أرسل طلبك الجديد وسأعالجه لك.

مثال: "احتاج سباك في الرياض"
"""
            else:
                # لا يوجد طلب نشط، إعادة تعيين المحادثة
                await supabase_service.update_conversation(
                    conversation_id=conversation_id,
                    status=ConversationState.NEW,
                    context={}
                )
                return "✅ تم إلغاء الطلب. كيف أقدر أساعدك؟"
        
        # التحقق من طلب جديد
        # إذا كانت الرسالة تحتوي على كلمات طلب خدمة، نتحقق من صلاحية الطلب الحالي
        service_keywords = ["سباك", "كهرب", "تكييف", "تنظيف", "نقل", "صباغ", "نجار", "احتاج", "ابي", "مطلوب"]
        is_service_request = any(keyword in message_body.lower() for keyword in service_keywords)
        
        if is_service_request:
            # التحقق من صلاحية الطلب الحالي
            active_request = await supabase_service.get_active_request_for_customer(from_number)
            
            if not active_request:
                # الطلب الحالي منتهي أو غير موجود، يمكن إنشاء طلب جديد
                await supabase_service.update_conversation(
                    conversation_id=conversation_id,
                    status=ConversationState.COLLECTING,
                    context={}
                )
                # معالجة الرسالة الجديدة - استخراج المعلومات مباشرة
                local_info = extract_info_locally([{"sender": "customer", "content": message_body}])
                
                # بناء رد ذكي
                if local_info.get("service_type") and local_info.get("city"):
                    return f"""📝 *فهمت طلبك الجديد!*

🔧 الخدمة: {local_info.get('service_type')}
📍 المدينة: {local_info.get('city')}

هل المعلومات صحيحة؟ أجب بـ "نعم" للتأكيد أو أخبرني بالتعديل."""
                else:
                    service = local_info.get("service_type", "غير محدد")
                    city = local_info.get("city")
                    
                    city_line = f"📍 المدينة: {city}" if city else "📍 في أي مدينة تحتاج الخدمة؟"
                    help_line = "💡 أخبرني بالمدينة لأكمل طلبك" if not city else "هل هذه المعلومات صحيحة؟"
                    
                    return f"""📝 *طلب جديد*

🔧 الخدمة: {service if service != "غير محدد" else "لم أحددها بعد"}

{city_line}
{help_line}"""
            else:
                # يوجد طلب نشط
                offers_url = context.get("offer_page_url", f"{APP_URL}/offers/{active_request.get('id')}")
                return f"""⚠️ *لديك طلب نشط بالفعل!*

📋 رقم الطلب: {active_request.get('id', '')[:8]}...
📊 عدد العروض: {active_request.get('offers_count', 0)}

🔗 *صفحة العروض:*
{offers_url}

💡 إذا تريد إلغاء الطلب الحالي، أرسل: "إلغاء الطلب"
"""
        
        # رد افتراضي
        offers_url = context.get("offer_page_url", f"{APP_URL}/offers")
        return f"""⏳ *جاري انتظار العروض...*

🔗 *صفحة العروض:*
{offers_url}

📊 الصفحة تتحدث تلقائياً عند وصول عروض جديدة!

💡 إذا تريد إلغاء الطلب، أرسل: "إلغاء الطلب"
"""
    
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
        "version": "2.2.0"
    }


@app.get("/health")
async def health():
    """فحص صحة الخادم"""
    return {"status": "ok", "version": "2.2.0"}


# ============================================
# Notification Endpoint - للإشعارات من المنصة
# ============================================
@app.post("/api/notify-new-offer")
async def notify_new_offer(request: Request):
    """
    استقبال إشعار من المنصة عند تقديم عرض جديد
    يُستدعى من صفحة المزود (provider-offer)
    """
    try:
        body = await request.json()
        
        customer_phone = body.get("customer_phone")
        request_id = body.get("request_id")
        offer_id = body.get("offer_id")
        price = body.get("price")
        
        print(f"📩 [Notify] New offer notification:")
        print(f"   Request: {request_id}")
        print(f"   Customer: {customer_phone}")
        print(f"   Price: {price}")
        
        if not customer_phone or not request_id:
            return {"success": False, "error": "Missing required fields"}
        
        # الحصول على معلومات العرض والمزود
        offers = await supabase_service.get_offers_for_request(request_id)
        
        # العرض الجديد
        new_offer = None
        for offer in offers:
            if offer.get("id") == offer_id:
                new_offer = offer
                break
        
        if not new_offer:
            # نأخذ آخر عرض
            new_offer = offers[-1] if offers else None
        
        if new_offer:
            provider_info = new_offer.get("providers", {})
            provider_name = provider_info.get("business_name", "مزود") if provider_info else "مزود"
            provider_rating = provider_info.get("rating", "جديد") if provider_info else "جديد"
            
            # إرسال إشعار للعميل
            offers_url = f"{APP_URL}/offers/{request_id}"
            
            notification_message = f"""
🎉 *وصل عرض جديد!*

👤 *المزود:* {provider_name}
⭐ *التقييم:* {provider_rating}
💰 *السعر:* {price} ريال

━━━━━━━━━━━━━━━

📊 *عدد العروض المستلمة:* {len(offers)}

🔗 *شوف كل العروض:*
{offers_url}

💡 يمكنك قبول العرض أو انتظار عروض أخرى!
            """.strip()
            
            # إرسال الإشعار
            twilio_service.send_whatsapp(
                to_number=f"whatsapp:+{customer_phone}",
                body=notification_message
            )
            
            print(f"✅ [Notify] Customer notified: {customer_phone}")
            
            return {"success": True, "notified": True}
        
        return {"success": True, "notified": False, "reason": "Offer not found"}
        
    except Exception as e:
        print(f"❌ [Notify] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ============================================
# Cron Jobs - المهام الدورية
# ============================================
@app.post("/cron/expire-requests")
async def cron_expire_requests(request: Request):
    """
    تحديث الطلبات منتهية الصلاحية
    يستدعى كل 5 دقائق من Railway Cron
    """
    # التحقق من Authorization (optional security)
    auth_header = request.headers.get("Authorization", "")
    cron_secret = os.getenv("CRON_SECRET", "")
    
    if cron_secret and auth_header != f"Bearer {cron_secret}":
        return {"status": "unauthorized", "message": "Invalid secret"}
    
    try:
        # استدعاء function في Supabase
        result = await supabase_service.expire_old_requests()
        
        return {
            "status": "success",
            "message": "Expired old requests",
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/debug/requests")
async def debug_requests():
    """عرض حالة الطلبات"""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            # الحصول على إحصائيات الطلبات
            response = await client.get(
                f"{supabase_service.url}/rest/v1/service_requests?select=status,expires_at,created_at&order=created_at.desc&limit=20",
                headers=supabase_service.headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                requests = response.json()
                
                # حساب الإحصائيات
                stats = {}
                for req in requests:
                    status = req.get("status", "unknown")
                    stats[status] = stats.get(status, 0) + 1
                
                return {
                    "total": len(requests),
                    "stats": stats,
                    "recent": requests[:5]
                }
            else:
                return {"error": response.status_code}
                
    except Exception as e:
        return {"error": str(e)}


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
