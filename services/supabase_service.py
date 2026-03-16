"""
Supabase Database Service
خدمة قاعدة البيانات Supabase
"""

import os
import json
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY


class SupabaseService:
    """
    خدمة قاعدة البيانات Supabase
    يستخدم HTTP API مباشرة لضمان العمل
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
        self.client: Optional[Client] = None

        # Debug: print key type
        if self.key:
            key_type = "service_role" if self.key.startswith("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx2Z25tbXFoZm9pbnN5Zm93a3d5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSI") else "anon"
            print(f"🔑 [Supabase] Using {key_type} key")
        else:
            print("⚠️ [Supabase] No key found")

        if self.url and self.key:
            try:
                self.client = create_client(self.url, self.key)
                print(f"✅ [Supabase] Client connected to: {self.url}")
            except Exception as e:
                print(f"❌ [Supabase] Client connection failed: {e}")

        # HTTP client will always work if we have credentials
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        } if self.key else {}

        if self.url and self.key:
            print(f"✅ [Supabase] HTTP client ready")
        else:
            print("⚠️ [Supabase] No credentials - Running in Mock Mode")

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
        """إنشاء طلب خدمة جديد باستخدام HTTP API"""

        import uuid
        request_id = str(uuid.uuid4())

        if not self.url or not self.key:
            print("⚠️ [Supabase] MOCK: No credentials")
            return {"success": True, "request_id": request_id}

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
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    f"{self.url}/rest/v1/service_requests",
                    headers=self.headers,
                    json=data,
                    timeout=10.0
                )

                print(f"📊 [Supabase] Response status: {response.status_code}")
                print(f"📊 [Supabase] Response: {response.text}")

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
        if not self.url or not self.key:
            return None

        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
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

    async def search_providers(
        self,
        service_type: str,
        city: str,
        limit: int = 5
    ) -> List[Dict]:
        """البحث عن مزودين"""
        if not self.url or not self.key:
            return []

        try:
            category_slug = self.CATEGORY_SLUGS.get(service_type, "")
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
                    f"{self.url}/rest/v1/providers?status=eq.active&category_slug=eq.{category_slug}&city=ilike.%25{city}%25&select=*&order=rating.desc&limit={limit}",
                    headers=self.headers,
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"❌ [Supabase] Search providers error: {e}")
        return []

    async def get_offers_for_request(self, request_id: str) -> List[Dict]:
        """الحصول على عروض طلب"""
        if not self.url or not self.key:
            return []

        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
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
