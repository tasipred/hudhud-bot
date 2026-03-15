"""
Supabase Database Service
خدمة قاعدة البيانات Supabase
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY


class SupabaseService:
    """
    خدمة قاعدة البيانات Supabase
    """
    
    def __init__(self):
        self.url = SUPABASE_URL
        self.key = SUPABASE_KEY
        
        if self.url and self.key:
            self.client: Client = create_client(self.url, self.key)
            print("✅ [Supabase] Connected successfully")
        else:
            self.client = None
            print("⚠️ [Supabase] No credentials - Running in Mock Mode")
    
    # ============================================
    # Conversations
    # ============================================
    
    async def create_conversation(
        self,
        customer_phone: str,
        initial_message: str
    ) -> Dict[str, Any]:
        """
        إنشاء محادثة جديدة
        
        Returns:
            {"success": bool, "conversation_id": str, "error": str}
        """
        if not self.client:
            return {"success": True, "conversation_id": "mock-conv-123"}
        
        try:
            result = self.client.table("conversations").insert({
                "customer_phone": customer_phone,
                "status": "new",
                "context": {
                    "initial_message": initial_message,
                    "stage": "collecting"
                },
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            
            return {
                "success": True,
                "conversation_id": result.data[0]["id"]
            }
        except Exception as e:
            print(f"❌ [Supabase] Create conversation error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """الحصول على محادثة"""
        if not self.client:
            return {"id": conversation_id, "status": "collecting", "context": {}}
        
        try:
            result = self.client.table("conversations").select("*").eq("id", conversation_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"❌ [Supabase] Get conversation error: {e}")
            return None
    
    async def get_conversation_by_phone(self, customer_phone: str) -> Optional[Dict]:
        """الحصول على آخر محادثة للعميل"""
        if not self.client:
            return None
        
        try:
            result = self.client.table("conversations").select("*").eq("customer_phone", customer_phone).order("created_at", desc=True).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"❌ [Supabase] Get conversation by phone error: {e}")
            return None
    
    async def get_active_conversation_by_phone(self, customer_phone: str) -> Optional[Dict]:
        """
        الحصول على آخر محادثة نشطة للعميل (غير مكتملة)
        
        نشوف المحادثات اللي حالتها مو "completed" و "presenting"
        """
        if not self.client:
            return None
        
        try:
            # جلب آخر محادثة غير مكتملة
            result = self.client.table("conversations").select("*").eq("customer_phone", customer_phone).neq("status", "completed").order("created_at", desc=True).limit(1).execute()
            
            if result.data:
                conv = result.data[0]
                # إذا المحادثة في وضع انتظار العروض أو تقديمها، نعتبرها مكتملة
                if conv.get("status") in ["waiting", "presenting"]:
                    print(f"ℹ️ [Supabase] Conversation {conv['id']} is in {conv['status']} state, treating as completed")
                    return None
                return conv
            
            return None
        except Exception as e:
            print(f"❌ [Supabase] Get active conversation by phone error: {e}")
            return None
    
    async def update_conversation(
        self,
        conversation_id: str,
        status: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> bool:
        """تحديث المحادثة"""
        if not self.client:
            return True
        
        try:
            update_data = {}
            if status:
                update_data["status"] = status
            if context:
                update_data["context"] = context
            
            self.client.table("conversations").update(update_data).eq("id", conversation_id).execute()
            return True
        except Exception as e:
            print(f"❌ [Supabase] Update conversation error: {e}")
            return False
    
    # ============================================
    # Messages
    # ============================================
    
    async def save_message(
        self,
        conversation_id: str,
        sender: str,  # "customer" or "bot" or "provider"
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """حفظ رسالة"""
        if not self.client:
            return True
        
        try:
            self.client.table("messages").insert({
                "conversation_id": conversation_id,
                "sender": sender,
                "content": content,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return True
        except Exception as e:
            print(f"❌ [Supabase] Save message error: {e}")
            return False
    
    async def get_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """الحصول على رسائل المحادثة"""
        if not self.client:
            return []
        
        try:
            result = self.client.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).limit(limit).execute()
            return result.data
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
        if not self.client:
            return {"success": True, "request_id": "mock-req-123"}
        
        try:
            # إنشاء slug للصفحة
            import uuid
            slug = str(uuid.uuid4())[:8]
            
            result = self.client.table("service_requests").insert({
                "conversation_id": conversation_id,
                "customer_phone": customer_phone,
                "service_type": service_type,
                "city": city,
                "details": details,
                "budget": budget,
                "status": "pending",
                "offer_page_slug": slug,
                "expires_at": (datetime.utcnow() + timedelta(hours=2)).isoformat()
            }).execute()
            
            return {
                "success": True,
                "request_id": result.data[0]["id"],
                "slug": slug
            }
        except Exception as e:
            print(f"❌ [Supabase] Create service request error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_service_request(self, request_id: str) -> Optional[Dict]:
        """الحصول على طلب خدمة"""
        if not self.client:
            return None
        
        try:
            result = self.client.table("service_requests").select("*").eq("id", request_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"❌ [Supabase] Get service request error: {e}")
            return None
    
    async def get_request_by_slug(self, slug: str) -> Optional[Dict]:
        """الحصول على طلب عبر slug صفحة العروض"""
        if not self.client:
            return None
        
        try:
            result = self.client.table("service_requests").select("*").eq("offer_page_slug", slug).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"❌ [Supabase] Get request by slug error: {e}")
            return None
    
    # ============================================
    # Providers
    # ============================================
    
    async def search_providers(
        self,
        service_type: str,
        city: str,
        limit: int = 5
    ) -> List[Dict]:
        """البحث عن مزودين مطابقين"""
        if not self.client:
            return []
        
        try:
            # البحث عن مزودين نشطين في نفس الخدمة والمدينة
            result = self.client.table("providers").select("*").eq("status", "active").ilike("services", f"%{service_type}%").ilike("city", f"%{city}%").order("rating", desc=True).limit(limit).execute()
            
            return result.data
        except Exception as e:
            print(f"❌ [Supabase] Search providers error: {e}")
            return []
    
    async def get_provider(self, provider_id: str) -> Optional[Dict]:
        """الحصول على بيانات مزود"""
        if not self.client:
            return None
        
        try:
            result = self.client.table("providers").select("*").eq("id", provider_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"❌ [Supabase] Get provider error: {e}")
            return None
    
    # ============================================
    # Provider Offers
    # ============================================
    
    async def save_provider_offer(
        self,
        request_id: str,
        provider_id: str,
        price: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """حفظ عرض مزود"""
        if not self.client:
            return {"success": True, "offer_id": "mock-offer-123"}
        
        try:
            result = self.client.table("provider_offers").insert({
                "request_id": request_id,
                "provider_id": provider_id,
                "price": price,
                "notes": notes,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            
            return {
                "success": True,
                "offer_id": result.data[0]["id"]
            }
        except Exception as e:
            print(f"❌ [Supabase] Save provider offer error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_offers_for_request(self, request_id: str) -> List[Dict]:
        """الحصول على عروض طلب معين"""
        if not self.client:
            return []
        
        try:
            result = self.client.table("provider_offers").select("*, providers(*)").eq("request_id", request_id).order("created_at", desc=False).execute()
            return result.data
        except Exception as e:
            print(f"❌ [Supabase] Get offers error: {e}")
            return []
    
    # ============================================
    # Categories & Cities
    # ============================================
    
    async def get_categories(self) -> List[Dict]:
        """الحصول على قائمة التصنيفات"""
        if not self.client:
            return []
        
        try:
            result = self.client.table("categories").select("*").order("name").execute()
            return result.data
        except Exception as e:
            print(f"❌ [Supabase] Get categories error: {e}")
            return []
    
    async def get_cities(self) -> List[Dict]:
        """الحصول على قائمة المدن"""
        if not self.client:
            return []
        
        try:
            result = self.client.table("cities").select("*").order("name").execute()
            return result.data
        except Exception as e:
            print(f"❌ [Supabase] Get cities error: {e}")
            return []


# إنشاء instance واحد
supabase_service = SupabaseService()
