"""
Supabase Database Service
خدمة قاعدة البيانات Supabase
"""

import os
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime

# Hardcoded credentials for Railway (no env vars available)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lvgnmmqhfoinsyfowkwy.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx2Z25tbXFoZm9pbnN5Zm93a3d5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzQyNDE5MywiZXhwIjoyMDg5MDAwMTkzfQ.umYlLweTNylI9tPOeYKGn7wDCc1NBU81scEMwX0-_Mk")


class SupabaseService:
    """
    خدمة قاعدة البيانات Supabase
    يستخدم HTTP API مباشرة
    """

    # Category slug mapping
    CATEGORY_SLUGS = {
        "سباكة": "plumbing",
        "كهرباء": "electrical",
        "تنظيف": "cleaning",
        "تكييف": "ac",
        "نقل عفش": "moving",
        "صباغة": "painting",
        "نجارة": "maintenance",
    }

    def __init__(self):
        self.url = SUPABASE_URL
        self.key = SUPABASE_KEY

        # HTTP headers
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        print(f"🔑 [Supabase] Initialized with service role key")
        print(f"🌐 [Supabase] URL: {self.url}")

    def _normalize_phone(self, phone: str) -> str:
        """ت normalize رقم الهاتف"""
        if not phone:
            return phone
        return phone.replace(" ", "").replace("+", "").replace("whatsapp:", "")

    async def create_service_request(
        self,
        customer_phone: str,
        service_type: str,
        city: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """إنشاء طلب خدمة جديد"""

        import uuid
        request_id = str(uuid.uuid4())

        # Get category slug
        category_slug = self.CATEGORY_SLUGS.get(service_type)

        data = {
            "id": request_id,
            "customer_phone": self._normalize_phone(customer_phone),
            "description": description or f"{service_type} في {city}",
            "category_slug": category_slug,
            "city": city,
            "status": "new"
        }

        print(f"📝 [Supabase] Creating request: {data}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/service_requests",
                    headers=self.headers,
                    json=data,
                    timeout=30.0
                )

                print(f"📊 [Supabase] Response status: {response.status_code}")
                print(f"📊 [Supabase] Response: {response.text[:500] if response.text else 'empty'}")

                if response.status_code in [200, 201]:
                    print(f"✅ [Supabase] Created service request: {request_id}")
                    return {
                        "success": True,
                        "request_id": request_id
                    }
                else:
                    print(f"❌ [Supabase] Create failed: {response.status_code} - {response.text}")
                    return {"success": False, "error": response.text}

        except Exception as e:
            print(f"❌ [Supabase] Create service request error: {e}")
            return {"success": False, "error": str(e)}

    async def get_service_request(self, request_id: str) -> Optional[Dict]:
        """الحصول على طلب خدمة"""
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

    async def get_offers_for_request(self, request_id: str) -> List[Dict]:
        """الحصول على عروض طلب"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/provider_offers?request_id=eq.{request_id}&select=*,providers(id,business_name,whatsapp,rating,review_count,total_jobs)",
                    headers=self.headers,
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"❌ [Supabase] Get offers error: {e}")
        return []


# إنشاء instance
supabase_service = SupabaseService()
