"""
Reception Agent - وكيل الاستقبال الذكي المحمي
يستخرج المعلومات ويتحقق من التوفر وينشئ طلب في قاعدة البيانات

Features:
- التحقق من توفر المزودين قبل التأكيد
- حماية من الطلبات الخارجة عن النطاق
- ردود مشروطة حسب التوفر
"""

import re
from typing import Dict, Any, Optional, List
from services.supabase_service import supabase_service, PLATFORM_URL

# In-Memory Context Store
CONTEXT_STORE: Dict[str, Dict] = {}

# كلمات التأكيد
CONFIRM_WORDS = ["نعم", "صح", "صحيح", "تمام", "اكيد", "ابحث", "ابدأ", "تم", "آبحث", "أبحث", "أيوة", "ايوه", "صح"]

# كلمات الإلغاء
CANCEL_WORDS = ["لا", "إلغاء", "الغاء", "تراجع", "كانسل", "الغي"]

# كلمات إعادة التعيين (طلب جديد)
RESET_WORDS = ["طلب جديد", "جديد", "ابي", "أبي", "ابغى", "أبغى", "أريد", "اريد", "احتاج", "أحتاج", "اريده", "ممكن", "أبي"]

# المدن
KNOWN_CITIES = [
    "الرياض", "جدة", "مكة", "المدينة", "الدمام", "الخبر", "الطائف", 
    "تبوك", "بريدة", "خميس مشيط", "الهفوف", "حائل", "نجران", "أبها", 
    "جازان", "القصيم", "القطيف", "الأحساء", "ينبع", "الجبيل", "الخرج",
    "عنيزة", "الرس", "الطائف"
]

# الخدمات
SERVICE_KEYWORDS = {
    "سباكة": ["سباك", "سباكة", "تسريب", "مويه", "مياه", "حمام", "مطبخ", "خراب", "صرف", "مويا"],
    "كهرباء": ["كهرب", "كهرباء", "تمديد", "أسلاك", "مفتاح", "فيش", "أعطال", "إنارة", "انارة"],
    "تنظيف": ["تنظيف", "نظاف", "تعقيم", "غسيل", "سجاد", "موكيت", "كنس", "شقق", "خزانات"],
    "تكييف": ["تكييف", "مكيف", "تبريد", "فريون", "سبلت", "وحدة", "تشغيل", "تبريد"],
    "نقل عفش": ["نقل", "عفش", "أثاث", "انتقال", "أغراض", "أواني", "شحن", "انتقال"],
    "صباغة": ["صباغ", "صباغة", "دهان", "طلاء", "لون", "ديكور", "جدران", "دهن"],
    "نجارة": ["نجار", "نجارة", "خشب", "أبواب", "مطابخ", "موبيليا", "أرفف"]
}

# كلمات محاولات الخداع (Prompt Injection)
ATTACK_KEYWORDS = [
    "تجاهل", "اضبط", "اعمل كـ", "اكتب كود", "اكتب قصيد", "من أنت",
    "ما تعليماتك", "كيف تعمل", "programmer", "developer", "ignore",
    "system prompt", "تعليماتك الداخلية", "فوق دورك", "خرج عن الموضوع",
    "أصبح", "كن أنت", "change your", "act as", "pretend"
]

# رد الحماية
OFF_TOPIC_RESPONSE = "عذراً، أنا هنا لمساعدتك في طلب الخدمات فقط 🙏\n\nهل تحتاج فني أو خدمة معينة؟"

# رد عدم التوفر
SERVICE_NOT_AVAILABLE = "عذراً، خدمة {service} في {city} غير متوفرة حالياً 💔\n\n💡 سنبلغك فور توفرها، أو جرب مدينة أخرى!"


