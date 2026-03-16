"""
Manager Agent - وكيل المدير
الوكيل الخامس - يُشرف على النظام ويُنتج التقارير
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from services.supabase_service import supabase_service
from services.deepseek_service import deepseek_service


class ManagerAgent:
    """
    وكيل المدير - الوكيل الخامس في النظام
    
    المسؤوليات:
    1. مراقبة أداء الوكلاء
    2. تتبع الإحصائيات والمقاييس
    3. توليد التقارير
    4. تنبيه المسؤولين عند المشاكل
    """
    
    # عتبات التنبيه
    ERROR_RATE_THRESHOLD = 0.1  # 10% نسبة أخطاء
    RESPONSE_TIME_THRESHOLD = 30  # 30 ثانية
    NO_PROVIDER_THRESHOLD = 3  # 3 طلبات متتالية بدون مزودين
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_offers": 0,
            "avg_response_time": 0,
            "errors": []
        }
        self.alerts: List[Dict] = []
    
    async def log_request(
        self,
        request_id: str,
        success: bool,
        response_time: float = 0,
        error: str = None
    ):
        """
        تسجيل طلب جديد في الإحصائيات
        
        Args:
            request_id: معرف الطلب
            success: هل نجح الطلب؟
            response_time: وقت الاستجابة بالثواني
            error: رسالة الخطأ (إن وجدت)
        """
        self.metrics["total_requests"] += 1
        
        if success:
            self.metrics["successful_requests"] += 1
        else:
            self.metrics["failed_requests"] += 1
            if error:
                self.metrics["errors"].append({
                    "request_id": request_id,
                    "error": error,
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        # تحديث متوسط وقت الاستجابة
        if response_time > 0:
            current_avg = self.metrics["avg_response_time"]
            total = self.metrics["total_requests"]
            self.metrics["avg_response_time"] = (
                (current_avg * (total - 1) + response_time) / total
            )
        
        # التحقق من العتبات
        await self._check_thresholds()
    
    async def log_offer(self, offer_id: str):
        """تسجيل عرض جديد"""
        self.metrics["total_offers"] += 1
    
    async def _check_thresholds(self):
        """التحقق من عتبات التنبيه"""
        total = self.metrics["total_requests"]
        failed = self.metrics["failed_requests"]
        
        # التحقق من نسبة الأخطاء
        if total > 10:  # بعد 10 طلبات على الأقل
            error_rate = failed / total
            if error_rate > self.ERROR_RATE_THRESHOLD:
                await self._create_alert(
                    alert_type="high_error_rate",
                    message=f"نسبة الأخطاء مرتفعة: {error_rate:.1%}",
                    severity="warning"
                )
        
        # التحقق من وقت الاستجابة
        if self.metrics["avg_response_time"] > self.RESPONSE_TIME_THRESHOLD:
            await self._create_alert(
                alert_type="slow_response",
                message=f"متوسط وقت الاستجابة بطيء: {self.metrics['avg_response_time']:.1f}s",
                severity="warning"
            )
    
    async def _create_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "info"
    ):
        """إنشاء تنبيه جديد"""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # تجنب التكرار
        existing = [a for a in self.alerts if a["type"] == alert_type]
        if not existing:
            self.alerts.append(alert)
            print(f"⚠️ [ManagerAgent] Alert: {message}")
    
    async def get_daily_report(self) -> Dict[str, Any]:
        """
        توليد تقرير يومي
        
        Returns:
            تقرير يومي شامل
        """
        total = self.metrics["total_requests"]
        success = self.metrics["successful_requests"]
        
        report = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "summary": {
                "total_requests": total,
                "successful_requests": success,
                "failed_requests": self.metrics["failed_requests"],
                "success_rate": f"{(success/total*100):.1f}%" if total > 0 else "N/A",
                "total_offers": self.metrics["total_offers"]
            },
            "performance": {
                "avg_response_time": f"{self.metrics['avg_response_time']:.2f}s",
                "offers_per_request": f"{self.metrics['total_offers']/total:.1f}" if total > 0 else "N/A"
            },
            "alerts": self.alerts[-10:] if self.alerts else [],
            "errors": self.metrics["errors"][-5:] if self.metrics["errors"] else []
        }
        
        return report
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        الحصول على حالة النظام
        
        Returns:
            حالة النظام الحالية
        """
        return {
            "status": "healthy" if not self.alerts else "warning",
            "uptime": "active",
            "metrics": {
                "total_requests": self.metrics["total_requests"],
                "total_offers": self.metrics["total_offers"],
                "avg_response_time": f"{self.metrics['avg_response_time']:.2f}s"
            },
            "active_alerts": len([a for a in self.alerts if a["severity"] in ["warning", "critical"]]),
            "last_updated": datetime.utcnow().isoformat()
        }
    
    async def analyze_trends(self) -> Dict[str, Any]:
        """
        تحليل الاتجاهات (للتطوير المستقبلي)
        """
        # TODO: تحليل الاتجاهات مع积累 المزيد من البيانات
        return {
            "popular_services": [],
            "peak_hours": [],
            "provider_performance": []
        }
    
    def reset_metrics(self):
        """إعادة تعيين الإحصائيات"""
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_offers": 0,
            "avg_response_time": 0,
            "errors": []
        }
        self.alerts = []
    
    async def generate_admin_summary(self) -> str:
        """
        توليد ملخص نصي للمسؤول
        
        Returns:
            ملخص نصي
        """
        report = await self.get_daily_report()
        
        summary = f"""
📊 *تقرير هدهد اليومي*
━━━━━━━━━━━━━━━

📅 التاريخ: {report['date']}

📈 *الإحصائيات:*
• الطلبات: {report['summary']['total_requests']}
• النجاح: {report['summary']['success_rate']}
• العروض: {report['summary']['total_offers']}

⏱️ *الأداء:*
• متوسط الرد: {report['performance']['avg_response_time']}
• عروض/طلب: {report['performance']['offers_per_request']}

⚠️ *التنبيهات:* {len(report['alerts'])}

━━━━━━━━━━━━━━━
🦦 منصة هدهد
        """.strip()
        
        return summary


# إنشاء instance واحد
manager_agent = ManagerAgent()
