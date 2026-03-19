#!/usr/bin/env python3
"""
هدهد - خدمة الذاكرة الطويلة
Hudhud - Long-term Memory Service

تخزين واسترجاع الذكريات لتحسين الـ AI Agent
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import httpx


@dataclass
class MemoryInteraction:
    """تفاعل مع المستخدم"""
    user_phone: str
    user_type: str  # customer, provider
    interaction_type: str  # service_request, inquiry, greeting
    user_message: str
    ai_response: Optional[str] = None
    extracted_service_type: Optional[str] = None
    extracted_city: Optional[str] = None
    extracted_details: Optional[Dict] = None
    confidence_score: Optional[float] = None
    was_successful: Optional[bool] = None


@dataclass
class UserProfile:
    """ملف المستخدم"""
    phone: str
    user_type: str = 'customer'
    preferred_name: Optional[str] = None
    preferred_city: Optional[str] = None
    most_requested_services: List[str] = None
    request_count: int = 0
    tags: List[str] = None
    
    def __post_init__(self):
        if self.most_requested_services is None:
            self.most_requested_services = []
        if self.tags is None:
            self.tags = []


class MemoryService:
    """خدمة الذاكرة الطويلة لهدهد"""
    
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        self._initialized = False
        
    async def initialize(self):
        """تهيئة الخدمة"""
        if not self.supabase_url or not self.supabase_key:
            print("⚠️ [Memory] No Supabase credentials - Memory disabled")
            return False
        
        # التحقق من وجود الجداول
        try:
            async with httpx.AsyncClient() as client:
                # اختبار جدول التفاعلات
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/memory_interactions?select=id&limit=1",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    self._initialized = True
                    print("✅ [Memory] Memory service initialized")
                    return True
                elif response.status_code == 404:
                    print("⚠️ [Memory] Memory tables not found. Run quick_memory_setup.sql first!")
                    return False
                else:
                    print(f"⚠️ [Memory] Unexpected status: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ [Memory] Initialization failed: {e}")
            return False
    
    async def log_interaction(self, interaction: MemoryInteraction) -> Optional[str]:
        """
        تسجيل تفاعل جديد في الذاكرة
        """
        if not self._initialized:
            return None
            
        try:
            data = {
                "user_phone": interaction.user_phone,
                "user_type": interaction.user_type,
                "interaction_type": interaction.interaction_type,
                "user_message": interaction.user_message,
                "ai_response": interaction.ai_response,
                "extracted_service_type": interaction.extracted_service_type,
                "extracted_city": interaction.extracted_city,
                "extracted_details": interaction.extracted_details,
                "confidence_score": interaction.confidence_score,
                "was_successful": interaction.was_successful
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.supabase_url}/rest/v1/memory_interactions",
                    headers=self.headers,
                    json=data,
                    timeout=10.0
                )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    interaction_id = result[0].get('id') if result else None
                    
                    # تحديث ملف المستخدم
                    await self._update_user_profile(interaction)
                    
                    return interaction_id
                else:
                    print(f"⚠️ [Memory] Failed to log: {response.status_code}")
                    return None
                    
        except Exception as e:
            print(f"❌ [Memory] Error logging interaction: {e}")
            return None
    
    async def get_user_profile(self, phone: str) -> Optional[UserProfile]:
        """
        الحصول على ملف المستخدم
        """
        if not self._initialized:
            return None
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/memory_user_profiles?phone=eq.{phone}",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        profile = data[0]
                        return UserProfile(
                            phone=profile.get('phone'),
                            user_type=profile.get('user_type', 'customer'),
                            preferred_name=profile.get('preferred_name'),
                            preferred_city=profile.get('preferred_city'),
                            most_requested_services=profile.get('most_requested_services', []),
                            request_count=profile.get('request_count', 0),
                            tags=profile.get('tags', [])
                        )
                    return None
                return None
                
        except Exception as e:
            print(f"❌ [Memory] Error getting profile: {e}")
            return None
    
    async def _update_user_profile(self, interaction: MemoryInteraction):
        """
        تحديث ملف المستخدم بعد التفاعل
        """
        if not self._initialized:
            return
            
        try:
            # الحصول على الملف الحالي
            existing = await self.get_user_profile(interaction.user_phone)
            
            if existing:
                # تحديث الملف الموجود
                services = existing.most_requested_services or []
                if interaction.extracted_service_type and interaction.extracted_service_type not in services:
                    services.append(interaction.extracted_service_type)
                    # الاحتفاظ بآخر 5 خدمات فقط
                    services = services[-5:]
                
                update_data = {
                    "request_count": existing.request_count + 1,
                    "last_active_at": datetime.utcnow().isoformat(),
                    "preferred_city": interaction.extracted_city or existing.preferred_city,
                    "most_requested_services": services
                }
                
                async with httpx.AsyncClient() as client:
                    await client.patch(
                        f"{self.supabase_url}/rest/v1/memory_user_profiles?phone=eq.{interaction.user_phone}",
                        headers=self.headers,
                        json=update_data,
                        timeout=10.0
                    )
            else:
                # إنشاء ملف جديد
                new_profile = {
                    "phone": interaction.user_phone,
                    "user_type": interaction.user_type,
                    "preferred_city": interaction.extracted_city,
                    "most_requested_services": [interaction.extracted_service_type] if interaction.extracted_service_type else [],
                    "request_count": 1,
                    "last_active_at": datetime.utcnow().isoformat()
                }
                
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{self.supabase_url}/rest/v1/memory_user_profiles",
                        headers=self.headers,
                        json=new_profile,
                        timeout=10.0
                    )
                    
        except Exception as e:
            print(f"❌ [Memory] Error updating profile: {e}")
    
    async def get_similar_interactions(self, phone: str, limit: int = 5) -> List[Dict]:
        """
        الحصول على تفاعلات مشابهة للمستخدم
        """
        if not self._initialized:
            return []
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/memory_interactions?user_phone=eq.{phone}&was_successful=eq.true&order=created_at.desc&limit={limit}",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                return []
                
        except Exception as e:
            print(f"❌ [Memory] Error getting similar: {e}")
            return []
    
    async def get_pattern(self, pattern_type: str, service_type: str = None) -> Optional[Dict]:
        """
        الحصول على نمط مطابق
        """
        if not self._initialized:
            return None
            
        try:
            query = f"pattern_type=eq.{pattern_type}&is_active=eq.true"
            if service_type:
                query += f"&service_type=eq.{service_type}"
            query += "&order=priority.desc&limit=1"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/memory_patterns?{query}",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        return data[0]
                return None
                
        except Exception as e:
            print(f"❌ [Memory] Error getting pattern: {e}")
            return None
    
    async def get_knowledge(self, category: str, topic: str = None) -> Optional[Dict]:
        """
        الحصول على معلومة من قاعدة المعرفة
        """
        if not self._initialized:
            return None
            
        try:
            query = f"category=eq.{category}&is_active=eq.true"
            if topic:
                query += f"&topic=eq.{topic}"
            query += "&limit=1"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/memory_knowledge_base?{query}",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        return data[0]
                return None
                
        except Exception as e:
            print(f"❌ [Memory] Error getting knowledge: {e}")
            return None
    
    def get_context_for_ai(self, phone: str, current_message: str) -> Dict:
        """
        الحصول على سياق للمساعد AI (دالة sync للتوافق)
        """
        # هذه الدالة ستعيد سياق أساسي
        # في الإنتاج، يجب أن تكون async
        return {
            "user_phone": phone,
            "has_memory": self._initialized,
            "current_message": current_message,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def enrich_context(self, phone: str, current_message: str) -> Dict:
        """
        إثراء سياق الـ AI بالمعلومات من الذاكرة
        """
        context = {
            "has_memory": self._initialized,
            "user_phone": phone,
            "current_message": current_message,
            "user_profile": None,
            "past_interactions": [],
            "relevant_knowledge": None,
            "patterns": []
        }
        
        if not self._initialized:
            return context
        
        # الحصول على ملف المستخدم
        profile = await self.get_user_profile(phone)
        if profile:
            context["user_profile"] = {
                "preferred_city": profile.preferred_city,
                "most_requested_services": profile.most_requested_services,
                "request_count": profile.request_count
            }
        
        # الحصول على تفاعلات سابقة ناجحة
        past = await self.get_similar_interactions(phone, limit=3)
        if past:
            context["past_interactions"] = [
                {
                    "message": p.get("user_message", ""),
                    "service": p.get("extracted_service_type"),
                    "city": p.get("extracted_city")
                }
                for p in past
            ]
        
        return context


# إنشاء instance عام
memory_service = MemoryService()


# ===========================================
# دوال مساعدة للاستخدام المباشر
# ===========================================

async def log_customer_request(
    phone: str,
    message: str,
    service_type: str = None,
    city: str = None,
    ai_response: str = None,
    confidence: float = None
) -> Optional[str]:
    """تسجيل طلب عميل"""
    interaction = MemoryInteraction(
        user_phone=phone,
        user_type='customer',
        interaction_type='service_request',
        user_message=message,
        ai_response=ai_response,
        extracted_service_type=service_type,
        extracted_city=city,
        confidence_score=confidence
    )
    return await memory_service.log_interaction(interaction)


async def log_provider_response(
    phone: str,
    message: str,
    ai_response: str = None,
    was_successful: bool = None
) -> Optional[str]:
    """تسجيل رد مزود"""
    interaction = MemoryInteraction(
        user_phone=phone,
        user_type='provider',
        interaction_type='offer_response',
        user_message=message,
        ai_response=ai_response,
        was_successful=was_successful
    )
    return await memory_service.log_interaction(interaction)


async def get_user_context(phone: str, current_message: str = "") -> Dict:
    """الحصول على سياق المستخدم للـ AI"""
    return await memory_service.enrich_context(phone, current_message)


async def search_training_data(message: str, limit: int = 5) -> List[Dict]:
    """
    البحث في بيانات التدريب لإيجاد طلبات مشابهة
    يساعد الـ AI على فهم الطلبات بشكل أفضل
    """
    if not memory_service._initialized:
        return []
    
    try:
        # البحث بالنص المشابه
        # نستخدم ilike للبحث الجزئي
        search_terms = message.split()[:3]  # أول 3 كلمات
        search_query = " ".join(search_terms)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{memory_service.supabase_url}/rest/v1/memory_training_data?input_text=ilike.*{search_query}*&select=*&limit={limit}",
                headers=memory_service.headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                return response.json()
            return []
            
    except Exception as e:
        print(f"❌ [Memory] Error searching training data: {e}")
        return []


async def get_smart_suggestion(message: str) -> Optional[Dict]:
    """
    الحصول على اقتراح ذكي من بيانات التدريب
    يعيد الخدمة والمدينة المتوقعة
    """
    similar = await search_training_data(message, limit=3)
    
    if similar:
        # نأخذ النتيجة الأكثر تطابقاً
        best_match = similar[0]
        return {
            "suggested_service": best_match.get("expected_service_type"),
            "suggested_city": best_match.get("expected_city"),
            "confidence": 0.8,  # ثقة افتراضية
            "matched_pattern": best_match.get("input_text")
        }
    
    return None
