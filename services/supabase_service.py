"""
Supabase Database Service
خدمة قاعدة البيانات Supabase - النسخة المحسنة
"""

import os
import httpx
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from config import SUPABASE_URL, SUPABASE_KEY, APP_URL

# Category slug mapping
CATEGORY_SLUGS = {
    "سباكة": "plumbing",
    "كهرباء": "electrical",
    "تنظيف": "cleaning",
    "تكييف": "ac",
    "نقل عفش": "moving",
    "صباغة": "painting",
    "نجارة": "maintenance",
    "سباك": "plumbing",
    "كهربائي": "electrical",
    "مكيفات": "ac",
}


class SupabaseService:
    """
    خدمة قاعدة البيانات Supabase
    يستخدم HTTP API مباشرة
    """
    
    def __init__(self):
        self.url = SUPABASE_URL
        self.key = SUPABASE_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        if self.url and self.key:
            print(f"✅ [Supabase] Service initialized")
            print(f"🌐 [Supabase] URL: {self.url}")
        else:
            print("⚠️ [Supabase] No credentials - Running in Mock Mode")
    
    def _normalize_phone(self, phone: str) -> str:
        """ت normalize رقم الهاتف"""
        if not phone:
            return phone
        return phone.replace(" ", "").replace("+", "").replace("whatsapp:", "")
    
    def _get_category_slug(self, service_type: str) -> Optional[str]:
        """تحويل اسم الخدمة إلى slug"""
        # بحث مباشر
        if service_type in CATEGORY_SLUGS:
            return CATEGORY_SLUGS[service_type]
        
        # بحث جزئي
        for key, slug in CATEGORY_SLUGS.items():
            if key in service_type or service_type in key:
                return slug
        
        return None
    
    # ============================================
    # Conversations
    # ============================================
    
    async def create_conversation(
        self,
        customer_phone: str,
        initial_message: str
    ) -> Dict[str, Any]:
        """إنشاء محادثة جديدة"""
        if not self.url:
            return {"success": True, "conversation_id": "mock-conv-123"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/conversations",
                    headers=self.headers,
                    json={
                        "customer_phone": self._normalize_phone(customer_phone),
                        "status": "new",
                        "context": {
                            "initial_message": initial_message,
                            "stage": "collecting"
                        }
                    },
                    timeout=30.0
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    return {
                        "success": True,
                        "conversation_id": data[0]["id"]
                    }
                else:
                    print(f"❌ [Supabase] Create conversation error: {response.status_code}")
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            print(f"❌ [Supabase] Create conversation error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """الحصول على محادثة"""
        if not self.url:
            return {"id": conversation_id, "status": "collecting", "context": {}}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/conversations?id=eq.{conversation_id}&select=*",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data[0] if data else None
                    
        except Exception as e:
            print(f"❌ [Supabase] Get conversation error: {e}")
        return None
    
    async def get_conversation_by_phone(self, customer_phone: str) -> Optional[Dict]:
        """الحصول على آخر محادثة للعميل"""
        if not self.url:
            return None
        
        phone = self._normalize_phone(customer_phone)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/conversations?customer_phone=eq.{phone}&select=*&order=created_at.desc&limit=1",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data[0] if data else None
                    
        except Exception as e:
            print(f"❌ [Supabase] Get conversation by phone error: {e}")
        return None
    
    async def update_conversation(
        self,
        conversation_id: str,
        status: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> bool:
        """تحديث المحادثة"""
        if not self.url:
            return True
        
        try:
            update_data = {}
            if status:
                update_data["status"] = status
            if context:
                update_data["context"] = context
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.url}/rest/v1/conversations?id=eq.{conversation_id}",
                    headers=self.headers,
                    json=update_data,
                    timeout=10.0
                )
                return response.status_code in [200, 204]
                
        except Exception as e:
            print(f"❌ [Supabase] Update conversation error: {e}")
            return False
    
    # ============================================
    # Messages
    # ============================================
    
    async def save_message(
        self,
        conversation_id: str,
        sender: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """حفظ رسالة"""
        if not self.url:
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/messages",
                    headers=self.headers,
                    json={
                        "conversation_id": conversation_id,
                        "sender": sender,
                        "content": content,
                        "metadata": metadata or {}
                    },
                    timeout=10.0
                )
                return response.status_code in [200, 201]
                
        except Exception as e:
            print(f"❌ [Supabase] Save message error: {e}")
            return False
    
    async def get_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """الحصول على رسائل المحادثة"""
        if not self.url:
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/messages?conversation_id=eq.{conversation_id}&select=*&order=created_at.asc&limit={limit}",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                    
        except Exception as e:
            print(f"❌ [Supabase] Get messages error: {e}")
        return []
    
    # ============================================
    # Service Requests
    # ============================================
    
    async def create_service_request(
        self,
        conversation_id: str,
        customer_phone: str,
        service_type: str,
        city: str,
        details: Optional[str] = None,
        budget: Optional[str] = None
    ) -> Dict[str, Any]:
        """إنشاء طلب خدمة جديد"""
        request_id = str(uuid.uuid4())
        category_slug = self._get_category_slug(service_type)
        
        if not self.url:
            return {
                "success": True,
                "request_id": request_id,
                "offers_url": f"{APP_URL}/offers/{request_id}"
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/service_requests",
                    headers=self.headers,
                    json={
                        "id": request_id,
                        "conversation_id": conversation_id,
                        "customer_phone": self._normalize_phone(customer_phone),
                        "description": details or f"{service_type} في {city}",
                        "category_slug": category_slug,
                        "city": city,
                        "status": "new"
                    },
                    timeout=30.0
                )
                
                print(f"📊 [Supabase] Create request response: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    return {
                        "success": True,
                        "request_id": request_id,
                        "offers_url": f"{APP_URL}/offers/{request_id}"
                    }
                else:
                    print(f"❌ [Supabase] Create request failed: {response.text}")
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            print(f"❌ [Supabase] Create service request error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_service_request(self, request_id: str) -> Optional[Dict]:
        """الحصول على طلب خدمة"""
        if not self.url:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/service_requests?id=eq.{request_id}&select=*",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data[0] if data else None
                    
        except Exception as e:
            print(f"❌ [Supabase] Get service request error: {e}")
        return None
    
    # ============================================
    # Providers - المزودين
    # ============================================
    
    async def search_providers(
        self,
        service_type: str,
        city: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        البحث عن مزودين مطابقين
        
        Args:
            service_type: نوع الخدمة (مثل: سباكة، كهرباء)
            city: المدينة
            limit: أقصى عدد من النتائج
        """
        if not self.url:
            print("⚠️ [Supabase] No URL - returning mock providers")
            return []
        
        # تحويل الخدمة إلى slug
        category_slug = self._get_category_slug(service_type)
        
        if not category_slug:
            print(f"⚠️ [Supabase] Unknown service type: {service_type}")
            # نحاول البحث بدون تصنيف
            category_slug = None
        
        try:
            # بناء الاستعلام
            base_url = f"{self.url}/rest/v1/providers?status=eq.active&select=*&order=rating.desc&limit={limit}"
            
            # إضافة فلتر المدينة
            if city:
                base_url += f"&city=ilike.%25{city}%25"
            
            # إضافة فلتر التصنيف
            if category_slug:
                base_url += f"&category_slug=eq.{category_slug}"
            
            print(f"🔍 [Supabase] Searching providers: {base_url}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    base_url,
                    headers=self.headers,
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    providers = response.json()
                    print(f"✅ [Supabase] Found {len(providers)} providers")
                    return providers
                else:
                    print(f"❌ [Supabase] Search failed: {response.status_code}")
                    return []
                    
        except Exception as e:
            print(f"❌ [Supabase] Search providers error: {e}")
            return []
    
    async def get_provider_by_phone(self, phone: str) -> Optional[Dict]:
        """الحصول على مزود برقم الهاتف"""
        if not self.url:
            return None
        
        clean_phone = self._normalize_phone(phone)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/providers?whatsapp=eq.{clean_phone}&select=*&limit=1",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data[0] if data else None
                    
        except Exception as e:
            print(f"❌ [Supabase] Get provider by phone error: {e}")
        return None
    
    # ============================================
    # Provider Offers - عروض المزودين
    # ============================================
    
    async def save_provider_offer(
        self,
        request_id: str,
        provider_id: str,
        price: str,
        notes: Optional[str] = None,
        estimated_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """حفظ عرض مزود"""
        if not self.url:
            return {"success": True, "offer_id": "mock-offer-123"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/provider_offers",
                    headers=self.headers,
                    json={
                        "request_id": request_id,
                        "provider_id": provider_id,
                        "price": price,
                        "notes": notes,
                        "estimated_time": estimated_time,
                        "status": "pending"
                    },
                    timeout=10.0
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    return {
                        "success": True,
                        "offer_id": data[0]["id"]
                    }
                else:
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            print(f"❌ [Supabase] Save provider offer error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_offers_for_request(self, request_id: str) -> List[Dict]:
        """الحصول على عروض طلب معين"""
        if not self.url:
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/provider_offers?request_id=eq.{request_id}&select=*,providers(id,business_name,whatsapp,rating,review_count,total_jobs)&order=created_at.asc",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                    
        except Exception as e:
            print(f"❌ [Supabase] Get offers error: {e}")
        return []
    
    async def update_offer_status(self, offer_id: str, status: str) -> bool:
        """تحديث حالة العرض"""
        if not self.url:
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.url}/rest/v1/provider_offers?id=eq.{offer_id}",
                    headers=self.headers,
                    json={"status": status},
                    timeout=10.0
                )
                return response.status_code in [200, 204]
                
        except Exception as e:
            print(f"❌ [Supabase] Update offer status error: {e}")
            return False
    
    # ============================================
    # Provider Request Tracking
    # ============================================
    
    async def get_active_request_for_provider(self, provider_id: str) -> Optional[str]:
        """الحصول على الطلب النشط للمزود"""
        if not self.url:
            return None
        
        try:
            # البحث عن طلبات أُرسلت للمزود ولم يقدم عرضاً عليها
            async with httpx.AsyncClient() as client:
                # أولاً نبحث عن الطلبات الجديدة التي تطابق تخصص المزود
                response = await client.get(
                    f"{self.url}/rest/v1/provider_requests?provider_id=eq.{provider_id}&status=eq.sent&select=request_id&order=created_at.desc&limit=1",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        return data[0].get("request_id")
                    
        except Exception as e:
            print(f"❌ [Supabase] Get active request error: {e}")
        return None
    
    async def log_provider_request(
        self,
        request_id: str,
        provider_id: str
    ) -> bool:
        """تسجيل أن الطلب أُرسل للمزود"""
        if not self.url:
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/provider_requests",
                    headers=self.headers,
                    json={
                        "request_id": request_id,
                        "provider_id": provider_id,
                        "status": "sent"
                    },
                    timeout=10.0
                )
                return response.status_code in [200, 201]
                
        except Exception as e:
            print(f"❌ [Supabase] Log provider request error: {e}")
            return False


# إنشاء instance واحد
supabase_service = SupabaseService()
