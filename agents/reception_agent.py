"""
Reception Agent - وكيل الاستقبال المحترف
يبني على منهجية Entity Extraction + Structured Output
"""

import json
import re
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from services.deepseek_service import deepseek_service
from services.supabase_service import supabase_service
from services.twilio_service import twilio_service
from config import APP_URL


# ============================================
# Pydantic Models للبيانات المنظمة
# ============================================

class ExtractedEntities(BaseModel):
    """الكيانات المستخرجة من رسالة العميل"""
    service_type: Optional[str] = Field(None, description="نوع الخدمة")
    city: Optional[str] = Field(None, description="المدينة")
    neighborhood: Optional[str] = Field(None, description="اسم الحي")
    details: Optional[str] = Field(None, description="تفاصيل المشكلة")
    urgency: Optional[str] = Field(None, description="مستوى الاستعجال")
    time_slot: Optional[str] = Field(None, description="الوقت المفضل")
    budget: Optional[str] = Field(None, description="الميزانية")


# ============================================
# System Prompt للاستخراج
# ============================================

EXTRACTION_SYSTEM_PROMPT = """أنت محرك استخراج معلومات. من رسالة العميل، استخرج المعلومات المتوفرة فقط.

أعد النتيجة بتنسيق JSON فقط (بدون أي نص إضافي):
{
    "service_type": "نوع الخدمة أو null",
    "city": "المدينة أو null",
    "neighborhood": "الحي أو null",
    "details": "تفاصيل المشكلة أو null",
    "urgency": "عاجل/اليوم/غداً أو null",
    "budget": "الميزانية أو null"
}

ملاحظات:
- استخرج فقط المعلومات المذكورة صراحة
- إذا لم توجد معلومة، ضع null
- لا تخترع معلومات غير موجودة

أمثلة:
"أبي سباك في الرياض" → {"service_type": "سباكة", "city": "الرياض", ...}
"عندي تسريب في الحمام" → {"details": "تسريب في الحمام", ...}
"نعم صحيح" → {} (لا توجد معلومات جديدة)"""


REPLY_SYSTEM_PROMPT = """أنت مساعد واتساب ودود ومختصر لمنصة "هدهد" للخدمات.

## قواعد الرد:
1. كن مختصراً جداً (2-4 أسطر)
2. استخدم الإيموجي باعتدال
3. تحدث بالعربية الفصحى البسيطة

## مواقف الرد:

### إذا المعلومات ناقصة:
اسأل عن الناقص فقط (خدمة أو مدينة)

### إذا المعلومات كاملة:
أكد المعلومات واطلب التأكيد:
"تمام! ✅
- 🔧 [الخدمة]
- 📍 [المدينة]
صحيح؟"

### إذا العميل يطلب تعديل:
"لا مشكلة! وش التعديل؟"

لا تضف أي معلومات غير موجودة."""


