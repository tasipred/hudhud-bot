"""
Reception Agent - وكيل الاستقبال المحترف
يبني على منهجية Entity Extraction + Structured Output
"""

import json
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
    service_type: Optional[str] = Field(None, description="نوع الخدمة: سباكة، كهرباء، تنظيف، تكييف، نقل، صباغة، نجارة، إلخ")
    city: Optional[str] = Field(None, description="المدينة: الرياض، جدة، مكة، الدمام، إلخ")
    neighborhood: Optional[str] = Field(None, description="اسم الحي أو المنطقة")
    details: Optional[str] = Field(None, description="تفاصيل المشكلة أو الطلب")
    urgency: Optional[str] = Field(None, description="مستوى الاستعجال: عاجل، اليوم، غداً، هذا الأسبوع")
    time_slot: Optional[str] = Field(None, description="الوقت المفضل: صباح، مساء، بعد المغرب")
    budget: Optional[str] = Field(None, description="الميزانية المذكورة")
    contact_preference: Optional[str] = Field(None, description="تفضيل التواصل: اتصال، واتساب")


class ConversationContext(BaseModel):
    """سياق المحادثة الكامل"""
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    stage: str = Field(default="collecting", description="collecting, confirming, searching")
    messages_count: int = Field(default=0)
    last_intent: Optional[str] = None


# ============================================
# System Prompt المحترف
# ============================================

RECEPTION_SYSTEM_PROMPT = """
أنت وكيل الاستقبال الذكي في منصة "هدهد" للخدمات المنزلية.

## 🎯 مهمتك:
استخرج معلومات العميل من رسالته وأجب بشكل طبيعي ومفيد.

## 📋 بروتوكول الاستخراج:
من كل رسالة، استخرج المعلومات المتوفرة وأعدها في JSON:

```json
{
    "service_type": "نوع الخدمة أو null",
    "city": "المدينة أو null",
    "neighborhood": "الحي أو null",
    "details": "تفاصيل المشكلة أو null",
    "urgency": "عاجل/اليوم/غداً أو null",
    "time_slot": "الوقت المفضل أو null",
    "budget": "الميزانية أو null"
}
```

## 📝 قاعدة الرد:
1. إذا المعلومات **ناقصة** → اسأل عن الناقص فقط
2. إذا المعلومات **كاملة** → أكدها واطلب التأكيد
3. إذا العميل **أكد** → قل "تمام! جاري البحث..."

## ⚠️ قواعد صارمة:
- لا تسأل عن معلومة ذُكرت سابقاً
- لا تكرر الأسئلة
- كن مختصراً (3-4 أسطر كحد أقصى)
- لا تختلق معلومات غير موجودة
- إذا العميل قال "نعم" أو "صح" أو "ابحث" → اعتبره تأكيد

## 📱 المعلومات المطلوبة (بالترتيب):
1. نوع الخدمة (إجباري)
2. المدينة (إجباري)
3. التفاصيل (اختياري لكن مهم)

## أمثلة:

### مثال 1 - رسالة أولى:
العميل: "أبي سباك في الرياض عندي تسريب"
الرد: تم استخراج: سباكة، الرياض، تسريب
JSON: {"service_type": "سباكة", "city": "الرياض", "details": "تسريب"}
الرسالة: "تمام! 🔧 سباكة في الرياض - تسريب\n\nصحيح؟ 🤝"

### مثال 2 - نقص المدينة:
العميل: "أبي كهربائي"
الرد: {"service_type": "كهرباء"}
الرسالة: "أهلاً! ⚡ كهربائي - فهمت!\n\n📍 في أي مدينة؟"

### مثال 3 - تأكيد:
العميل: "نعم صحيح ابحث"
الرد: تأكيد = true
الرسالة: "تمام! 🔍 جاري البحث..."

---

**أهم شيء:** ردك يجب أن يكون JSON يليه رسالة للعميل. سيتم فصلهم تلقائياً.
"""


