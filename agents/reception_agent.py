"""
Reception Agent - وكيل الاستقبال البسيط
"""

import re
from typing import Dict, Any, Optional, List

# In-Memory Context Store
CONTEXT_STORE: Dict[str, Dict] = {}

# كلمات التأكيد
CONFIRM_WORDS = ["نعم", "صح", "صحيح", "تمام", "اكيد", "ابحث", "ابدأ", "تم", "آبحث", "أبحث", "أيوة"]

# المدن
KNOWN_CITIES = ["الرياض", "جدة", "مكة", "المدينة", "الدمام", "الخبر", "الطائف", "تبوك", "بريدة", "خميس مشيط", "الهفوف", "حائل", "نجران", "أبها", "جازان", "القصيم", "القطيف", "الأحساء"]

# الخدمات
SERVICE_KEYWORDS = {
    "سباكة": ["سباك", "سباكة", "تسريب", "مويه", "مياه", "حمام", "مطبخ"],
    "كهرباء": ["كهرب", "كهرباء", "تمديد", "أسلاك", "مفتاح", "فيش"],
    "تنظيف": ["تنظيف", "نظاف", "تعقيم", "غسيل", "سجاد", "موكيت"],
    "تكييف": ["تكييف", "مكيف", "تبريد", "فريون", "سبلت"],
    "نقل عفش": ["نقل", "عفش", "أثاث", "انتقال", "أغراض"],
    "صباغة": ["صباغ", "صباغة", "دهان", "طلاء", "لون"],
    "نجارة": ["نجار", "نجارة", "خشب", "أبواب", "مطابخ"]
}


class ReceptionAgent:
    
    def _normalize_phone(self, phone: str) -> str:
        return phone.replace(" ", "").replace("+", "").replace("whatsapp:", "")
    
    def _extract_info(self, message: str) -> Dict:
        """استخراج المعلومات من الرسالة"""
        data = {}
        print(f"🔍 [_extract_info] Analyzing: {message}")
        
        # استخراج الخدمة
        for service, keywords in SERVICE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message:
                    data["service_type"] = service
                    print(f"✅ [_extract_info] Found service: {service} (keyword: {keyword})")
                    break
            if data.get("service_type"):
                break
        
        # استخراج المدينة
        for city in KNOWN_CITIES:
            if city in message:
                data["city"] = city
                print(f"✅ [_extract_info] Found city: {city}")
                break
        
        print(f"📊 [_extract_info] Result: {data}")
        return data
    
    def _is_confirmed(self, message: str) -> bool:
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
        print(f"🤖 [Agent] Phone: {phone_key}, Message: {message}")
        
        # استرجاع أو إنشاء سياق
        context = CONTEXT_STORE.get(phone_key, {"extracted_data": {}, "stage": "collecting"})
        extracted_data = context.get("extracted_data", {})
        print(f"📋 [Agent] Current data: {extracted_data}")
        
        # التحقق من التأكيد
        if self._is_confirmed(message):
            if extracted_data.get("service_type") and extracted_data.get("city"):
                print("✅ [Agent] Confirmed with complete data!")
                
                # مسح السياق
                if phone_key in CONTEXT_STORE:
                    del CONTEXT_STORE[phone_key]
                
                return {
                    "reply": f"""✅ *تم استلام طلبك!*

📋 *الخدمة:* {extracted_data.get('service_type')}
📍 *المدينة:* {extracted_data.get('city')}
{f"📝 *التفاصيل:* {extracted_data.get('details')}" if extracted_data.get('details') else ''}

🔍 جاري البحث عن أفضل المزودين...

سيصلك رابط صفحة العروض قريباً! 📬""",
                    "extracted_data": extracted_data,
                    "ready_for_matching": True
                }
        
        # استخراج معلومات جديدة
        new_data = self._extract_info(message)
        print(f"📊 [Agent] Extracted: {new_data}")
        
        # دمج
        merged = {**extracted_data, **new_data}
        print(f"🔄 [Agent] Merged: {merged}")
        
        # حفظ
        CONTEXT_STORE[phone_key] = {"extracted_data": merged}
        
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
