"""
DeepSeek AI Service
خدمة الذكاء الاصطناعي DeepSeek
"""

import os
import httpx
from typing import Optional, Dict, Any, List
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class DeepSeekService:
    """
    خدمة DeepSeek AI للتفاعل مع النموذج
    """
    
    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL
        self.model = DEEPSEEK_MODEL
        self.client = httpx.AsyncClient(timeout=60.0)
        
        if not self.api_key:
            print("⚠️ [DeepSeek] No API Key - Running in Mock Mode")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        إرسال رسالة للنموذج والحصول على رد
        
        Args:
            messages: قائمة الرسائل [{"role": "user", "content": "..."}]
            system_prompt: تعليمات النظام
            temperature: درجة الإبداع (0-1)
            max_tokens: أقصى عدد tokens في الرد
            
        Returns:
            {"success": bool, "content": str, "error": str}
        """
        if not self.api_key:
            return self._mock_response(messages)
        
        try:
            # بناء الرسائل
            full_messages = []
            if system_prompt:
                full_messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            full_messages.extend(messages)
            
            # إرسال الطلب
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": full_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {
                    "success": True,
                    "content": content,
                    "usage": data.get("usage", {})
                }
            else:
                error = response.text
                print(f"❌ [DeepSeek] API Error: {response.status_code} - {error}")
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code}",
                    "content": None
                }
                
        except Exception as e:
            print(f"❌ [DeepSeek] Exception: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": None
            }
    
    async def extract_structured_data(
        self,
        user_message: str,
        fields: List[str],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        استخراج بيانات منظمة من رسالة المستخدم
        
        Args:
            user_message: رسالة المستخدم
            fields: الحقول المطلوب استخراجها
            system_prompt: تعليمات إضافية
            
        Returns:
            {"success": bool, "data": dict}
        """
        extraction_prompt = f"""
أنت مساعد ذكي متخصص في استخراج المعلومات.

من رسالة المستخدم، استخرج المعلومات التالية:
{chr(10).join(f'- {field}' for field in fields)}

أعد النتيجة بتنسيق JSON فقط، بدون أي نص إضافي:
{{{','.join(f'"{field}": "قيمة أو null"' for field in fields)}}}

إذا لم تجد معلومة، ضع null.
"""
        
        result = await self.chat(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=extraction_prompt
        )
        
        if result["success"]:
            try:
                # تنظيف الرد وإزالة ```json إن وجدت
                content = result["content"].strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1]  # إزالة السطر الأول
                if content.endswith("```"):
                    content = content.rsplit("```", 1)[0]  # إزالة الأخير
                
                import json
                data = json.loads(content)
                return {"success": True, "data": data}
            except json.JSONDecodeError:
                return {"success": False, "error": "Invalid JSON", "data": None}
        
        return result
    
    def _mock_response(self, messages: List[Dict]) -> Dict[str, Any]:
        """
        رد وهمي للاختبار
        """
        last_message = messages[-1].get("content", "") if messages else ""
        return {
            "success": True,
            "content": f"[MOCK] استلمت رسالتك: {last_message[:50]}...",
            "usage": {"total_tokens": 100}
        }
    
    async def close(self):
        """إغلاق الاتصال"""
        await self.client.aclose()


# ============================================
# System Prompts للوكلاء
# ============================================

RECEPTION_AGENT_PROMPT = """
أنت وكيل الاستقبال في منصة "هدهد" للخدمات.
دورك: فهم طلب العميل واستخراج المعلومات المطلوبة.

## مهمتك:
1. رحب بالعميل بأسلوب ودية ومختصر
2. افهم نوع الخدمة المطلوبة
3. استخرج المعلومات التالية:
   - نوع الخدمة (سباكة، كهرباء، تنظيف، نقل، إلخ)
   - المدينة/المنطقة
   - تفاصيل إضافية (المشكلة، المساحة، الموعد)
   - الميزانية (إن وجدت)

## قواعد:
- تحدث بالعربية الفصحى البسيطة
- كن مختصراً ومباشراً
- إذا نقصت معلومة، اسأل عنها بلطف
- بعد جمع المعلومات، أكدها مع العميل قبل المتابعة

## مثال:
العميل: "أبي سباك"
الرد: "أهلاً وسهلاً! 🙋‍♂️

أنت تحتاج سباك. عشان أساعدك أفضل:
- في أي مدينة؟
- وش المشكلة بالضبط؟"

العميل: "الرياض، تسريب مويه"
الرد: "تمام! خلصت المعلومات:
- 🔧 الخدمة: سباكة
- 📍 المدينة: الرياض  
- 📝 المشكلة: تسريب مياه

صحيح؟ وإذا عندك ميزانية معينة ذكرها."
"""

PROVIDER_AGENT_PROMPT = """
أنت وكيل البحث عن المزودين في منصة "هدهد".
دورك: مطابقة طلب العميل مع أفضل المزودين المتاحين.

## مهمتك:
- ابحث في قاعدة البيانات عن مزودين مطابقين
- رتب حسب: التقييم + القرب + الخبرة
- أرسل للـ 3-5 الأفضل

## قواعد الاختيار:
1. نفس نوع الخدمة
2. نفس المدينة أو قريبة
3. تقييم عالي (4+ نجوم)
4. متفرغ/نشط
"""

RANKING_AGENT_PROMPT = """
أنت وكيل ترتيب العروض في منصة "هدهد".
دورك: ترتيب عروض المزودين واختيار الأفضل للعميل.

## معايير الترتيب:
1. السعر (40%)
2. التقييم السابق (30%)
3. سرعة الرد (20%)
4. جودة العرض/الملاحظات (10%)

## قواعد:
- وضح سبب اختيار "الأفضل"
- قدم معلومات شاملة ومفيدة
- لا تحذف أي عرض من القائمة
"""


# إنشاء instance واحد
deepseek_service = DeepSeekService()
