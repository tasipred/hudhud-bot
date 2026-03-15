"""
Reception Agent - وكيل الاستقبال
الوكيل الأول - يستقبل طلبات العملاء ويفهمها
"""

from typing import Dict, Any, Optional, List
from services.deepseek_service import deepseek_service
from services.supabase_service import supabase_service
from services.twilio_service import twilio_service
from config import APP_URL


class ReceptionAgent:
    """
    وكيل الاستقبال - الوكيل الأول في النظام
    """
    
    def __init__(self):
        # تخزين مؤقت للبيانات المستخرجة خلال المحادثة
        self.session_data: Dict[str, Dict] = {}
    
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
        print(f"🤖 [ReceptionAgent] Processing: {message[:50]}...")
        
        # استخراج البيانات من السياق السابق
        previous_data = {}
        if current_context and current_context.get("extracted_data"):
            previous_data = current_context["extracted_data"]
            print(f"📋 [ReceptionAgent] Previous data: {previous_data}")
        
        # بناء ملخص المعلومات المعروفة
        known_info = self._format_known_info(previous_data)
        
        # System Prompt محسّن
        system_prompt = self._build_system_prompt(known_info)
        
        # بناء تاريخ المحادثة
        chat_history = []
        for msg in conversation_history:
            role = "user" if msg["sender"] == "customer" else "assistant"
            chat_history.append({"role": role, "content": msg["content"]})
        
        # إضافة الرسالة الحالية
        chat_history.append({"role": "user", "content": message})
        
        # إرسال للـ AI
        ai_response = await deepseek_service.chat(
            messages=chat_history,
            system_prompt=system_prompt
        )
        
        if not ai_response["success"]:
            return {
                "reply": "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى.",
                "extracted_data": previous_data,
                "ready_for_matching": False
            }
        
        reply = ai_response["content"]
        
        # استخراج البيانات من المحادثة كاملة
        new_data = await self._extract_all_data(chat_history)
        
        # دمج البيانات - البيانات الجديدة تسبق
        merged_data = {**previous_data, **{k: v for k, v in new_data.items() if v}}
        print(f"📊 [ReceptionAgent] Merged data: {merged_data}")
        
        # التحقق من التأكيد
        confirmation_words = ["نعم", "صح", "صحيح", "تمام", "أيوة", "اكيد", "ابحث", "ابدأ", "سوي", "تم", "نعم صح", "نعم صحيح", "أبحث"]
        is_confirmed = any(word in message for word in confirmation_words)
        
        ready_for_matching = False
        request_id = None
        
        # التحقق من اكتمال البيانات والتأكيد
        if is_confirmed and merged_data.get("service_type") and merged_data.get("city"):
            ready_for_matching = True
            
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
    
    def _build_system_prompt(self, known_info: str) -> str:
        """بناء System Prompt مع المعلومات المعروفة"""
        return f"""أنت وكيل الاستقبال في منصة "هدهد" للخدمات.

## المعلومات المعروفة مسبقاً:
{known_info if known_info else "لا توجد معلومات بعد."}

## قواعد مهمة جداً:
1. **لا تسأل عن معلومة معروفة مسبقاً** - إذا العميل قال "الرياض" لا تسأل عن المدينة مرة أخرى
2. **تابع المحادثة بشكل طبيعي** - ركز على المعلومات الناقصة فقط
3. **إذا العميل أكد (نعم/صح/صحيح/تمام/ابحث)** - قل "تمام! جاري البحث..." ولاتسأل شي آخر
4. **كن مختصراً** - لا تطيل الرد
5. **تحدث بالعربية الفصحى البسيطة**

## المعلومات المطلوبة:
- نوع الخدمة (سباكة، كهرباء، تنظيف...)
- المدينة
- تفاصيل المشكلة (اختياري)
- الميزانية (اختياري)

## أمثلة:
- إذا العميل قال "أبي سباك في الرياض" → لا تسأل عن المدينة! اسأل عن المشكلة فقط
- إذا العميل قال "نعم صحيح" → قل "تمام! جاري البحث..."
- إذا العميل أعطاك تفاصيل إضافية → أكد المعلومات واطلب التأكيد"""

    def _format_known_info(self, data: Dict) -> str:
        """تنسيق المعلومات المعروفة"""
        if not data:
            return ""
        
        parts = []
        if data.get("service_type"):
            parts.append(f"🔧 الخدمة: {data['service_type']}")
        if data.get("city"):
            parts.append(f"📍 المدينة: {data['city']}")
        if data.get("details"):
            parts.append(f"📝 التفاصيل: {data['details']}")
        if data.get("budget"):
            parts.append(f"💰 الميزانية: {data['budget']}")
        
        return "\n".join(parts)
    
    async def _extract_all_data(self, chat_history: List[Dict]) -> Dict:
        """استخراج جميع البيانات من المحادثة"""
        
        extraction_prompt = """من المحادثة التالية، استخرج جميع المعلومات المتوفرة:

{
    "service_type": "نوع الخدمة أو null",
    "city": "المدينة أو null",
    "details": "التفاصيل أو null", 
    "budget": "الميزانية أو null"
}

قواعد:
- استخرج من كل الرسائل، ليس فقط الأخيرة
- إذا ذُكرت معلومة في أي رسالة، احفظها
- أعد JSON فقط"""

        conversation_text = "\n".join([
            f"{'عميل' if msg['role'] == 'user' else 'بوت'}: {msg['content']}"
            for msg in chat_history
        ])
        
        result = await deepseek_service.extract_structured_data(
            user_message=conversation_text,
            fields=["service_type", "city", "details", "budget"],
            system_prompt=extraction_prompt
        )
        
        if result.get("success") and result.get("data"):
            return result["data"]
        
        return {}
    
    async def send_welcome(self, customer_phone: str) -> Dict[str, Any]:
        """إرسال رسالة الترحيب"""
        return twilio_service.send_welcome(customer_phone)


# إنشاء instance واحد
reception_agent = ReceptionAgent()
