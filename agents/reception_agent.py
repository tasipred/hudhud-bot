"""
Reception Agent - وكيل الاستقبال
الوكيل الأول - يستقبل طلبات العملاء ويفهمها
"""

import re
from typing import Dict, Any, Optional, List
from services.deepseek_service import deepseek_service
from services.supabase_service import supabase_service
from services.twilio_service import twilio_service
from config import APP_URL


# قائمة الخدمات المعروفة
KNOWN_SERVICES = [
    "سباك", "سباكة", "كهرباء", "كهربائي", "تنظيف", "نظافة",
    "تكييف", "مكيفات", "نقل", "نقل عفش", "أثاث", "صباغ", "صباغة",
    "نجار", "نجارة", "حداد", "حدادة", "تسليك", "صيانة",
    "تمديد", "تركيب", "إصلاح", "تصليح", "مبلط", "بلاط"
]

# قائمة المدن السعودية
KNOWN_CITIES = [
    "الرياض", "جدة", "مكة", "المدينة", "الدمام", "الخبر",
    "الظهران", "الطائف", "تبوك", "بريدة", "خميس مشيط",
    "الهفوف", "المبرز", "حفر الباطن", "حائل", "نجران",
    "الجبيل", "ينبع", "الخفجي", "عنيزة", "الرس", "القصيم",
    "جازان", "أبها", "القطيف", "الأحساء", "الخرج", "الدرعية"
]


