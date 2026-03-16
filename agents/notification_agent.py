"""
Notification Agent - وكيل الإشعارات
الوكيل الرابع - يرسل الإشعارات للعملاء
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
from services.twilio_service import twilio_service
from services.supabase_service import supabase_service
from services.deepseek_service import deepseek_service
from config import NOTIFICATION_REMINDER_MINUTES, APP_URL


class NotificationAgent:
    """
    وكيل الإشعارات - الوكيل الرابع في النظام
    
    المسؤوليات:
    1. إرسال إشعار فوري عند أول عرض
    2. إرسال ملخص عند اكتمال العروض
    3. إرسال تذكير قبل انتهاء صلاحية الصفحة
    4. إدارة timeline الإشعارات
    """
    
    # أنواع الإشعارات
    FIRST_OFFER = "first_offer"
    OFFERS_SUMMARY = "offers_summary"
    EXPIRY_REMINDER = "expiry_reminder"
    
    def __init__(self):
        self.notification_queue: Dict[str, Dict] = {}
        self.sent_notifications: Dict[str, List[str]] = {}
    
    async def send_first_offer_notification(
        self,
        customer_phone: str,
        provider_name: str,
        offer_page_slug: str
    ) -> Dict[str, Any]:
        """
        إرسال إشعار أول عرض
        
        Args:
            customer_phone: رقم العميل
            provider_name: اسم المزود
            offer_page_slug: slug صفحة العروض
        
        Returns:
            {"success": bool, "message_sid": str}
        """
        print(f"🔔 [NotificationAgent] First offer notification to {customer_phone}")
        
        # التحقق من عدم إرسال الإشعار مسبقاً
        if self._was_notification_sent(customer_phone, self.FIRST_OFFER):
            return {"success": True, "already_sent": True}
        
        offer_url = f"{APP_URL}/offers/{offer_page_slug}"
        
        result = twilio_service.send_first_offer_notification(
            to_number=customer_phone,
            provider_name=provider_name,
            offer_page_url=offer_url
        )
        
        if result.get("status") in ["sent", "mocked"]:
            self._mark_notification_sent(customer_phone, self.FIRST_OFFER)
        
        return {
            "success": result.get("status") in ["sent", "mocked"],
            "message_sid": result.get("sid")
        }
    
    async def send_offers_summary(
        self,
        customer_phone: str,
        offers: List[Dict],
        offer_page_slug: str
    ) -> Dict[str, Any]:
        """
        إرسال ملخص العروض
        
        Args:
            customer_phone: رقم العميل
            offers: قائمة العروض
            offer_page_slug: slug صفحة العروض
        
        Returns:
            {"success": bool, "message_sid": str}
        """
        print(f"📋 [NotificationAgent] Summary notification to {customer_phone}")
        
        if not offers:
            return {"success": False, "error": "لا توجد عروض"}
        
        # تحديد أفضل عرض
        best_offer = offers[0] if offers else None
        
        offer_url = f"{APP_URL}/offers/{offer_page_slug}"
        
        result = twilio_service.send_offers_summary(
            to_number=customer_phone,
            offers_count=len(offers),
            best_offer={
                "provider_name": best_offer.get("provider_name", "مزود"),
                "price": best_offer.get("price", "غير محدد"),
                "rating": best_offer.get("provider_rating", "جديد")
            },
            offer_page_url=offer_url
        )
        
        if result.get("status") in ["sent", "mocked"]:
            self._mark_notification_sent(customer_phone, self.OFFERS_SUMMARY)
        
        return {
            "success": result.get("status") in ["sent", "mocked"],
            "message_sid": result.get("sid")
        }
    
    async def send_expiry_reminder(
        self,
        customer_phone: str,
        offers_count: int,
        minutes_left: int,
        offer_page_slug: str
    ) -> Dict[str, Any]:
        """
        إرسال تذكير قبل انتهاء الصلاحية
        
        Args:
            customer_phone: رقم العميل
            offers_count: عدد العروض
            minutes_left: الدقائق المتبقية
            offer_page_slug: slug صفحة العروض
        
        Returns:
            {"success": bool, "message_sid": str}
        """
        print(f"⏰ [NotificationAgent] Expiry reminder to {customer_phone}")
        
        offer_url = f"{APP_URL}/offers/{offer_page_slug}"
        
        result = twilio_service.send_expiry_reminder(
            to_number=customer_phone,
            offers_count=offers_count,
            minutes_left=minutes_left,
            offer_page_url=offer_url
        )
        
        if result.get("status") in ["sent", "mocked"]:
            self._mark_notification_sent(customer_phone, self.EXPIRY_REMINDER)
        
        return {
            "success": result.get("status") in ["sent", "mocked"],
            "message_sid": result.get("sid")
        }
    
    async def schedule_reminder(
        self,
        customer_phone: str,
        request_id: str,
        expires_at: datetime,
        offer_page_slug: str
    ):
        """
        جدولة تذكير قبل انتهاء الصلاحية
        
        Args:
            customer_phone: رقم العميل
            request_id: معرف الطلب
            expires_at: وقت انتهاء الصلاحية
            offer_page_slug: slug صفحة العروض
        """
        # حساب الوقت المتبقي
        reminder_time = expires_at - timedelta(minutes=NOTIFICATION_REMINDER_MINUTES)
        now = datetime.utcnow()
        
        if reminder_time > now:
            # إضافة للمهام المجدولة
            self.notification_queue[request_id] = {
                "customer_phone": customer_phone,
                "reminder_time": reminder_time,
                "offer_page_slug": offer_page_slug
            }
            
            print(f"📅 [NotificationAgent] Reminder scheduled for {reminder_time}")
    
    async def process_scheduled_reminders(self):
        """
        معالجة التذكيرات المجدولة
        """
        now = datetime.utcnow()
        
        for request_id, reminder_data in list(self.notification_queue.items()):
            if reminder_data["reminder_time"] <= now:
                # وقت التذكير
                # جلب عدد العروض
                offers = await supabase_service.get_offers_for_request(request_id)
                
                await self.send_expiry_reminder(
                    customer_phone=reminder_data["customer_phone"],
                    offers_count=len(offers),
                    minutes_left=NOTIFICATION_REMINDER_MINUTES,
                    offer_page_slug=reminder_data["offer_page_slug"]
                )
                
                # إزالة من القائمة
                del self.notification_queue[request_id]
    
    async def notify_on_new_offer(
        self,
        request_id: str,
        customer_phone: str,
        provider_name: str,
        offer_page_slug: str
    ) -> Dict[str, Any]:
        """
        إشعار عند وصول عرض جديد
        
        Args:
            request_id: معرف الطلب
            customer_phone: رقم العميل
            provider_name: اسم المزود
            offer_page_slug: slug صفحة العروض
        
        Returns:
            {"success": bool}
        """
        # التحقق من عدد العروض
        offers = await supabase_service.get_offers_for_request(request_id)
        
        # أول عرض - إرسال إشعار فوري
        if len(offers) == 1:
            return await self.send_first_offer_notification(
                customer_phone=customer_phone,
                provider_name=provider_name,
                offer_page_slug=offer_page_slug
            )
        
        # عروض متعددة - يمكن إرسال ملخص أو تحديث
        # للآن، نكتفي بالإشعار الأول فقط
        
        return {"success": True, "notification_type": "update_only"}
    
    def _was_notification_sent(self, customer_phone: str, notification_type: str) -> bool:
        """التحقق إذا تم إرسال الإشعار مسبقاً"""
        key = f"{customer_phone}_{notification_type}"
        return key in str(self.sent_notifications.get(customer_phone, []))
    
    def _mark_notification_sent(self, customer_phone: str, notification_type: str):
        """تسجيل أن الإشعار تم إرساله"""
        if customer_phone not in self.sent_notifications:
            self.sent_notifications[customer_phone] = []
        self.sent_notifications[customer_phone].append(notification_type)
    
    def clear_notifications(self, customer_phone: str = None):
        """مسح سجلات الإشعارات"""
        if customer_phone:
            self.sent_notifications.pop(customer_phone, None)
        else:
            self.sent_notifications.clear()


# إنشاء instance واحد
notification_agent = NotificationAgent()