class ReceptionAgent:
    """
    وكيل الاستقبال المحترف - يستخدم Structured Output
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
        معالجة رسالة العميل بطريقة احترافية
        """
        print(f"🤖 [ReceptionAgent] Processing: {message}")
        
        # تحميل السياق السابق
        context = self._load_context(current_context)
        print(f"📋 [ReceptionAgent] Current context: {context}")
        
        # بناء تاريخ المحادثة للـ AI
        chat_history = self._build_chat_history(conversation_history, message)
        
        # بناء Prompt مع السياق
        full_prompt = self._build_prompt_with_context(context, message)
        
        # استدعاء AI مرة واحدة فقط
        ai_response = await deepseek_service.chat(
            messages=chat_history,
            system_prompt=full_prompt
        )
        
        if not ai_response["success"]:
            return self._error_response()
        
        # تحليل الرد
        raw_content = ai_response["content"]
        extracted_entities, reply_text = self._parse_ai_response(raw_content)
        
        print(f"📊 [ReceptionAgent] Extracted: {extracted_entities}")
        print(f"💬 [ReceptionAgent] Reply: {reply_text}")
        
        # دمج الكيانات الجديدة مع القديمة
        merged_entities = self._merge_entities(context.entities, extracted_entities)
        print(f"🔄 [ReceptionAgent] Merged: {merged_entities}")
        
        # تحديث السياق
        context.entities = merged_entities
        context.messages_count += 1
        
        # التحقق من التأكيد
        is_confirming = self._check_confirmation(message)
        
        # التحقق من جاهزية البحث
        ready_for_matching = False
        request_id = None
        
        if is_confirming and merged_entities.service_type and merged_entities.city:
            ready_for_matching = True
            context.stage = "searching"
            
            # إنشاء طلب الخدمة
            request_result = await supabase_service.create_service_request(
                conversation_id=conversation_id,
                customer_phone=customer_phone,
                service_type=merged_entities.service_type,
                city=merged_entities.city,
                details=merged_entities.details,
                budget=merged_entities.budget
            )
            
            if request_result.get("success"):
                request_id = request_result.get("request_id")
                slug = request_result.get("slug")
                offer_url = f"{APP_URL}/offers/{slug}"
                
                reply_text = f"""✅ *تم استلام طلبك!*

📋 *الخدمة:* {merged_entities.service_type}
📍 *المدينة:* {merged_entities.city}
📝 *التفاصيل:* {merged_entities.details or 'غير محددة'}

🔍 جاري البحث عن أفضل المزودين...

🔗 *صفحة العروض:*
{offer_url}

⏰ صلاحية الصفحة: ساعتين"""
        
        # إذا المعلومات كاملة ولم يؤكد بعد
        elif merged_entities.service_type and merged_entities.city and not is_confirming:
            context.stage = "confirming"
            reply_text = self._generate_confirmation_message(merged_entities)
        
        return {
            "reply": reply_text,
            "extracted_data": merged_entities.model_dump(),
            "ready_for_matching": ready_for_matching,
            "request_id": request_id
        }
    
    def _load_context(self, current_context: Dict) -> ConversationContext:
        """تحميل السياق من البيانات المحفوظة"""
        if current_context:
            entities_data = current_context.get("extracted_data", {})
            entities = ExtractedEntities(**entities_data) if entities_data else ExtractedEntities()
            return ConversationContext(
                entities=entities,
                stage=current_context.get("stage", "collecting"),
                messages_count=current_context.get("messages_count", 0)
            )
        return ConversationContext()
    
    def _build_chat_history(self, conversation_history: List[Dict], current_message: str) -> List[Dict]:
        """بناء تاريخ المحادثة"""
        history = []
        for msg in conversation_history:
            role = "user" if msg["sender"] == "customer" else "assistant"
            history.append({"role": role, "content": msg["content"]})
        history.append({"role": "user", "content": current_message})
        return history
    
    def _build_prompt_with_context(self, context: ConversationContext, message: str) -> str:
        """بناء Prompt مع السياق الحالي"""
        
        # معلومات مستخرجة سابقاً
        known_info = []
        if context.entities.service_type:
            known_info.append(f"🔧 الخدمة: {context.entities.service_type}")
        if context.entities.city:
            known_info.append(f"📍 المدينة: {context.entities.city}")
        if context.entities.neighborhood:
            known_info.append(f"🏘️ الحي: {context.entities.neighborhood}")
        if context.entities.details:
            known_info.append(f"📝 التفاصيل: {context.entities.details}")
        if context.entities.urgency:
            known_info.append(f"⚡ الاستعجال: {context.entities.urgency}")
        if context.entities.budget:
            known_info.append(f"💰 الميزانية: {context.entities.budget}")
        
        context_section = ""
        if known_info:
            context_section = f"""
## 📋 معلومات معروفة مسبقاً (لا تسأل عنها):
{chr(10).join(known_info)}

⚠️ مهم: العميل قد ذكر هذه المعلومات سابقاً، لا تسأل عنها مجدداً!
"""
        
        return RECEPTION_SYSTEM_PROMPT + context_section
    
    def _parse_ai_response(self, content: str) -> tuple:
        """تحليل رد AI لاستخراج JSON والنص"""
        
        # محاولة استخراج JSON من الرد
        try:
            # البحث عن JSON في الرد
            json_match = None
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_match = content[start:end].strip()
            elif "{" in content and "}" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                json_match = content[start:end]
            
            if json_match:
                data = json.loads(json_match)
                entities = ExtractedEntities(**data)
                
                # استخراج النص بعد JSON
                text = content
                if "```" in content:
                    parts = content.split("```")
                    text = parts[-1].strip() if len(parts) > 2 else content
                else:
                    # إزالة JSON من النص
                    text = content.replace(json_match, "").strip()
                
                return entities, text if text else self._generate_default_reply(entities)
        
        except Exception as e:
            print(f"⚠️ [ReceptionAgent] JSON parse error: {e}")
        
        # إذا فشل الاستخراج، نرجع النص كما هو
        return ExtractedEntities(), content
    
    def _merge_entities(self, old: ExtractedEntities, new: ExtractedEntities) -> ExtractedEntities:
        """دمج الكيانات القديمة مع الجديدة"""
        merged = old.model_dump()
        new_data = new.model_dump()
        
        # البيانات الجديدة تسبق إذا لم تكن null
        for key, value in new_data.items():
            if value is not None:
                merged[key] = value
        
        return ExtractedEntities(**merged)
    
    def _check_confirmation(self, message: str) -> bool:
        """التحقق من كلمات التأكيد"""
        confirm_words = ["نعم", "صح", "صحيح", "تمام", "اكيد", "ابحث", "ابدأ", "تم", "آبحث", "أبحث", "نعم صح", "نعم صحيح"]
        return any(word in message for word in confirm_words)
    
    def _generate_confirmation_message(self, entities: ExtractedEntities) -> str:
        """توليد رسالة التأكيد"""
        parts = ["تمام! ✅\n"]
        parts.append(f"- 🔧 الخدمة: {entities.service_type}")
        parts.append(f"- 📍 المدينة: {entities.city}")
        if entities.details:
            parts.append(f"- 📝 التفاصيل: {entities.details}")
        if entities.neighborhood:
            parts.append(f"- 🏘️ الحي: {entities.neighborhood}")
        parts.append("\nصحيح؟ أكد عشان أبحث لك! 👍")
        return "\n".join(parts)
    
    def _generate_default_reply(self, entities: ExtractedEntities) -> str:
        """توليد رد افتراضي بناءً على الكيانات"""
        if entities.service_type and entities.city:
            return self._generate_confirmation_message(entities)
        elif entities.service_type:
            return f"أهلاً! 🙋‍♂️ {entities.service_type} - فهمت!\n\n📍 في أي مدينة؟"
        elif entities.city:
            return f"أهلاً! 🙋‍♂️\n\nأنت في {entities.city}.\n\n🔧 وش نوع الخدمة؟"
        return "أهلاً! 🙋‍♂️\n\nكيف أقدر أساعدك؟"
    
    def _error_response(self) -> Dict[str, Any]:
        """رد في حالة الخطأ"""
        return {
            "reply": "عذراً، حدث خطأ تقني. يرجى المحاولة مرة أخرى.",
            "extracted_data": {},
            "ready_for_matching": False
        }


# إنشاء instance واحد
reception_agent = ReceptionAgent()
