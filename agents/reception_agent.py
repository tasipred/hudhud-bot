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
    
    # System Prompt للوكيل
    SYSTEM_PROMPT = """
أنت وكيل الاستقبال في منصة "هدهد" للخدمات.
دورك: فهم طلب العميل واستخراج المعلومات المطلوبة.

## مهمتك:
1. رحب بالعميل بأسلوب ودية ومختصر
2. افهم نوع الخدمة المطلوبة
3. استخرج المعلومات التالية:
   - نوع الخدمة (سباكة، كهرباء، تنظيف، نقل، إلخ)
   - المدينة/المنطقة
   - تفاصيل إضافية (المشكلة، المساحة، الموعد)
   - الميزانية (إن وجدت)

## قواعد:
- تحدث بالعربية الفصحى البسيطة
- كن مختصراً ومباشراً
- إذا نقصت معلومة، اسأل عنها بلطف
- بعد جمع المعلومات، أكدها مع العميل قبل المتابعة
- استخدم الإيموجي بشكل معتدل

## مثال:
العميل: "أبي سباك"
الرد: "أهلاً وسهلاً! 🙋‍♂️

أنت تحتاج سباك. عشان أساعدك أفضل:
- في أي مدينة؟
- وش المشكلة بالضبط؟"

العميل: "الرياض، تسريب مويه"
الرد: "تمام! خلصت المعلومات:
- 🔧 الخدمة: سباكة
- 📍 المدينة: الرياض  
- 📝 المشكلة: تسريب مياه

صحيح؟ وإذا عندك ميزانية معينة ذكرها."
"""

    # Prompt لاستخراج البيانات المنظمة
    EXTRACTION_PROMPT = """
أنت مساعد ذكي لاستخراج البيانات المنظمة.

من رسالة العميل، استخرج المعلومات التالية وأعدها بتنسيق JSON فقط:

{
    "service_type": "نوع الخدمة أو null",
    "city": "المدينة أو null", 
    "details": "التفاصيل أو null",
    "budget": "الميزانية أو null",
    "is_confirmed": true/false (هل العميل أكد المعلومات؟)
}

قواعد:
- إذا لم تجد معلومة، ضع null
- أعد JSON فقط بدون أي نص إضافي
- is_confirmed = true فقط إذا العميل قال "نعم" أو "صح" أو "صحيح" أو ما يشبه التأكيد
"""
    
    def __init__(self):
        self.conversation_context: Dict[str, Any] = {}
    
    async def process_message(
        self,
        customer_phone: str,
        message: str,
        conversation_id: str,
        conversation_history: List[Dict]
    ) -> Dict[str, Any]:
        """
        معالجة رسالة العميل
        
        Args:
            customer_phone: رقم هاتف العميل
            message: نص الرسالة
            conversation_id: معرف المحادثة
            conversation_history: تاريخ المحادثة
        
        Returns:
            {
                "reply": str,
                "extracted_data": dict,
                "ready_for_matching": bool,
                "request_id": str (if created)
            }
        """
        print(f"🤖 [ReceptionAgent] Processing: {message[:50]}...")
        
        # بناء تاريخ المحادثة للسياق
        chat_history = []
        for msg in conversation_history:
            role = "user" if msg["sender"] == "customer" else "assistant"
            chat_history.append({"role": role, "content": msg["content"]})
        
        # إضافة الرسالة الحالية
        chat_history.append({"role": "user", "content": message})
        
        # إرسال للـ AI للفهم والرد
        ai_response = await deepseek_service.chat(
            messages=chat_history,
            system_prompt=self.SYSTEM_PROMPT
        )
        
        if not ai_response["success"]:
            return {
                "reply": "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى.",
                "extracted_data": None,
                "ready_for_matching": False
            }
        
        reply = ai_response["content"]
        
        # استخراج البيانات المنظمة
        extracted_data = await self._extract_data(message, chat_history)
        
        # التحقق إذا كان العميل أكد المعلومات
        ready_for_matching = False
        request_id = None
        
        if extracted_data and extracted_data.get("is_confirmed"):
            # العميل أكد - نحتاج نتحقق من اكتمال البيانات
            if self._is_data_complete(extracted_data):
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
        chat_history: List[Dict]
    ) -> Optional[Dict]:
        """
        استخراج البيانات المنظمة من المحادثة
        """
        # بناء ملخص المحادثة للاستخراج
        conversation_text = "\n".join([
            f"{'عميل' if msg['role'] == 'user' else 'بوت'}: {msg['content']}"
            for msg in chat_history
        ])
        
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