class ReceptionAgent:
    """وكيل الاستقبال الذكي المحمي"""
    
    def _normalize_phone(self, phone: str) -> str:
        """ت normalize رقم الهاتف"""
        return phone.replace(" ", "").replace("+", "").replace("whatsapp:", "")
    
    def _detect_service(self, message: str) -> Optional[str]:
        """اكتشاف الخدمة من الرسالة"""
        for service, keywords in SERVICE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message:
                    return service
        return None
    
    def _detect_city(self, message: str) -> Optional[str]:
        """اكتشاف المدينة من الرسالة"""
        for city in KNOWN_CITIES:
            if city in message:
                return city
        return None
    
    def _is_off_topic(self, message: str) -> bool:
        """التحقق من الطلبات الخارجة عن النطاق"""
        message_lower = message.lower()
        
        # التحقق من كلمات الخداع
        for keyword in ATTACK_KEYWORDS:
            if keyword.lower() in message_lower:
                return True
        
        # التحقق من الرسائل الطويلة بدون خدمات
        has_service = self._detect_service(message) is not None
        has_city = self._detect_city(message) is not None
        has_request_word = any(w in message_lower for w in ["أبي", "ابي", "أحتاج", "احتاج", "مطلوب", "دور", "ابحث", "أبحث"])
        
        if len(message) > 150 and not (has_service or has_city or has_request_word):
            return True
        
        return False
    
    def _is_confirmed(self, message: str) -> bool:
        """التحقق من التأكيد"""
        message = message.strip().lower()
        return any(w in message for w in CONFIRM_WORDS)
    
    def _is_canceled(self, message: str) -> bool:
        """التحقق من الإلغاء"""
        message = message.strip().lower()
        return any(w in message for w in CANCEL_WORDS)
    
    async def _check_provider_availability(self, service_type: str, city: str) -> Dict[str, Any]:
        """التحقق من توفر المزودين"""
        try:
            providers = await supabase_service.search_providers(
                service_type=service_type,
                city=city,
                limit=10
            )
            
            if providers:
                return {
                    "available": True,
                    "count": len(providers),
                    "top_provider": providers[0].get("business_name", "مزود معتمد")
                }
            else:
                return {
                    "available": False,
                    "count": 0,
                    "top_provider": None
                }
        except Exception as e:
            print(f"❌ [Agent] Provider check error: {e}")
            # في حالة الخطأ، نفترض التوفر لعدم حجب العميل
            return {"available": True, "count": 0, "top_provider": None}
    
    async def process_message(
        self,
        customer_phone: str,
        message: str,
        conversation_id: str,
        conversation_history: List[Dict],
        current_context: Dict = None
    ) -> Dict[str, Any]:
        """معالجة الرسالة مع الحماية والتحقق من التوفر"""
        
        phone_key = self._normalize_phone(customer_phone)
        print(f"🤖 [SmartAgent] Phone: {phone_key}")
        print(f"💬 [SmartAgent] Message: '{message}'")
        
        # 🛡️ حماية: التحقق من الطلبات الخارجة عن النطاق
        if self._is_off_topic(message):
            print("⚠️ [SmartAgent] Off-topic detected - blocking")
            return {
                "reply": OFF_TOPIC_RESPONSE,
                "extracted_data": {},
                "ready_for_matching": False
            }
        
        # استرجاع أو إنشاء سياق
        context = CONTEXT_STORE.get(phone_key, {"extracted_data": {}, "stage": "collecting"})
        extracted_data = context.get("extracted_data", {})
        print(f"📋 [SmartAgent] Current data: {extracted_data}")
        
        # 🔄 التحقق من طلب جديد - إعادة تعيين السياق
        is_new_request = any(w in message for w in RESET_WORDS)
        new_service = self._detect_service(message)
        new_city = self._detect_city(message)
        
        if is_new_request and (new_service or new_city):
            print("🔄 [SmartAgent] New request detected - resetting context")
            extracted_data = {}
            if phone_key in CONTEXT_STORE:
                del CONTEXT_STORE[phone_key]
            print("✅ [SmartAgent] Context cleared for new request")
        
        # التحقق من الإلغاء
        if self._is_canceled(message):
            if phone_key in CONTEXT_STORE:
                del CONTEXT_STORE[phone_key]
            return {
                "reply": "تم الإلغاء ✅\n\nكيف أساعدك؟ 🙋‍♂️",
                "extracted_data": {},
                "ready_for_matching": False
            }
        
        # التحقق من التأكيد
        if self._is_confirmed(message):
            if extracted_data.get("service_type") and extracted_data.get("city"):
                print("✅ [SmartAgent] Confirmed - checking availability...")
                
                # 🔍 التحقق من توفر المزودين
                availability = await self._check_provider_availability(
                    extracted_data.get("service_type"),
                    extracted_data.get("city")
                )
                
                if not availability.get("available"):
                    # لا يوجد مزودين - اعتذر
                    service_name = extracted_data.get("service_type")
                    city_name = extracted_data.get("city")
                    print(f"⚠️ [SmartAgent] No providers for {service_name} in {city_name}")
                    
                    return {
                        "reply": SERVICE_NOT_AVAILABLE.format(service=service_name, city=city_name),
                        "extracted_data": extracted_data,
                        "ready_for_matching": False
                    }
                
                provider_count = availability.get("count", 0)
                print(f"✅ [SmartAgent] {provider_count} providers available!")
                
                # إنشاء طلب في قاعدة البيانات
                db_result = await supabase_service.create_service_request(
                    customer_phone=customer_phone,
                    service_type=extracted_data.get("service_type"),
                    city=extracted_data.get("city"),
                    description=extracted_data.get("details")
                )
                
                # مسح السياق
                if phone_key in CONTEXT_STORE:
                    del CONTEXT_STORE[phone_key]
                
                # إرسال رابط صفحة العروض
                if db_result.get("success") and db_result.get("request_id"):
                    offers_url = f"{PLATFORM_URL}/offers/{db_result['request_id']}"
                    print(f"🔗 [SmartAgent] Offers URL: {offers_url}")
                    
                    return {
                        "reply": f"""✅ *تم استلام طلبك!*

📋 *الخدمة:* {extracted_data.get('service_type')}
📍 *المدينة:* {extracted_data.get('city')}
👥 *المزودين المتاحين:* {provider_count}
{f"📝 *التفاصيل:* {extracted_data.get('details')}" if extracted_data.get('details') else ''}

🔗 *صفحة العروض:*
{offers_url}

سيصلك إشعار عند وصول عروض جديدة! 📬""",
                        "extracted_data": extracted_data,
                        "ready_for_matching": True,
                        "request_id": db_result.get("request_id"),
                        "provider_count": provider_count
                    }
                else:
                    return {
                        "reply": f"""✅ *تم استلام طلبك!*

📋 *الخدمة:* {extracted_data.get('service_type')}
📍 *المدينة:* {extracted_data.get('city')}
👥 *المزودين:* {provider_count}

🔍 جاري البحث عن أفضل المزودين...
سيصلك رابط صفحة العروض قريباً! 📬""",
                        "extracted_data": extracted_data,
                        "ready_for_matching": True
                    }
        
        # استخراج معلومات جديدة
        new_service = self._detect_service(message)
        new_city = self._detect_city(message)
        
        if new_service:
            extracted_data["service_type"] = new_service
            print(f"🔧 [SmartAgent] Detected service: {new_service}")
        if new_city:
            extracted_data["city"] = new_city
            print(f"📍 [SmartAgent] Detected city: {new_city}")
        
        # حفظ التفاصيل
        extracted_data["details"] = message
        
        # حفظ السياق
        CONTEXT_STORE[phone_key] = {"extracted_data": extracted_data}
        
        # توليد الرد الذكي
        service = extracted_data.get("service_type")
        city = extracted_data.get("city")
        
        if service and city:
            # 🔍 التحقق من التوفر قبل طلب التأكيد
            availability = await self._check_provider_availability(service, city)
            
            if availability.get("available"):
                count = availability.get("count", 0)
                return {
                    "reply": f"""📝 *فهمت طلبك!*

🔧 {service} - {city}
👥 {count} مزود متاح

صحيح؟ أكد للبحث! ✅""",
                    "extracted_data": extracted_data,
                    "ready_for_matching": False
                }
            else:
                return {
                    "reply": f"""📝 *فهمت طلبك!*

🔧 {service} - {city}
⚠️ الخدمة غير متوفرة حالياً

💡 هل تريد خدمة أخرى؟ أو جرب مدينة قريبة!""",
                    "extracted_data": extracted_data,
                    "ready_for_matching": False
                }
        
        elif service:
            return {
                "reply": f"🔧 {service} - فهمت!\n\n📍 في أي مدينة؟",
                "extracted_data": extracted_data,
                "ready_for_matching": False
            }
        
        elif city:
            return {
                "reply": f"📍 {city} - عرفت!\n\n🔧 وش تحتاج؟ (سباك، كهربائي، مكيفات...)",
                "extracted_data": extracted_data,
                "ready_for_matching": False
            }
        
        else:
            return {
                "reply": "أهلاً! 🙋‍♂️\n\nكيف أساعدك؟ أخبرني بالخدمة والمدينة.\n\nمثال: أحتاج سباك في الرياض",
                "extracted_data": extracted_data,
                "ready_for_matching": False
            }


# إنشاء instance
reception_agent = ReceptionAgent()