class ReceptionAgent:
    """
    وكيل الاستقبال المحترف
    """
    
    # كلمات التأكيد
    CONFIRM_WORDS = ["نعم", "صح", "صحيح", "تمام", "اكيد", "ابحث", "ابدأ", "تم", "آبحث", "أبحث", "نعم صح", "نعم صحيح", "أيوة"]
    
    # كلمات التعديل
    EDIT_WORDS = ["لا", "خطأ", "غلط", "تعديل", "غير", "لا صح", "مو صح"]
    
    # المدن المعروفة
    KNOWN_CITIES = [
        "الرياض", "جدة", "مكة", "المدينة", "الدمام", "الخبر", "الظهران", 
        "الطائف", "تبوك", "بريدة", "خميس مشيط", "الهفوف", "المبرز", 
        "حفر الباطن", "حائل", "نجران", "الجبيل", "ينبع", "القصيم", "جازان", "أبها"
    ]
    
    # الخدمات المعروفة
    KNOWN_SERVICES = [
        "سباك", "سباكة", "كهرباء", "كهربائي", "تنظيف", "نظافة", "تكييف", 
        "مكيفات", "نقل", "عفش", "أثاث", "صباغ", "صباغة", "نجار", "نجارة",
        "حداد", "حدادة", "تسليك", "صيانة", "تمديد", "تركيب", "إصلاح", "تصليح"
    ]
    
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
        
        # استخراج البيانات السابقة
        previous_entities = self._get_previous_entities(current_context)
        print(f"📋 [ReceptionAgent] Previous entities: {previous_entities}")
        
        # التحقق من التأكيد أو التعديل
        is_confirming = self._is_confirmation(message)
        is_editing = self._is_edit(message)
        
        print(f"✅ [ReceptionAgent] Confirming: {is_confirming}, Editing: {is_editing}")
        
        # إذا العميل يؤكد والبيانات كاملة
        if is_confirming and previous_entities.service_type and previous_entities.city:
            print("🎯 [ReceptionAgent] Confirmation with complete data - starting search")
            return await self._handle_confirmation(
                customer_phone, conversation_id, previous_entities
            )
        
        # إذا العميل يعدل
        if is_editing:
            return {
                "reply": "لا مشكلة! 😊 أخبرني بالمعلومات الصحيحة.",
                "extracted_data": previous_entities.model_dump(),
                "ready_for_matching": False
            }
        
        # استخراج معلومات جديدة من الرسالة
        new_entities = await self._extract_entities(message)
        print(f"📊 [ReceptionAgent] New entities: {new_entities}")
        
        # دمج المعلومات
        merged_entities = self._merge_entities(previous_entities, new_entities)
        print(f"🔄 [ReceptionAgent] Merged entities: {merged_entities}")
        
        # توليد الرد
        reply = self._generate_reply(merged_entities, message)
        
        # التحقق إذا جاهز للتأكيد
        if merged_entities.service_type and merged_entities.city:
            # البيانات كاملة - ننتظر التأكيد
            pass
        
        return {
            "reply": reply,
            "extracted_data": merged_entities.model_dump(),
            "ready_for_matching": False
        }
    
    def _get_previous_entities(self, current_context: Dict) -> ExtractedEntities:
        """استخراج الكيانات السابقة من السياق"""
        if current_context and current_context.get("extracted_data"):
            try:
                return ExtractedEntities(**current_context["extracted_data"])
            except:
                pass
        return ExtractedEntities()
    
    def _is_confirmation(self, message: str) -> bool:
        """التحقق من كلمات التأكيد"""
        msg_clean = message.strip()
        return any(word in msg_clean for word in self.CONFIRM_WORDS)
    
    def _is_edit(self, message: str) -> bool:
        """التحقق من كلمات التعديل"""
        msg_clean = message.strip().lower()
        return any(word in msg_clean for word in self.EDIT_WORDS)
    
    async def _extract_entities(self, message: str) -> ExtractedEntities:
        """استخراج الكيانات من الرسالة"""
        
        # أولاً: استخراج سريع بالكلمات المفتاحية
        entities = ExtractedEntities()
        msg_lower = message.lower()
        
        # استخراج الخدمة
        for service in self.KNOWN_SERVICES:
            if service in msg_lower:
                if "سباك" in service:
                    entities.service_type = "سباكة"
                elif "كهرب" in service:
                    entities.service_type = "كهرباء"
                elif "نظاف" in service or "تنظيف" in service:
                    entities.service_type = "تنظيف"
                elif "تكييف" in service or "مكيف" in service:
                    entities.service_type = "تكييف"
                elif "نقل" in service or "عفش" in service:
                    entities.service_type = "نقل عفش"
                elif "صباغ" in service:
                    entities.service_type = "صباغة"
                elif "نجار" in service:
                    entities.service_type = "نجارة"
                else:
                    entities.service_type = service
                break
        
        # استخراج المدينة
        for city in self.KNOWN_CITIES:
            if city in message:
                entities.city = city
                break
        
        # استخراج التفاصيل
        details_patterns = [
            (r"تسريب?\s*(في|ب)?\s*(الحمام|المطبخ|البيت|الدور)?", "تسريب مياه"),
            (r"عطل\s*(في)?", "عطل"),
            (r"تركيب\s*(في)?", "تركيب"),
            (r"صيانة\s*(ل)?", "صيانة"),
        ]
        for pattern, detail in details_patterns:
            if re.search(pattern, msg_lower):
                entities.details = detail
                break
        
        # استخراج الميزانية
        budget_match = re.search(r'(\d+)\s*(ريال|ر\.س)', msg_lower)
        if budget_match:
            entities.budget = f"{budget_match.group(1)} ريال"
        
        # استخراج الاستعجال
        if any(w in msg_lower for w in ["عاجل", "ضروري", "الآن", "اليوم"]):
            entities.urgency = "عاجل"
        elif "غداً" in msg_lower or "بكره" in msg_lower:
            entities.urgency = "غداً"
        
        # إذا وجدنا معلومات كافية، نرجعها
        if entities.service_type or entities.city or entities.details:
            return entities
        
        # إذا لم نجد شيئاً، نستخدم AI
        try:
            ai_result = await deepseek_service.chat(
                messages=[{"role": "user", "content": message}],
                system_prompt=EXTRACTION_SYSTEM_PROMPT
            )
            
            if ai_result["success"]:
                content = ai_result["content"].strip()
                # استخراج JSON
                if "{" in content and "}" in content:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    json_str = content[start:end]
                    data = json.loads(json_str)
                    return ExtractedEntities(**data)
        except Exception as e:
            print(f"⚠️ [ReceptionAgent] AI extraction failed: {e}")
        
        return entities
    
    def _merge_entities(self, old: ExtractedEntities, new: ExtractedEntities) -> ExtractedEntities:
        """دمج الكيانات"""
        merged = old.model_dump()
        new_data = new.model_dump()
        
        for key, value in new_data.items():
            if value is not None:
                merged[key] = value
        
        return ExtractedEntities(**merged)
    
    def _generate_reply(self, entities: ExtractedEntities, message: str) -> str:
        """توليد الرد"""
        
        # إذا البيانات كاملة
        if entities.service_type and entities.city:
            parts = ["تمام! ✅\n"]
            parts.append(f"- 🔧 الخدمة: {entities.service_type}")
            parts.append(f"- 📍 المدينة: {entities.city}")
            if entities.details:
                parts.append(f"- 📝 التفاصيل: {entities.details}")
            if entities.neighborhood:
                parts.append(f"- 🏘️ الحي: {entities.neighborhood}")
            parts.append("\nصحيح؟ أكد عشان أبحث لك! 👍")
            return "\n".join(parts)
        
        # إذا ناقصة الخدمة
        if not entities.service_type and entities.city:
            return f"أهلاً! 🙋‍♂️\n\nأنت في {entities.city}.\n\n🔧 وش نوع الخدمة اللي تحتاجها؟"
        
        # إذا ناقصة المدينة
        if entities.service_type and not entities.city:
            return f"أهلاً! 🙋‍♂️\n\n{entities.service_type} - فهمت!\n\n📍 في أي مدينة؟"
        
        # لا توجد معلومات
        return "أهلاً! 🙋‍♂️\n\nكيف أقدر أساعدك؟ أخبرني بنوع الخدمة والمدينة."
    
    async def _handle_confirmation(
        self, 
        customer_phone: str, 
        conversation_id: str,
        entities: ExtractedEntities
    ) -> Dict[str, Any]:
        """معالجة التأكيد وبدء البحث"""
        
        # إنشاء طلب الخدمة
        request_result = await supabase_service.create_service_request(
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            service_type=entities.service_type,
            city=entities.city,
            details=entities.details,
            budget=entities.budget
        )
        
        if request_result.get("success"):
            request_id = request_result.get("request_id")
            slug = request_result.get("slug")
            offer_url = f"{APP_URL}/offers/{slug}"
            
            reply = f"""✅ *تم استلام طلبك!*

📋 *الخدمة:* {entities.service_type}
📍 *المدينة:* {entities.city}
📝 *التفاصيل:* {entities.details or 'غير محددة'}

🔍 جاري البحث عن أفضل المزودين...

🔗 *صفحة العروض:*
{offer_url}

⏰ صلاحية الصفحة: ساعتين

سيصلك تنبيه عند وصول عروض! 📬"""
            
            return {
                "reply": reply,
                "extracted_data": entities.model_dump(),
                "ready_for_matching": True,
                "request_id": request_id
            }
        
        return {
            "reply": "عذراً، حدث خطأ في إنشاء الطلب. يرجى المحاولة مرة أخرى.",
            "extracted_data": entities.model_dump(),
            "ready_for_matching": False
        }


# إنشاء instance واحد
reception_agent = ReceptionAgent()
