"""
Provider Agent - وكيل المزودين
الوكيل الثاني - يبحث عن المزودين ويرسل لهم الطلبات
"""

from typing import Dict, Any, Optional, List
from services.deepseek_service import deepseek_service
from services.supabase_service import supabase_service
from services.twilio_service import twilio_service
from config import MAX_PROVIDERS_PER_REQUEST


class ProviderAgent:
    """
    وكيل المزودين - الوكيل الثاني في النظام
    
    المسؤوليات:
    1. البحث عن مزودين مطابقين في قاعدة البيانات
    2. تصفية وترتيب المزودين حسب المعايير
    3. إرسال طلبات العروض للمزودين عبر واتساب
    4. تتبع حالة الإرسال
    """
    
    # System Prompt للوكيل (للاتصالات المستقبلية مع المزودين)
    SYSTEM_PROMPT = """
أنت وكيل التواصل مع المزودين في منصة "هدهد".

## مهمتك:
- تفهم ردود المزودين على طلبات العروض
- تستخرج معلومات العرض (السعر، الملاحظات)
- تحافظ على تواصل مهني ومحترف

## قواعد:
- تعامل باحترافية مع المزودين
- ساعد في توضيح تفاصيل الطلب إذا سُئلت
- لا تعطِ معلومات العميل الشخصية للمزود
"""
    
    def __init__(self):
        self.active_requests: Dict[str, List[str]] = {}
    
    async def find_and_contact_providers(
        self,
        request_id: str,
        service_type: str,
        city: str,
        details: Optional[str] = None,
        budget: Optional[str] = None,
        customer_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        البحث عن مزودين وإرسال طلبات لهم
        
        Args:
            request_id: معرف الطلب
            service_type: نوع الخدمة
            city: المدينة
            details: تفاصيل الطلب
            budget: الميزانية
        
        Returns:
            {
                "success": bool,
                "providers_found": int,
                "providers_contacted": List[str],
                "error": str (if any)
            }
        """
        print(f"🔍 [ProviderAgent] Searching for: {service_type} in {city}")
        
        # البحث عن مزودين مطابقين
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
                "providers_contacted": [],
                "error": "لا يوجد مزودين متاحين في منطقتك حالياً"
            }
        
        print(f"✅ [ProviderAgent] Found {len(providers)} providers")
        
        # إرسال طلبات للمزودين
        contacted_providers = []
        
        for provider in providers:
            provider_phone = provider.get("phone", "")
            provider_id = provider.get("id")
            
            if not provider_phone:
                continue
            
            # تنسيق رقم الهاتف
            if not provider_phone.startswith("whatsapp:"):
                provider_phone = f"whatsapp:+{provider_phone.replace('+', '').replace(' ', '')}"
            
            # إرسال طلب العرض
            send_result = twilio_service.send_vendor_offer_request(
                vendor_phone=provider_phone,
                request_data={
                    "request_id": request_id,
                    "service_type": service_type,
                    "city": city,
                    "details": details or "لا توجد تفاصيل إضافية",
                    "budget": budget or "مفتوح"
                }
            )
            
            if send_result.get("status") in ["sent", "mocked"]:
                contacted_providers.append(provider_id)
                print(f"📤 [ProviderAgent] Sent to provider: {provider.get('name')}")
        
        # حفظ المزودين الذين تم التواصل معهم
        self.active_requests[request_id] = contacted_providers
        
        return {
            "success": True,
            "providers_found": len(providers),
            "providers_contacted": contacted_providers
        }
    
    async def process_provider_response(
        self,
        provider_phone: str,
        message: str
    ) -> Dict[str, Any]:
        """
        معالجة رد المزود على طلب عرض
        
        Args:
            provider_phone: رقم هاتف المزود
            message: نص الرد
        
        Returns:
            {
                "success": bool,
                "offer_saved": bool,
                "price": str,
                "notes": str
            }
        """
        print(f"📥 [ProviderAgent] Provider response from {provider_phone}: {message[:50]}...")
        
        # استخراج معلومات العرض من رسالة المزود
        offer_data = await self._extract_offer_data(message)
        
        if not offer_data:
            return {
                "success": False,
                "error": "لم أتمكن من فهم العرض"
            }
        
        # البحث عن المزود في قاعدة البيانات
        provider = await self._get_provider_by_phone(provider_phone)
        
        if not provider:
            return {
                "success": False,
                "error": "المزود غير مسجل في النظام"
            }
        
        # البحث عن الطلب النشط للمزود
        active_request_id = await self._get_active_request_for_provider(provider["id"])
        
        if not active_request_id:
            return {
                "success": False,
                "error": "لا يوجد طلب نشط لهذا المزود"
            }
        
        # حفظ العرض
        save_result = await supabase_service.save_provider_offer(
            request_id=active_request_id,
            provider_id=provider["id"],
            price=offer_data.get("price", ""),
            notes=offer_data.get("notes")
        )
        
        if save_result.get("success"):
            # إرسال تأكيد للمزود
            twilio_service.send_whatsapp(
                to_number=provider_phone,
                body="✅ تم استلام عرضك! سيتم إشعار العميل."
            )
            
            return {
                "success": True,
                "offer_saved": True,
                "price": offer_data.get("price"),
                "notes": offer_data.get("notes"),
                "request_id": active_request_id
            }
        
        return {
            "success": False,
            "error": "حدث خطأ أثناء حفظ العرض"
        }
    
    async def _extract_offer_data(self, message: str) -> Optional[Dict]:
        """
        استخراج معلومات العرض من رسالة المزود
        """
        extraction_prompt = """
استخرج معلومات العرض من رسالة المزود:

{
    "price": "السعر المقدم أو null",
    "notes": "ملاحظات المزود أو null",
    "is_rejection": true/false (هل المزود يرفض الطلب؟)
}

أعد JSON فقط.
"""
        
        result = await deepseek_service.extract_structured_data(
            user_message=message,
            fields=["price", "notes", "is_rejection"],
            system_prompt=extraction_prompt
        )
        
        if result.get("success"):
            data = result.get("data")
            if data and not data.get("is_rejection"):
                return data
        
        return None
    
    async def _get_provider_by_phone(self, phone: str) -> Optional[Dict]:
        """
        الحصول على بيانات المزود من رقم الهاتف
        """
        # تنظيف الرقم
        clean_phone = phone.replace("whatsapp:", "").replace("+", "").replace(" ", "")
        
        # البحث في قاعدة البيانات
        # TODO: إضافة دالة البحث بالهاتف في supabase_service
        return None  # مؤقتاً
    
    async def _get_active_request_for_provider(self, provider_id: str) -> Optional[str]:
        """
        الحصول على الطلب النشط للمزود
        """
        # TODO: تنفيذ منطق البحث عن الطلب النشط
        return None  # مؤقتاً


# إنشاء instance واحد
provider_agent = ProviderAgent()
