"""
Ranking Agent - وكيل الترتيب
الوكيل الثالث - يرتب عروض المزودين ويحدد الأفضل
"""

from typing import Dict, Any, Optional, List
from services.deepseek_service import deepseek_service
from services.supabase_service import supabase_service


class RankingAgent:
    """
    وكيل الترتيب - الوكيل الثالث في النظام
    
    المسؤوليات:
    1. استقبال عروض المزودين
    2. ترتيب العروض حسب معايير محددة
    3. تحديد "الأفضل" للعميل
    4. توفير ملخص واضح
    """
    
    # معايير الترتيب
    PRICE_WEIGHT = 0.40       # 40% للسعر
    RATING_WEIGHT = 0.30      # 30% للتقييم
    RESPONSE_SPEED_WEIGHT = 0.20  # 20% لسرعة الرد
    OFFER_QUALITY_WEIGHT = 0.10   # 10% لجودة العرض
    
    SYSTEM_PROMPT = """
أنت وكيل ترتيب العروض في منصة "هدهد".

## مهمتك:
- ترتيب عروض المزودين حسب معايير محددة
- تحديد العرض "الأفضل" للعميل
- توفير توضيح مختصر لسبب الاختيار

## معايير الترتيب:
1. السعر (40%) - الأقل أفضل
2. التقييم السابق (30%) - الأعلى أفضل
3. سرعة الرد (20%) - الأسرع أفضل
4. جودة العرض (10%) - التفاصيل والوضوح

## قواعد:
- كن عادلاً وشفافاً
- لا تحذف أي عرض من القائمة
- قدم معلومات شاملة ومفيدة
- ركز على مصلحة العميل
"""
    
    def __init__(self):
        self.cached_rankings: Dict[str, List[Dict]] = {}
    
    async def rank_offers(
        self,
        request_id: str
    ) -> Dict[str, Any]:
        """
        ترتيب عروض طلب معين
        
        Args:
            request_id: معرف الطلب
        
        Returns:
            {
                "success": bool,
                "ranked_offers": List[Dict],
                "best_offer": Dict,
                "summary": str
            }
        """
        print(f"📊 [RankingAgent] Ranking offers for: {request_id}")
        
        # جلب العروض من قاعدة البيانات
        offers = await supabase_service.get_offers_for_request(request_id)
        
        if not offers:
            return {
                "success": False,
                "error": "لا توجد عروض بعد",
                "ranked_offers": [],
                "best_offer": None
            }
        
        # جلب بيانات المزودين
        enriched_offers = []
        for offer in offers:
            provider_id = offer.get("provider_id")
            provider = await supabase_service.get_provider(provider_id)
            
            enriched_offer = {
                **offer,
                "provider_name": provider.get("name", "مزود") if provider else "مزود",
                "provider_rating": provider.get("rating", 0) if provider else 0,
                "provider_city": provider.get("city", "") if provider else "",
                "provider_phone": provider.get("phone", "") if provider else ""
            }
            enriched_offers.append(enriched_offer)
        
        # حساب درجة كل عرض
        scored_offers = []
        for offer in enriched_offers:
            score = self._calculate_score(offer, enriched_offers)
            offer["score"] = score
            scored_offers.append(offer)
        
        # ترتيب حسب الدرجة
        ranked_offers = sorted(scored_offers, key=lambda x: x["score"], reverse=True)
        
        # تحديد الأفضل
        best_offer = ranked_offers[0] if ranked_offers else None
        
        # توليد ملخص
        summary = await self._generate_summary(ranked_offers)
        
        # حفظ في الـ cache
        self.cached_rankings[request_id] = ranked_offers
        
        return {
            "success": True,
            "ranked_offers": ranked_offers,
            "best_offer": best_offer,
            "summary": summary,
            "total_offers": len(ranked_offers)
        }
    
    def _calculate_score(
        self,
        offer: Dict,
        all_offers: List[Dict]
    ) -> float:
        """
        حساب درجة العرض (0-100)
        """
        # درجة السعر (الأقل = درجة أعلى)
        prices = [self._parse_price(o.get("price", "0")) for o in all_offers]
        current_price = self._parse_price(offer.get("price", "0"))
        
        if max(prices) > min(prices):
            price_score = 100 * (1 - (current_price - min(prices)) / (max(prices) - min(prices)))
        else:
            price_score = 100
        
        # درجة التقييم
        rating = offer.get("provider_rating", 0)
        rating_score = (rating / 5) * 100 if rating else 50  # 50% إذا مفيش تقييم
        
        # درجة سرعة الرد (placeholder - يحتاج timestamps حقيقية)
        response_score = 70  # درجة افتراضية
        
        # درجة جودة العرض
        notes = offer.get("notes", "")
        quality_score = min(100, 50 + len(notes) * 2)  # أكثر تفاصيل = درجة أعلى
        
        # المجموع الموزون
        total_score = (
            price_score * self.PRICE_WEIGHT +
            rating_score * self.RATING_WEIGHT +
            response_score * self.RESPONSE_SPEED_WEIGHT +
            quality_score * self.OFFER_QUALITY_WEIGHT
        )
        
        return round(total_score, 2)
    
    def _parse_price(self, price_str: str) -> float:
        """
        تحويل نص السعر إلى رقم
        """
        import re
        # استخراج الأرقام من النص
        numbers = re.findall(r'\d+', str(price_str).replace(',', ''))
        if numbers:
            return float(numbers[0])
        return 0.0
    
    async def _generate_summary(self, ranked_offers: List[Dict]) -> str:
        """
        توليد ملخص للعروض
        """
        if not ranked_offers:
            return "لا توجد عروض حالياً"
        
        best = ranked_offers[0]
        
        summary = f"""
📊 *ملخص العروض ({len(ranked_offers)} عرض)*

🏆 *الأفضل:*
{best.get('provider_name', 'مزود')}
💰 {best.get('price', 'غير محدد')}
⭐ {best.get('provider_rating', 'جديد')} تقييم

━━━━━━━━━━━━━━━

"""
        
        # إضافة باقي العروض
        for i, offer in enumerate(ranked_offers[1:], 2):
            summary += f"""
{i}. {offer.get('provider_name', 'مزود')}
   💰 {offer.get('price', 'غير محدد')}
   ⭐ {offer.get('provider_rating', 'جديد')}
   
"""
        
        return summary.strip()
    
    async def get_ranked_offers(self, request_id: str) -> Optional[List[Dict]]:
        """
        الحصول على العروض المرتبة من الـ cache أو قاعدة البيانات
        """
        if request_id in self.cached_rankings:
            return self.cached_rankings[request_id]
        
        result = await self.rank_offers(request_id)
        return result.get("ranked_offers")
    
    def clear_cache(self, request_id: str = None):
        """
        مسح الـ cache
        """
        if request_id:
            self.cached_rankings.pop(request_id, None)
        else:
            self.cached_rankings.clear()


# إنشاء instance واحد
ranking_agent = RankingAgent()
