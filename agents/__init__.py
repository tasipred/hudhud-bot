"""
Hudhudbot Agents
وكلاء هدهد بوت

5 وكلاء يعملون معاً لخدمة العملاء:
1. ReceptionAgent - وكيل الاستقبال (يفهم الطلب)
2. ProviderAgent - وكيل المزودين (يبحث ويرسل)
3. RankingAgent - وكيل الترتيب (يرتب العروض)
4. NotificationAgent - وكيل الإشعارات (يُنبه العميل)
5. ManagerAgent - وكيل المدير (يُشرف ويُبلغ)
"""

from .reception_agent import reception_agent, ReceptionAgent
from .provider_agent import provider_agent, ProviderAgent
from .ranking_agent import ranking_agent, RankingAgent
from .notification_agent import notification_agent, NotificationAgent
from .manager_agent import manager_agent, ManagerAgent

__all__ = [
    # Instances (جاهزة للاستخدام)
    'reception_agent',
    'provider_agent',
    'ranking_agent',
    'notification_agent',
    'manager_agent',
    
    # Classes (للاختبارات)
    'ReceptionAgent',
    'ProviderAgent',
    'RankingAgent',
    'NotificationAgent',
    'ManagerAgent'
]
