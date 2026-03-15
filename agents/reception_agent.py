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
    
    المسؤوليات:
    1. ترحيب العميل
    2. فهم نوع الخدمة المطلوبة
    3. استخراج المعلومات (خدمة، مدينة، تفاصيل، ميزانية)
    4. تأكيد المعلومات مع العميل
    5. إنشاء طلب خدمة وصفحة عروض
    """
    
    # System Prompt للوكيل - محسّن للحفاظ على السياق
    SYSTEM_PROMPT = """
أنت وكيل الاستقبال في منصة "هدهد" للخدمات.
دورك: فهم طلب العميل واستخراج المعلومات المطلوبة.

## مهمتك:
1. تابع المحادثة مع العميل بشكل طبيعي
2. استخرج المعلومات التالية تدريجياً:
   - نوع الخدمة (سباكة، كهرباء، تنظيف، نقل، إلخ)
   - المدينة/المنطقة
   - تفاصيل إضافية (المشكلة، المساحة، الموعد)
   - الميزانية (إن وجدت)

## قواعد مهمة جداً:
- تذكر كل ما قاله العميل في المحادثة
- لا تسأل عن معلومة سبق وذكرها العميل
- إذا العميل أكد المعلومات (قال: نعم/صح/صحيح/تمام)، قل: "تمام! جاري البحث..."
- كن مختصراً ومباشراً
- تحدث بالعربية الفصحى البسيطة
- استخدم الإيموجي بشكل معتدل

## أمثلة:
العميل: "أبي سباك في الرياض"
الرد: "أهلاً! 🙋‍♂️ سباك في الرياض - فهمت!
وش المشكلة بالضبط؟ (تسريب، تركيب، صيانة؟)"

العميل: "في تسريب مويه في الحمام"
الرد: "تمام! ✅
- 🔧 الخدمة: سباكة
- 📍 المدينة: الرياض  
- 📝 المشكلة: تسريب مياه في الحمام

صحيح؟ وإذا عندك ميزانية معينة ذكرها."

العميل: "نعم صحيح ابحث لي"
الرد: "تمام! 🔍 جاري البحث عن أفضل السباكين في الرياض..."
"""

    # Prompt لاستخراج البيانات المنظمة - محسّن
    EXTRACTION_PROMPT = """
أنت مساعد ذكي لاستخراج البيانات من محادثة.

من المحادثة كاملة، استخرج المعلومات وأعدها بتنسيق JSON فقط:

{
    "service_type": "نوع الخدمة (من المحادثة) أو null",
    "city": "المدينة (من المحادثة) أو null", 
    "details": "التفاصيل (من المحادثة) أو null",
    "budget": "الميزانية (من المحادثة) أو null",
    "is_confirmed": true/false
}

