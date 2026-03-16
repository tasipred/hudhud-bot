"""
External API Service
خدمة الاتصال بالمنصة الخارجية
"""

import os
import httpx
from typing import Optional, Dict, Any, List
from config import APP_URL


class SupabaseService:
    """
    خدمة الاتصال بالمنصة عبر HTTP API
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
        # Use the Next.js platform API
        self.platform_url = APP_URL
        print(f"🌐 [API] Platform URL: {self.platform_url}")

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
        """إنشاء طلب خدمة جديد عبر Platform API"""

        data = {
            "customer_phone": self._normalize_phone(customer_phone),
            "service_type": service_type,
            "city": city,
            "description": description
        }

        print(f"📝 [API] Creating request: {data}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.platform_url}/api/requests",
                    json=data,
                    timeout=30.0
                )

                print(f"📊 [API] Response status: {response.status_code}")
                print(f"📊 [API] Response: {response.text[:500]}")

                if response.status_code in [200, 201]:
                    result = response.json()
                    print(f"✅ [API] Created request: {result.get('request_id')}")
                    return {
                        "success": True,
                        "request_id": result.get("request_id")
                    }
                else:
                    print(f"❌ [API] Create failed: {response.status_code}")
                    return {"success": False, "error": response.text}

        except Exception as e:
            print(f"❌ [API] Create request error: {e}")
            return {"success": False, "error": str(e)}

    async def get_service_request(self, request_id: str) -> Optional[Dict]:
        """الحصول على طلب خدمة"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.platform_url}/api/requests?id={request_id}",
                    timeout=10.0
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("request")
        except Exception as e:
            print(f"❌ [API] Get request error: {e}")
        return None

    async def get_offers_for_request(self, request_id: str) -> List[Dict]:
        """الحصول على عروض طلب"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.platform_url}/api/offers/{request_id}",
                    timeout=10.0
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("offers", [])
        except Exception as e:
            print(f"❌ [API] Get offers error: {e}")
        return []


# إنشاء instance
supabase_service = SupabaseService()