class ReceptionAgent:
    """
    وكيل الاستقبال - الوكيل الأول في النظام
    """
    
    def __init__(self):
        pass
    
    async def process_message(
        self,
        customer_phone: str,
        message: str,
        conversation_id: str,
        conversation_history: List[Dict],
        current_context: Dict = None
    ) -> Dict[str, Any]:
        """
        معالجة رسالة العميل
        """
        print(f"🤖 [ReceptionAgent] Processing: {message}")
        
        # استخراج البيانات من السياق السابق
        previous_data = {}
        if current_context and current_context.get("extracted_data"):
            previous_data = current_context["extracted_data"]
            print(f"📋 [ReceptionAgent] Previous data: {previous_data}")
        
        # استخراج البيانات من الرسالة الجديدة (بطريقة بسيطة)
        new_data = self._simple_extract(message)
        print(f"📊 [ReceptionAgent] New extracted data: {new_data}")
        
        # دمج البيانات
        merged_data = {**previous_data, **new_data}
        print(f"🔄 [ReceptionAgent] Merged data: {merged_data}")
        
        # بناء الرد
        reply, ready_for_matching = self._generate_reply(message, merged_data)
        
        request_id = None
        
        # إذا جاهز للمطابقة
        if ready_for_matching:
            # إنشاء طلب خدمة
            request_result = await supabase_service.create_service_request(
                conversation_id=conversation_id,
                customer_phone=customer_phone,
                service_type=merged_data.get("service_type"),
                city=merged_data.get("city"),
                details=merged_data.get("details"),
                budget=merged_data.get("budget")
            )
            
            if request_result.get("success"):
                request_id = request_result.get("request_id")
                slug = request_result.get("slug")
                
                offer_url = f"{APP_URL}/offers/{slug}"
                reply = f"""✅ *تم استلام طلبك!*

📋 *الخدمة:* {merged_data.get('service_type')}
📍 *المدينة:* {merged_data.get('city')}
📝 *التفاصيل:* {merged_data.get('details', 'غير محددة')}

🔍 جاري البحث عن أفضل المزودين...

🔗 *صفحة العروض:*
{offer_url}

⏰ صلاحية الصفحة: ساعتين

سيصلك تنبيه عند وصول عروض جديدة! 📬"""
        
        return {
            "reply": reply,
            "extracted_data": merged_data,
            "ready_for_matching": ready_for_matching,
            "request_id": request_id
        }
    
    def _simple_extract(self, message: str) -> Dict:
        """
        استخراج بسيط بدون AI
        """
        data = {}
        msg_lower = message.lower()
        
        # استخراج الخدمة
        for service in KNOWN_SERVICES:
            if service in msg_lower:
                # تحويل لاسم الخدمة الأساسي
                if "سباك" in service:
                    data["service_type"] = "سباكة"
                elif "كهرب" in service:
                    data["service_type"] = "كهرباء"
                elif "نظاف" in service or "تنظيف" in service:
                    data["service_type"] = "تنظيف"
                elif "تكييف" in service or "مكيف" in service:
                    data["service_type"] = "تكييف"
                elif "نقل" in service:
                    data["service_type"] = "نقل عفش"
                elif "صباغ" in service:
                    data["service_type"] = "صباغة"
                elif "نجار" in service:
                    data["service_type"] = "نجارة"
                else:
                    data["service_type"] = service
                break
        
        # استخراج المدينة
        for city in KNOWN_CITIES:
            if city in message:
                data["city"] = city
                break
        
        # استخراج التفاصيل (كلمات مفتاحية للمشاكل)
        details_keywords = ["تسريب", "تسرب", "عطل", "خلل", "مشكلة", "انهيار", "انفجار", "ضرر", "تركيب", "صيانة"]
        for keyword in details_keywords:
            if keyword in msg_lower:
                # استخراج الجملة المحيطة
                if "تسريب" in msg_lower or "تسرب" in msg_lower:
                    data["details"] = "تسريب مياه"
                elif "عطل" in msg_lower:
                    data["details"] = "عطل"
                elif "تركيب" in msg_lower:
                    data["details"] = "تركيب"
                elif "صيانة" in msg_lower:
                    data["details"] = "صيانة"
                break
        
        # استخراج الميزانية
        budget_match = re.search(r'(\d+)\s*(ريال|ر\.س|رIAL)', msg_lower)
        if budget_match:
            data["budget"] = f"{budget_match.group(1)} ريال"
        
        return data
    
    def _generate_reply(self, message: str, data: Dict) -> tuple:
        """
        توليد الرد بناءً على البيانات المتوفرة
        """
        msg_lower = message.lower()
        
        # كلمات التأكيد
        confirm_words = ["نعم", "صح", "صحيح", "تمام", "اكيد", "ابحث", "ابدأ", "تم", "آبحث"]
        is_confirming = any(word in msg_lower for word in confirm_words)
        
        # إذا أكد والبيانات كاملة
        if is_confirming and data.get("service_type") and data.get("city"):
            return "", True  # Ready for matching
        
        # بناء الرد
        parts = []
        
        # إذا عندنا خدمة ومدينة
        if data.get("service_type") and data.get("city"):
            parts.append(f"تمام! ✅")
            parts.append(f"- 🔧 الخدمة: {data['service_type']}")
            parts.append(f"- 📍 المدينة: {data['city']}")
            if data.get("details"):
                parts.append(f"- 📝 التفاصيل: {data['details']}")
            parts.append("")
            parts.append("صحيح؟ إذا تبي أبحث لك اكتب 'نعم' 👍")
            return "\n".join(parts), False
        
        # إذا عندنا خدمة فقط
        if data.get("service_type") and not data.get("city"):
            return f"أهلاً! 🙋‍♂️ فهمت تحتاج {data['service_type']}.\n\n📍 في أي مدينة أنت؟", False
        
        # إذا عندنا مدينة فقط
        if data.get("city") and not data.get("service_type"):
            return f"أهلاً! 🙋‍♂️\n\nأنت في {data['city']}.\n\n🔧 وش نوع الخدمة اللي تحتاجها؟", False
        
        # لا توجد معلومات
        return "أهلاً! 🙋‍♂️\n\nكيف أقدر أساعدك؟ قولي نوع الخدمة والمدينة.", False
    
    async def send_welcome(self, customer_phone: str) -> Dict[str, Any]:
        """إرسال رسالة الترحيب"""
        return twilio_service.send_welcome(customer_phone)


# إنشاء instance واحد
reception_agent = ReceptionAgent()