قواعد مهمة:
- اجمع المعلومات من كل المحادثة، ليس فقط آخر رسالة
- إذا العميل قال "نعم" أو "صح" أو "صحيح" أو "تمام" أو "أكد" أو "ابحث" → is_confirmed = true
- أعد JSON فقط بدون أي نص إضافي
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
        
        Args:
            customer_phone: رقم هاتف العميل
            message: نص الرسالة
            conversation_id: معرف المحادثة
            conversation_history: تاريخ المحادثة
            current_context: السياق الحالي (البيانات المستخرجة سابقاً)
        
        Returns:
            {
                "reply": str,
                "extracted_data": dict,
                "ready_for_matching": bool,
                "request_id": str (if created)
            }
        """
        print(f"🤖 [ReceptionAgent] Processing: {message[:50]}...")
        print(f"📋 [ReceptionAgent] History length: {len(conversation_history)}")
        
        # بناء تاريخ المحادثة للسياق
        chat_history = []
        for msg in conversation_history:
            role = "user" if msg["sender"] == "customer" else "assistant"
            chat_history.append({"role": role, "content": msg["content"]})
        
        # إضافة الرسالة الحالية
        chat_history.append({"role": "user", "content": message})
        
        # استخراج البيانات من المحادثة كاملة
        extracted_data = await self._extract_data(message, chat_history, current_context)
        
        # دمج البيانات المستخرجة مع السياق السابق
        if current_context and current_context.get("extracted_data"):
            previous_data = current_context["extracted_data"]
            # دمج البيانات - البيانات الجديدة تسبق
            merged_data = {**previous_data, **{k: v for k, v in extracted_data.items() if v is not None}}
            extracted_data = merged_data
        
        print(f"📊 [ReceptionAgent] Extracted data: {extracted_data}")
        
        # إرسال للـ AI للفهم والرد
        ai_response = await deepseek_service.chat(
            messages=chat_history,
            system_prompt=self.SYSTEM_PROMPT
        )
        
        if not ai_response["success"]:
            return {
                "reply": "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى.",
                "extracted_data": extracted_data,
                "ready_for_matching": False
            }
        
        reply = ai_response["content"]
        
        # التحقق إذا كان العميل أكد المعلومات
        ready_for_matching = False
        request_id = None
        
        # التحقق من التأكيد
        confirmation_words = ["نعم", "صح", "صحيح", "تمام", "أيوة", "اكيد", "ابحث", "آبحث", "ابدأ", "سوي", "نعم صح", "نعم صحيح"]
        is_confirmed = any(word in message.lower() for word in confirmation_words)
        
        if is_confirmed and self._is_data_complete(extracted_data):
            ready_for_matching = True
            
            # إنشاء طلب خدمة
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
                
                # إرسال رسالة التأكيد مع رابط الصفحة
                offer_url = f"{APP_URL}/offers/{slug}"
                confirmation_msg = f"""
✅ *تم استلام طلبك!*

📋 *الخدمة:* {extracted_data.get('service_type')}
📍 *المدينة:* {extracted_data.get('city')}
📝 *التفاصيل:* {extracted_data.get('details', 'غير محددة')}

🔍 جاري البحث عن أفضل المزودين...

🔗 *صفحة العروض:*
{offer_url}

⏰ صلاحية الصفحة: ساعتين

سيصلك تنبيه عند وصول عروض جديدة! 📬
                """.strip()
                
                reply = confirmation_msg
        
        return {
            "reply": reply,
            "extracted_data": extracted_data,
            "ready_for_matching": ready_for_matching,
            "request_id": request_id
        }
    
    async def _extract_data(
        self,
        message: str,
        chat_history: List[Dict],
        current_context: Dict = None
    ) -> Optional[Dict]:
        """
        استخراج البيانات المنظمة من المحادثة كاملة
        """
        # بناء ملخص المحادثة للاستخراج
        conversation_text = "\n".join([
            f"{'عميل' if msg['role'] == 'user' else 'بوت'}: {msg['content']}"
            for msg in chat_history
        ])
        
        # إضافة السياق السابق إن وجد
        if current_context and current_context.get("extracted_data"):
            context_info = f"\n[البيانات المعروفة مسبقاً: {current_context['extracted_data']}]"
            conversation_text += context_info
        
        result = await deepseek_service.extract_structured_data(
            user_message=conversation_text,
            fields=["service_type", "city", "details", "budget", "is_confirmed"],
            system_prompt=self.EXTRACTION_PROMPT
        )
        
        if result.get("success"):
            return result.get("data")
        
        return None
    
    def _is_data_complete(self, data: Dict) -> bool:
        """
        التحقق من اكتمال البيانات الأساسية
        """
        return (
            data.get("service_type") is not None and
            data.get("city") is not None
        )
    
    async def send_welcome(self, customer_phone: str) -> Dict[str, Any]:
        """
        إرسال رسالة الترحيب للعميل الجديد
        """
        return twilio_service.send_welcome(customer_phone)


# إنشاء instance واحد
reception_agent = ReceptionAgent()
