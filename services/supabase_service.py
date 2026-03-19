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

# Platform URL for offers pages
PLATFORM_URL = APP_URL

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
        """إنشاء محادثة جديدة أو استرجاع الموجودة"""
        if not self.url:
            return {"success": True, "conversation_id": "mock-conv-123"}
        
        phone = self._normalize_phone(customer_phone)
        
        try:
            async with httpx.AsyncClient() as client:
                # أولاً نبحث عن محادثة موجودة - استخدام phone فقط
                existing = await client.get(
                    f"{self.url}/rest/v1/conversations?phone=eq.{phone}&select=*&order=created_at.desc&limit=1",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if existing.status_code == 200:
                    existing_data = existing.json()
                    if existing_data:
                        conv = existing_data[0]
                        # تحديث المحادثة الموجودة
                        await client.patch(
                            f"{self.url}/rest/v1/conversations?id=eq.{conv['id']}",
                            headers=self.headers,
                            json={"status": "collecting", "metadata": {}},
                            timeout=10.0
                        )
                        return {"success": True, "conversation_id": conv["id"], "is_new": False}
                
                # إنشاء محادثة جديدة - استخدام phone و metadata
                response = await client.post(
                    f"{self.url}/rest/v1/conversations",
                    headers=self.headers,
                    json={
                        "phone": phone,
                        "type": "customer",
                        "status": "new",
                        "metadata": {"initial_message": initial_message, "stage": "collecting"}
                    },
                    timeout=30.0
                )
                
                print(f"📊 [Supabase] Create conversation response: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    return {"success": True, "conversation_id": data[0]["id"], "is_new": True}
                else:
                    print(f"❌ [Supabase] Create conversation error: {response.status_code} - {response.text}")
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
                # البحث باستخدام phone
                response = await client.get(
                    f"{self.url}/rest/v1/conversations?phone=eq.{phone}&select=*&order=created_at.desc&limit=1",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        conv = data[0]
                        # تحويل metadata إلى context للتوافقية مع الكود
                        if not conv.get("context"):
                            conv["context"] = conv.get("metadata") or {}
                        return conv
                    return None
                    
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
                # استخدام metadata بدلاً من context
                update_data["metadata"] = context
            
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
        
        # تحويل sender إلى direction للتوافقية
        direction = "inbound" if sender == "customer" else "outbound"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/messages",
                    headers=self.headers,
                    json={
                        "conversation_id": conversation_id,
                        "sender": sender,
                        "direction": direction,  # للتوافقية
                        "content": content,
                        "metadata": metadata or {},
                        "message_type": "text"
                    },
                    timeout=10.0
                )
                if response.status_code not in [200, 201]:
                    print(f"❌ [Supabase] Save message error: {response.status_code} - {response.text}")
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
    
    async def get_active_request_for_customer(self, customer_phone: str) -> Optional[Dict]:
        """
        الحصول على الطلب النشط للعميل (غير منتهي الصلاحية)
        يرجع None إذا لم يكن هناك طلب نشط
        """
        if not self.url:
            return None
        
        phone = self._normalize_phone(customer_phone)
        
        try:
            async with httpx.AsyncClient() as client:
                # البحث عن طلبات نشطة (new أو matched) وغير منتهية
                response = await client.get(
                    f"{self.url}/rest/v1/service_requests?"
                    f"customer_phone=eq.{phone}&"
                    f"status=in.(new,matched,processing)&"
                    f"select=*&order=created_at.desc&limit=1",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        request = data[0]
                        # التحقق من انتهاء الصلاحية
                        expires_at = request.get('expires_at')
                        if expires_at:
                            from datetime import datetime
                            expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                            if datetime.now(expiry_time.tzinfo) > expiry_time:
                                # الطلب منتهي الصلاحية
                                print(f"⏰ [Supabase] Request {request['id']} has expired")
                                # تحديث الحالة
                                await client.patch(
                                    f"{self.url}/rest/v1/service_requests?id=eq.{request['id']}",
                                    headers=self.headers,
                                    json={"status": "expired"},
                                    timeout=10.0
                                )
                                return None
                        return request
                    return None
                    
        except Exception as e:
            print(f"❌ [Supabase] Get active request error: {e}")
        return None
    
    async def can_create_new_request(self, customer_phone: str) -> Dict[str, Any]:
        """
        التحقق مما إذا كان العميل يمكنه إنشاء طلب جديد
        """
        active_request = await self.get_active_request_for_customer(customer_phone)
        
        if active_request:
            return {
                "can_create": False,
                "reason": "has_active_request",
                "active_request_id": active_request.get("id"),
                "active_request_status": active_request.get("status"),
                "expires_at": active_request.get("expires_at"),
                "offers_count": active_request.get("offers_count", 0),
                "message": f"لديك طلب نشط بالفعل. انتظر انتهاء صلاحيته أو راجع العروض."
            }
        
        return {
            "can_create": True,
            "reason": None
        }
    
    async def expire_old_requests(self) -> int:
        """
        تحديث جميع الطلبات منتهية الصلاحية
        """
        if not self.url:
            return 0
        
        try:
            async with httpx.AsyncClient() as client:
                # استدعاء الـ function
                response = await client.post(
                    f"{self.url}/rest/v1/rpc/expire_old_requests",
                    headers=self.headers,
                    json={},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    print("✅ [Supabase] Expired old requests")
                    return 1
                return 0
                
        except Exception as e:
            print(f"❌ [Supabase] Expire requests error: {e}")
            return 0
    
    async def cancel_service_request(self, request_id: str, customer_phone: str = None) -> Dict[str, Any]:
        """
        إلغاء طلب خدمة
        
        Args:
            request_id: معرف الطلب
            customer_phone: رقم هاتف العميل (للتحقق)
        
        Returns:
            Dict with success status
        """
        if not self.url:
            return {"success": True, "message": "Request cancelled (mock)"}
        
        try:
            async with httpx.AsyncClient() as client:
                # التحقق من الطلب أولاً
                check_response = await client.get(
                    f"{self.url}/rest/v1/service_requests?id=eq.{request_id}&select=*",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if check_response.status_code != 200:
                    return {"success": False, "error": "Request not found"}
                
                requests = check_response.json()
                if not requests:
                    return {"success": False, "error": "Request not found"}
                
                request = requests[0]
                
                # التحقق من أن الطلب يمكن إلغاؤه
                # يمكن إلغاء الطلبات: new, matched, processing, expired
                if request.get("status") not in ["new", "matched", "processing", "expired"]:
                    return {
                        "success": False, 
                        "error": f"لا يمكن إلغاء طلب بحالة: {request.get('status')}"
                    }
                
                # إذا كان الطلب expired، نعتبره ملغي تلقائياً
                if request.get("status") == "expired":
                    return {
                        "success": True,
                        "message": "الطلب منتهي الصلاحية بالفعل",
                        "request_id": request_id,
                        "already_expired": True
                    }
                
                # تحديث حالة الطلب
                update_response = await client.patch(
                    f"{self.url}/rest/v1/service_requests?id=eq.{request_id}",
                    headers=self.headers,
                    json={
                        "status": "cancelled",
                        "notes": "Cancelled by customer via WhatsApp"
                    },
                    timeout=10.0
                )
                
                if update_response.status_code in [200, 204]:
                    print(f"✅ [Supabase] Request {request_id} cancelled")
                    return {
                        "success": True,
                        "message": "Request cancelled successfully",
                        "request_id": request_id
                    }
                else:
                    return {"success": False, "error": update_response.text}
                    
        except Exception as e:
            print(f"❌ [Supabase] Cancel request error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_customer_active_request_id(self, customer_phone: str) -> Optional[str]:
        """
        الحصول على معرف الطلب النشط للعميل
        """
        active = await self.get_active_request_for_customer(customer_phone)
        if active:
            return active.get("id")
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
            # بناء الاستعلام - استخدام status=eq.active وليس status=active
            base_url = f"{self.url}/rest/v1/providers?status=eq.active&select=*&order=rating.desc&limit={limit}"
            
            # إضافة فلتر المدينة (ilike للبحث الجزئي)
            if city:
                # تنسيق ilike الصحيح في PostgREST: city=ilike.*النص*
                base_url += f"&city=ilike.*{city}*"
            
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
        
        # استخراج القيمة الرقمية من النص العربي
        price_decimal = None
        try:
            import re
            numbers = re.findall(r'[\d,]+\.?\d*', price.replace(',', ''))
            if numbers:
                price_decimal = float(numbers[0].replace(',', ''))
        except:
            pass
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/provider_offers",
                    headers=self.headers,
                    json={
                        "request_id": request_id,
                        "provider_id": provider_id,
                        "price": price_decimal,
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
                    print(f"❌ [Supabase] Save offer failed: {response.status_code} - {response.text}")
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
    
    async def get_active_request_for_provider(self, provider_id: str) -> Optional[Dict]:
        """
        الحصول على الطلب النشط للمزود مع تفاصيل كاملة
        
        Returns:
            Dict with request_id, customer_phone, description, city, etc.
        """
        if not self.url:
            return None
        
        try:
            # البحث عن طلبات نشطة في service_requests
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/service_requests?status=eq.new&select=*&limit=10",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    requests = response.json()
                    for req in requests:
                        matched = req.get("matched_providers") or []
                        if provider_id in matched:
                            # إرجاع الطلب مع معرف المزود
                            return {
                                "request_id": req.get("id"),
                                "customer_phone": req.get("customer_phone"),
                                "city": req.get("city"),
                                "category_slug": req.get("category_slug"),
                                "description": req.get("description"),
                                **req
                            }
                    
        except Exception as e:
            print(f"❌ [Supabase] Get active request error: {e}")
        return None
    
    async def log_provider_request(
        self,
        request_id: str,
        provider_id: str
    ) -> bool:
        """تسجيل أن الطلب أُرسل للمزود - تحديث matched_providers"""
        if not self.url:
            return True
        
        try:
            # الحصول على matched_providers الحالية
            async with httpx.AsyncClient() as client:
                get_response = await client.get(
                    f"{self.url}/rest/v1/service_requests?id=eq.{request_id}&select=matched_providers",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if get_response.status_code == 200:
                    data = get_response.json()
                    if data:
                        current_matched = data[0].get("matched_providers") or []
                        if provider_id not in current_matched:
                            current_matched.append(provider_id)
                            
                            # تحديث الطلب
                            update_response = await client.patch(
                                f"{self.url}/rest/v1/service_requests?id=eq.{request_id}",
                                headers=self.headers,
                                json={"matched_providers": current_matched},
                                timeout=10.0
                            )
                            return update_response.status_code in [200, 204]
                
                return True
                
        except Exception as e:
            print(f"❌ [Supabase] Log provider request error: {e}")
            return False
    
    async def get_request_with_offers(self, request_id: str) -> Optional[Dict]:
        """الحصول على الطلب مع جميع عروضه"""
        if not self.url:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                # الحصول على الطلب
                response = await client.get(
                    f"{self.url}/rest/v1/service_requests?id=eq.{request_id}&select=*",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    requests = response.json()
                    if requests:
                        request_data = requests[0]
                        
                        # الحصول على العروض
                        offers_response = await client.get(
                            f"{self.url}/rest/v1/provider_offers?request_id=eq.{request_id}&select=*&order=created_at.asc",
                            headers=self.headers,
                            timeout=10.0
                        )
                        
                        if offers_response.status_code == 200:
                            request_data["offers"] = offers_response.json()
                        else:
                            request_data["offers"] = []
                        
                        return request_data
                    
        except Exception as e:
            print(f"❌ [Supabase] Get request with offers error: {e}")
        return None


    # ============================================
    # Neighborhoods & Sectors - الأحياء والقطاعات
    # ============================================
    
    async def get_neighborhood_info(self, city: str, neighborhood_name: str) -> Optional[Dict]:
        """
        الحصول على معلومات الحي والقطاع
        
        Returns:
            Dict with neighborhood_id, sector_id, sector_code
        """
        if not self.url:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                # البحث عن الحي
                response = await client.get(
                    f"{self.url}/rest/v1/neighborhoods?"
                    f"city=ilike.*{city}*&"
                    f"name=ilike.*{neighborhood_name}*&"
                    f"select=id,name,city,sector_id,sectors(id,sector_code,sector_name)",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        return data[0]
                    return None
                    
        except Exception as e:
            print(f"❌ [Supabase] Get neighborhood error: {e}")
        return None
    
    async def find_matching_neighborhood(self, city: str, text: str) -> Optional[Dict]:
        """
        البحث عن حي مطابق من نص
        
        Args:
            city: المدينة
            text: النص الذي قد يحتوي على اسم الحي
        
        Returns:
            Dict with neighborhood info
        """
        if not self.url:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                # جلب كل أحياء المدينة
                response = await client.get(
                    f"{self.url}/rest/v1/neighborhoods?"
                    f"city=ilike.*{city}*&"
                    f"select=id,name,sector_id,sectors(id,sector_code)",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    neighborhoods = response.json()
                    
                    # البحث في النص
                    text_lower = text.lower()
                    for nb in neighborhoods:
                        if nb['name'] in text or nb['name'].lower() in text_lower:
                            return nb
                    
                    # البحث الجزئي
                    for nb in neighborhoods:
                        # البحث عن أي جزء من اسم الحي
                        name_parts = nb['name'].split()
                        for part in name_parts:
                            if len(part) > 2 and part in text:
                                return nb
                    
                    return None
                    
        except Exception as e:
            print(f"❌ [Supabase] Find neighborhood error: {e}")
        return None
    
    async def get_providers_in_sector(
        self,
        sector_id: str,
        category_slug: str,
        limit: int = 7
    ) -> List[Dict]:
        """
        الحصول على مزودين في قطاع معين
        """
        if not self.url:
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/providers?"
                    f"sector_id=eq.{sector_id}&"
                    f"category_slug=eq.{category_slug}&"
                    f"status=eq.active&"
                    f"select=*&order=rating.desc&limit={limit}",
                    headers=self.headers,
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    return response.json()
                    
        except Exception as e:
            print(f"❌ [Supabase] Get providers in sector error: {e}")
        return []
    
    async def get_providers_in_nearby_sectors(
        self,
        sector_code: str,
        category_slug: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        الحصول على مزودين في القطاعات المجاورة (نفس المدينة)
        
        Args:
            sector_code: كود القطاع (مثل: RYD-N)
            category_slug: تصنيف الخدمة
            limit: العدد الأقصى
        """
        if not self.url:
            return []
        
        try:
            # استخراج المدينة من الكود
            city_code = sector_code.split('-')[0]
            city_map = {
                'RYD': 'الرياض',
                'JED': 'جدة',
                'DMM': 'الدمام',
                'MKA': 'مكة',
                'MED': 'المدينة'
            }
            city = city_map.get(city_code)
            
            if not city:
                return []
            
            async with httpx.AsyncClient() as client:
                # البحث في نفس المدينة لكن قطاع مختلف
                response = await client.get(
                    f"{self.url}/rest/v1/providers?"
                    f"city=ilike.*{city}*&"
                    f"category_slug=eq.{category_slug}&"
                    f"status=eq.active&"
                    f"select=*&order=rating.desc&limit={limit}",
                    headers=self.headers,
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    providers = response.json()
                    # استبعاد مزودي نفس القطاع (تم البحث عنهم سابقاً)
                    return [p for p in providers if p.get('sector_id') != sector_code][:limit]
                    
        except Exception as e:
            print(f"❌ [Supabase] Get nearby providers error: {e}")
        return []

    # ============================================
    # Provider Offer Links - روابط المزودين
    # ============================================
    
    async def create_provider_offer_links(
        self,
        request_id: str,
        provider_ids: List[str],
        expiry_hours: int = 2
    ) -> List[Dict]:
        """
        إنشاء روابط فريدة لكل مزود
        
        Args:
            request_id: معرف الطلب
            provider_ids: قائمة معرفات المزودين
            expiry_hours: ساعات انتهاء الصلاحية
        
        Returns:
            List of dicts with provider_id, token, link_url
        """
        if not self.url:
            # إرجاع روابط وهمية
            return [
                {
                    "provider_id": pid,
                    "token": f"mock-token-{pid[:8]}",
                    "link_url": f"{APP_URL}/provider-offer/mock-token-{pid[:8]}"
                }
                for pid in provider_ids
            ]
        
        import secrets
        
        results = []
        
        try:
            async with httpx.AsyncClient() as client:
                for provider_id in provider_ids:
                    # توليد توكن فريد
                    token = secrets.token_hex(32)
                    expires_at = (datetime.now() + timedelta(hours=expiry_hours)).isoformat()
                    
                    # إنشاء الرابط
                    response = await client.post(
                        f"{self.url}/rest/v1/provider_offer_links",
                        headers=self.headers,
                        json={
                            "request_id": request_id,
                            "provider_id": provider_id,
                            "unique_token": token,
                            "expires_at": expires_at,
                            "status": "pending"
                        },
                        timeout=10.0
                    )
                    
                    if response.status_code in [200, 201]:
                        results.append({
                            "provider_id": provider_id,
                            "token": token,
                            "link_url": f"{APP_URL}/provider-offer/{token}"
                        })
                    else:
                        print(f"❌ [Supabase] Create link failed for {provider_id}: {response.text}")
                    
            return results
                    
        except Exception as e:
            print(f"❌ [Supabase] Create offer links error: {e}")
            return results
    
    async def get_provider_offer_link(self, token: str) -> Optional[Dict]:
        """
        الحصول على معلومات رابط المزود
        """
        if not self.url:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/provider_offer_links?"
                    f"unique_token=eq.{token}&"
                    f"select=*",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data[0] if data else None
                    
        except Exception as e:
            print(f"❌ [Supabase] Get offer link error: {e}")
        return None
    
    async def get_active_links_for_request(self, request_id: str) -> List[Dict]:
        """
        الحصول على الروابط النشطة لطلب معين
        """
        if not self.url:
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/provider_offer_links?"
                    f"request_id=eq.{request_id}&"
                    f"status=in.(pending,viewed)&"
                    f"select=*",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                    
        except Exception as e:
            print(f"❌ [Supabase] Get active links error: {e}")
        return []

    # ============================================
    # Lifecycle Management - إدارة دورة الحياة
    # ============================================
    
    async def update_request_lifecycle(
        self,
        request_id: str,
        status: str,
        timeline_event: Optional[str] = None
    ) -> bool:
        """
        تحديث حالة دورة الحياة للطلب
        
        Args:
            request_id: معرف الطلب
            status: الحالة الجديدة
            timeline_event: اسم الحدث للتسجيل
        """
        if not self.url:
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                # الحصول على timeline الحالي
                get_response = await client.get(
                    f"{self.url}/rest/v1/service_requests?id=eq.{request_id}&select=status_timeline",
                    headers=self.headers,
                    timeout=10.0
                )
                
                timeline = {}
                if get_response.status_code == 200:
                    data = get_response.json()
                    if data:
                        timeline = data[0].get("status_timeline") or {}
                
                # إضافة الحدث الجديد
                if timeline_event:
                    timeline[timeline_event] = datetime.now().isoformat()
                
                # تحديث الطلب
                update_data = {
                    "lifecycle_status": status,
                    "status_timeline": timeline
                }
                
                # إضافة تاريخ انتهاء الصلاحية إذا لزم
                if status == "waiting_offers":
                    # 30 دقيقة لجمع العروض
                    update_data["expires_at"] = (datetime.now() + timedelta(minutes=30)).isoformat()
                elif status == "decision_time":
                    # 60 دقيقة لاتخاذ القرار
                    update_data["expires_at"] = (datetime.now() + timedelta(hours=1)).isoformat()
                
                response = await client.patch(
                    f"{self.url}/rest/v1/service_requests?id=eq.{request_id}",
                    headers=self.headers,
                    json=update_data,
                    timeout=10.0
                )
                
                return response.status_code in [200, 204]
                
        except Exception as e:
            print(f"❌ [Supabase] Update lifecycle error: {e}")
            return False
    
    async def schedule_notification(
        self,
        notification_type: str,
        target_phone: str,
        message: str,
        scheduled_at: datetime,
        request_id: Optional[str] = None,
        data: Optional[Dict] = None
    ) -> bool:
        """
        جدولة إشعار للإرسال لاحقاً
        """
        if not self.url:
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/scheduled_notifications",
                    headers=self.headers,
                    json={
                        "notification_type": notification_type,
                        "target_phone": target_phone,
                        "message": message,
                        "scheduled_at": scheduled_at.isoformat(),
                        "request_id": request_id,
                        "data": data or {}
                    },
                    timeout=10.0
                )
                
                return response.status_code in [200, 201]
                
        except Exception as e:
            print(f"❌ [Supabase] Schedule notification error: {e}")
            return False
    
    async def get_pending_notifications(self) -> List[Dict]:
        """
        الحصول على الإشعارات المعلقة للإرسال
        """
        if not self.url:
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/scheduled_notifications?"
                    f"status=eq.pending&"
                    f"scheduled_at=lte.{datetime.now().isoformat()}&"
                    f"select=*",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                    
        except Exception as e:
            print(f"❌ [Supabase] Get pending notifications error: {e}")
        return []
    
    async def mark_notification_sent(self, notification_id: str) -> bool:
        """تحديد الإشعار كمُرسل"""
        if not self.url:
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.url}/rest/v1/scheduled_notifications?id=eq.{notification_id}",
                    headers=self.headers,
                    json={
                        "status": "sent",
                        "sent_at": datetime.now().isoformat()
                    },
                    timeout=10.0
                )
                return response.status_code in [200, 204]
                
        except Exception as e:
            print(f"❌ [Supabase] Mark notification error: {e}")
            return False


# إنشاء instance واحد
supabase_service = SupabaseService()
