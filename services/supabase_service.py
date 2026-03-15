"""
Supabase Database Service
خدمة قاعدة البيانات Supabase
"""

import os
import json
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
            try:
                self.client: Client = create_client(self.url, self.key)
                print(f"✅ [Supabase] Connected to: {self.url}")
            except Exception as e:
                self.client = None
                print(f"❌ [Supabase] Connection failed: {e}")
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
        """إنشاء محادثة جديدة"""
        if not self.client:
            print("⚠️ [Supabase] MOCK: Creating mock conversation")
            return {"success": True, "conversation_id": f"mock-{datetime.utcnow().timestamp()}"}
        
        try:
            result = self.client.table("conversations").insert({
                "customer_phone": customer_phone,
                "status": "new",
                "context": {
                    "initial_message": initial_message,
                    "extracted_data": {}
                },
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            
            conversation_id = result.data[0]["id"]
            print(f"✅ [Supabase] Created conversation: {conversation_id}")
            return {"success": True, "conversation_id": conversation_id}
        except Exception as e:
            print(f"❌ [Supabase] Create conversation error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """الحصول على محادثة"""
        if not self.client:
            return None
        
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
        """الحصول على آخر محادثة نشطة (غير مكتملة)"""
        if not self.client:
            print(f"⚠️ [Supabase] MOCK: No active conversation for {customer_phone}")
            return None
        
        try:
            # جلب آخر محادثة غير مكتملة
            result = self.client.table("conversations").select("*").eq("customer_phone", customer_phone).neq("status", "completed").order("created_at", desc=True).limit(1).execute()
            
            if result.data:
                conv = result.data[0]
                print(f"✅ [Supabase] Found active conversation: {conv['id']}")
                print(f"📋 [Supabase] Status: {conv.get('status')}, Context: {conv.get('context')}")
                
                # إذا المحادثة في وضع انتظار أو عرض، تعتبر مكتملة
                if conv.get("status") in ["waiting", "presenting", "searching"]:
                    print(f"ℹ️ [Supabase] Conversation {conv['id']} is in {conv['status']} state")
                    return None
                
                return conv
            
            print(f"ℹ️ [Supabase] No active conversation found for {customer_phone}")
            return None
        except Exception as e:
            print(f"❌ [Supabase] Get active conversation error: {e}")
            return None
    
    async def update_conversation(
        self,
        conversation_id: str,
        status: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> bool:
        """تحديث المحادثة"""
        if not self.client:
            print(f"⚠️ [Supabase] MOCK: Would update {conversation_id}")
            return True
        
        try:
            update_data = {}
            if status:
                update_data["status"] = status
            if context:
                update_data["context"] = context
            
            print(f"📝 [Supabase] Updating {conversation_id}: {update_data}")
            
            self.client.table("conversations").update(update_data).eq("id", conversation_id).execute()
            
            # تحقق من التحديث
            check = self.client.table("conversations").select("*").eq("id", conversation_id).execute()
            if check.data:
                print(f"✅ [Supabase] Updated successfully: {check.data[0].get('context')}")
            
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
        sender: str,
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
            print(f"💬 [Supabase] Retrieved {len(result.data)} messages")
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
            return {"success": True, "request_id": "mock-req-123", "slug": "mock-slug"}
        
        try:
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
        """الحصول على طلب عبر slug"""
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
        """البحث عن مزودين"""
        if not self.client:
            return []
        
        try:
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
            
            return {"success": True, "offer_id": result.data[0]["id"]}
        except Exception as e:
            print(f"❌ [Supabase] Save provider offer error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_offers_for_request(self, request_id: str) -> List[Dict]:
        """الحصول على عروض طلب"""
        if not self.client:
            return []
        
        try:
            result = self.client.table("provider_offers").select("*, providers(*)").eq("request_id", request_id).execute()
            return result.data
        except Exception as e:
            print(f"❌ [Supabase] Get offers error: {e}")
            return []


# إنشاء instance
supabase_service = SupabaseService()
