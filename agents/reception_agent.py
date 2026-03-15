"""
Reception Agent - وكيل الاستقبال
مع In-Memory Context للتجربة السريعة
"""

import re
from typing import Dict, Any, Optional, List
from services.deepseek_service import deepseek_service
from services.supabase_service import supabase_service
from services.twilio_service import twilio_service
from config import APP_URL


# In-Memory Context Store
CONTEXT_STORE: Dict[str, Dict] = {}


# كلمات التأكيد
CONFIRM_WORDS = ["نعم", "صح", "صحيح", "تمام", "اكيد", "ابحث", "ابدأ", "تم", "آبحث", "أبحث", "نعم صح", "نعم صحيح", "أيوة"]

# المدن
KNOWN_CITIES = ["الرياض", "جدة", "مكة", "المدينة", "الدمام", "الخبر", "الطائف", "تبوك", "بريدة", "خميس مشيط", "الهفوف", "حائل", "نجران", "أبها", "جازان"]

# الخدمات  
KNOWN_SERVICES = ["سباك", "سباكة", "كهرباء", "كهربائي", "تنظيف", "نظافة", "تكييف", "مكيفات", "نقل", "عفش", "أثاث", "صباغ", "صباغة", "نجار", "نجارة"]


class ReceptionAgent:
    def __init__(self):
        pass
    
    def _normalize_phone(self, phone: str) -> str:
        """تطبيع رقم الهاتف"""
        return phone.replace(" ", "").replace("+", "").replace("whatsapp:", "")
    
    def _extract_from_message(self, message: str) -> Dict:
        """استخراج المعلومات من الرسالة"""
        data = {}
        msg_lower = message.lower()
        
        # الخدمة
        for s in KNOWN_SERVICES:
            if s in msg_lower:
                if "سباك" in s:
                    data["service_type"] = "سباكة"
                elif "كهرب" in s:
                    data["service_type"] = "كهرباء"
                elif "نظاف" in s or "تنظيف" in s:
                    data["service_type"] = "تنظيف"
                elif "تكييف" in s or "مكيف" in s:
                    data["service_type"] = "تكييف"
                elif "نقل" in s or "عفش" in s:
                    data["service_type"] = "نقل عفش"
                elif "صباغ" in s:
                    data["service_type"] = "صباغة"
                elif "نجار" in s:
                    data["service_type"] = "نجارة"
                break
        
        # المدينة
        for city in KNOWN_CITIES:
            if city in message:
                data["city"] = city
                break
        
        # التفاصيل
        if "تسريب" in msg_lower or "تسرب" in msg_lower:
            data["details"] = "تسريب مياه"
        elif "عطل" in msg_lower:
            data["details"] = "عطل"
        
        # الميزانية
        budget_match = re.search(r'(\d+)\s*(ريال|ر\.س)', msg_lower)
        if budget_match:
            data["budget"] = f"{budget_match.group(1)} ريال"
        
        return data
    
    def _is_confirming(self, message: str) -> bool:
        """التحقق من التأكيد"""
        return any(w in message for w in CONFIRM_WORDS)
    
    async def process_message(
        self,
        customer_phone: str,
        message: str,
        conversation_id: str,
        conversation_history: List[Dict],
        current_context: Dict = None
    ) -> Dict[str, Any]:
        """معالجة الرسالة"""
        
        phone_key = self._normalize_phone(customer_phone)
        print(f"🤖 [Agent] Phone key: {phone_key}")
        
        # استرجاع السياق من الذاكرة
        if phone_key in CONTEXT_STORE:
            context = CONTEXT_STORE[phone_key]
            print(f"📋 [Agent] Found context: {context}")
        else:
            context = {"extracted_data": {}, "stage": "collecting"}
            print(f"🆕 [Agent] New context")
        
        extracted_data = context.get("extracted_data", {})
        
        # التحقق من التأكيد
        if self._is_confirming(message):
            if extracted_data.get("service_type") and extracted_data.get("city"):
                print("✅ [Agent] Confirmed! Starting search...")
                
                # إنشاء طلب
                request_result = await supabase_service.create_service_request(
                    conversation_id=conversation_id,
                    customer_phone=customer_phone,
                    service_type=extracted_data.get("service_type"),
                    city=extracted_data.get("city"),
                    details=extracted_data.get("details"),
                    budget=extracted_data.get("budget")
                )
                
                if request_result.get("success"):
                    request_id = request_result.get("request_id")
                    slug = request_result.get("slug")
                    offer_url = f"{APP_URL}/offers/{slug}"
                    
                    # مسح السياق
                    if phone_key in CONTEXT_STORE:
                        del CONTEXT_STORE[phone_key]
                    
                    reply = f"""✅ *تم استلام طلبك!*

📋 *الخدمة:* {extracted_data.get('service_type')}
📍 *المدينة:* {extracted_data.get('city')}
📝 *التفاصيل:* {extracted_data.get('details', 'غير محددة')}

🔍 جاري البحث عن أفضل المزودين...

🔗 *صفحة العروض:*
{offer_url}

⏰ صلاحية الصفحة: ساعتين"""
                    
                    return {
                        "reply": reply,
                        "extracted_data": extracted_data,
                        "ready_for_matching": True,
                        "request_id": request_id
                    }
        
        # استخراج معلومات جديدة
        new_data = self._extract_from_message(message)
        print(f"📊 [Agent] Extracted: {new_data}")
        
        # دمج
        merged = {**extracted_data, **new_data}
        print(f"🔄 [Agent] Merged: {merged}")
        
        # حفظ في الذاكرة
        CONTEXT_STORE[phone_key] = {"extracted_data": merged, "stage": "collecting"}
        
        # توليد الرد
        if merged.get("service_type") and merged.get("city"):
            reply = f"""تمام! ✅

- 🔧 الخدمة: {merged['service_type']}
- 📍 المدينة: {merged['city']}
{f"- 📝 التفاصيل: {merged['details']}" if merged.get('details') else ''}

صحيح؟ أكد عشان أبحث لك! 👍"""
        elif merged.get("service_type"):
            reply = f"أهلاً! 🙋‍♂️ {merged['service_type']} - فهمت!\n\n📍 في أي مدينة؟"
        elif merged.get("city"):
            reply = f"أهلاً! 🙋‍♂️\n\nأنت في {merged['city']}.\n\n🔧 وش نوع الخدمة؟"
        else:
            reply = "أهلاً! 🙋‍♂️\n\nكيف أقدر أساعدك؟ أخبرني بنوع الخدمة والمدينة."
        
        return {
            "reply": reply,
            "extracted_data": merged,
            "ready_for_matching": False
        }


reception_agent = ReceptionAgent()
