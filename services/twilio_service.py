"""
Twilio WhatsApp Service
خدمة واتساب عبر Twilio - هدهد بوت
"""

import os
import json
import hashlib
from typing import List, Optional, Dict, Any
from twilio.rest import Client
import httpx


class TwilioService:
    """
    خدمة Twilio للواتساب - هدهد بوت
    """
    
    def __init__(self):
        self.sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        print(f"[TwilioService] DEBUG: from_number = '{self.from_number}'")
        
        if self.sid and self.token:
            self.client = Client(self.sid, self.token)
            print("[TwilioService] ✅ Initialized Real Twilio Client")
        else:
            self.client = None
            print("[TwilioService] ⚠️ Running in Mock Mode (No Credentials)")
    
    # ============================================
    # Basic Messaging
    # ============================================
    
    def send_whatsapp(
        self,
        to_number: str,
        body: str,
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        إرسال رسالة واتساب عادية
        
        Args:
            to_number: رقم المستلم (with whatsapp: prefix)
            body: نص الرسالة
            media_url: رابط صورة (اختياري)
        
        Returns:
            {"status": "sent" | "error", "sid": str, "error": str}
        """
        if not self.client:
            print(f"[MOCK SEND] To: {to_number} | Body: {body[:50]}...")
            return {"status": "mocked", "sid": "mock-sid"}
        
        # التأكد من صيغة الرقم
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"
        
        try:
            msg_args = {
                "from_": self.from_number,
                "body": body,
                "to": to_number
            }
            # TODO: تعطيل media_url - يسبب أخطاء 11200 وتكاليف SMS إضافية
            # if media_url:
            #     msg_args["media_url"] = [media_url]

            message = self.client.messages.create(**msg_args)
            print(f"[TwilioService] ✅ Sent OK: {message.sid}")
            return {"status": "sent", "sid": message.sid}
        except Exception as e:
            print(f"[TwilioService] ❌ Error sending: {e}")
            return {"status": "error", "error": str(e)}
    
    # ============================================
    # Template Messages
    # ============================================
    
    def send_template_message(
        self,
        to_number: str,
        template_sid: str,
        variables: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        إرسال رسالة قالب تفاعلية
        """
        if not self.client:
            print(f"[MOCK TEMPLATE] To: {to_number} | Template: {template_sid}")
            return {"status": "mocked"}

        try:
            message = self.client.messages.create(
                from_=self.from_number,
                to=to_number,
                content_sid=template_sid,
                content_variables=json.dumps(variables)
            )
            print(f"[TwilioService] ✅ Template Sent: {message.sid}")
            return {"status": "sent", "sid": message.sid}
        except Exception as e:
            print(f"[TwilioService] ❌ Template Error: {e}")
            return {"status": "error", "error": str(e)}
    
    # ============================================
    # Welcome Message
    # ============================================
    
    def send_welcome(self, to_number: str) -> Dict[str, Any]:
        """
        إرسال رسالة الترحيب الموحدة
        """
        welcome_msg = """
🦦 *أهلاً بك في هدهد!*

أنا مساعدك الذكي للحصول على أفضل خدمات الصيانة والتركيب.

📋 *كيف أقدر أساعدك؟*
اكتب الخدمة اللي تحتاجها، مثال:
• "أبي سباك في الرياض"
• "كهربائي للإصلاح العاجل"
• "تنظيف مكيفات"

💡 *خدماتنا:*
سباكة • كهرباء • تكييف • تنظيف • نقل أثاث • وغيرها

_جاهز لخدمتك! فقط اكتب طلبك_ 👇
        """.strip()
        
        return self.send_whatsapp(to_number, welcome_msg)
    
    # ============================================
    # Request Confirmation
    # ============================================
    
    def send_request_received(
        self,
        to_number: str,
        service_type: str,
        city: str,
        offer_page_url: str,
        expires_hours: int = 2
    ) -> Dict[str, Any]:
        """
        إرسال تأكيد استلام الطلب مع رابط صفحة العروض
        """
        msg = f"""
✅ *تم استلام طلبك!*

📋 *الخدمة:* {service_type}
📍 *المدينة:* {city}

🔍 جاري البحث عن أفضل المزودين...

🔗 *صفحة العروض:*
{offer_page_url}

⏰ صلاحية الصفحة: {expires_hours} ساعة

سيصلك تنبيه عند وصول عروض جديدة! 📬
        """.strip()
        
        return self.send_whatsapp(to_number, msg)
    
    # ============================================
    # Provider Request
    # ============================================
    
    def send_vendor_offer_request(
        self,
        vendor_phone: str,
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        إرسال طلب عرض لمزود الخدمة
        
        Args:
            vendor_phone: رقم المزود
            request_data: {
                'request_id': str,
                'service_type': str,
                'city': str,
                'details': str,
                'budget': str
            }
        """
        message = f"""
🔔 *طلب جديد من هدهد!*

📋 *الخدمة:* {request_data.get('service_type', 'غير محدد')}
📍 *المدينة:* {request_data.get('city', 'غير محدد')}

📝 *التفاصيل:*
{request_data.get('details', 'لا توجد تفاصيل')}

💰 *الميزانية:* {request_data.get('budget', 'مفتوح')}

━━━━━━━━━━━━━━━

💡 *للتقدم بعرض:*
رد على هذه الرسالة بالتنسيق التالي:

*السعر:* [مبلغك]
*ملاحظات:* [إن وجدت]

مثال:
السعر: 500 ريال
ملاحظات: متفرغ غداً

⏰ العرض مفتوح لمدة ساعتين
        """.strip()
        
        return self.send_whatsapp(vendor_phone, message)
    
    # ============================================
    # Notification Messages
    # ============================================
    
    def send_first_offer_notification(
        self,
        to_number: str,
        provider_name: str,
        offer_page_url: str
    ) -> Dict[str, Any]:
        """
        إشعار أول عرض وصل
        """
        msg = f"""
🎉 *وصل أول عرض!*

مزود مهتم بخدمتك: {provider_name}

🔗 *شوف العروض:*
{offer_page_url}

📊 الصفحة تتحدث تلقائياً عند وصول عروض جديدة
        """.strip()
        
        return self.send_whatsapp(to_number, msg)
    
    def send_offers_summary(
        self,
        to_number: str,
        offers_count: int,
        best_offer: Dict[str, Any],
        offer_page_url: str
    ) -> Dict[str, Any]:
        """
        ملخص العروض عند الاكتمال
        """
        msg = f"""
📊 *تم استلام {offers_count} عروض!*

🏆 *الأفضل:*
{best_offer.get('provider_name', 'مزود')}
💰 {best_offer.get('price', 'غير محدد')}
⭐ {best_offer.get('rating', 'جديد')}

🔗 *شوف كل العروض:*
{offer_page_url}

📞 تواصل مباشرة مع المزود اللي يناسبك!
        """.strip()
        
        return self.send_whatsapp(to_number, msg)
    
    def send_expiry_reminder(
        self,
        to_number: str,
        offers_count: int,
        minutes_left: int,
        offer_page_url: str
    ) -> Dict[str, Any]:
        """
        تذكير قبل انتهاء صلاحية الصفحة
        """
        msg = f"""
⏰ *تذكير!*

صفحة عروضك تنتهي خلال *{minutes_left} دقيقة*!

📍 فيه {offers_count} عروض بانتظارك

🔗 {offer_page_url}

💡 لا تفوت الفرصة - تواصل مع المزود الآن!
        """.strip()
        
        return self.send_whatsapp(to_number, msg)
    
    # ============================================
    # Direct Contact Card
    # ============================================
    
    def send_direct_contact_card(
        self,
        customer_phone: str,
        vendor_data: Dict[str, Any],
        offer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        بطاقة تواصل مباشر مع المزود
        """
        vendor_phone = vendor_data.get('phone', '').replace('+', '').replace(' ', '').replace('whatsapp:', '')
        
        card_body = f"""
📋 *عرض من {vendor_data.get('name', 'مزود')}*

💰 السعر: {offer_data.get('price', 'غير محدد')} ريال
⭐ التقييم: {vendor_data.get('rating', 'جديد')}
📍 المدينة: {vendor_data.get('city', 'غير محدد')}

📝 *ملاحظات:*
{offer_data.get('notes') or 'لا توجد'}

━━━━━━━━━━━━━━━

🔗 *تواصل مباشر:*
📞 اتصال: tel:{vendor_phone}
💬 واتساب: wa.me/{vendor_phone}

🦦 شكراً لاستخدامك هدهد!
        """.strip()
        
        return self.send_whatsapp(
            to_number=customer_phone,
            body=card_body
            # media_url معطل - يسبب تكاليف SMS إضافية
            # media_url=vendor_data.get('portfolio_image')
        )


# إنشاء instance واحد
twilio_service = TwilioService()
