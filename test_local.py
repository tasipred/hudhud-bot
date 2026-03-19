#!/usr/bin/env python3
"""
هدهد - اختبار محلي
Local test for Hudhud Bot
"""

import asyncio
import os
import sys

# إضافة المسار للموديولات
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# تحميل المتغيرات من البيئة
os.environ.setdefault('SUPABASE_URL', 'https://lvgnmmqhfoinsyfowkwy.supabase.co')
os.environ.setdefault('APP_URL', 'https://hudhud.sa')

from services.supabase_service import supabase_service
from services.memory_service import memory_service, get_user_context, get_smart_suggestion, log_customer_request


async def test_memory_initialization():
    """اختبار تهيئة الذاكرة"""
    print("\n" + "="*50)
    print("🧪 اختبار 1: تهيئة الذاكرة")
    print("="*50)
    
    result = await memory_service.initialize()
    
    if result:
        print("✅ Memory service initialized successfully")
    else:
        print("⚠️ Memory service not available (tables may not exist)")
    
    return result


async def test_supabase_connection():
    """اختبار الاتصال بـ Supabase"""
    print("\n" + "="*50)
    print("🧪 اختبار 2: الاتصال بـ Supabase")
    print("="*50)
    
    # اختبار providers
    providers = await supabase_service.search_providers("سباكة", "الرياض", limit=2)
    
    if providers:
        print(f"✅ Found {len(providers)} providers")
        for p in providers[:2]:
            print(f"   - {p.get('business_name', 'Unknown')}: {p.get('city', 'N/A')}")
    else:
        print("⚠️ No providers found")
    
    return len(providers) > 0


async def test_smart_suggestion():
    """اختبار الاقتراح الذكي"""
    print("\n" + "="*50)
    print("🧪 اختبار 3: الاقتراح الذكي")
    print("="*50)
    
    test_messages = [
        "ابي نقل عفش في الرياض",
        "مطلوب سباك في جدة",
        "احتاج كهربائي في الدمام",
        "عندي تسريب مويا في مكة"
    ]
    
    for msg in test_messages:
        suggestion = await get_smart_suggestion(msg)
        if suggestion:
            print(f"✅ '{msg[:30]}...'")
            print(f"   الخدمة: {suggestion.get('suggested_service')}")
            print(f"   المدينة: {suggestion.get('suggested_city')}")
        else:
            print(f"⚠️ No suggestion for: {msg[:30]}...")


async def test_user_context():
    """اختبار سياق المستخدم"""
    print("\n" + "="*50)
    print("🧪 اختبار 4: سياق المستخدم")
    print("="*50)
    
    test_phone = "966501234567"
    
    context = await get_user_context(test_phone, "ابي سباك في الرياض")
    
    print(f"✅ Context retrieved for {test_phone}")
    print(f"   Has memory: {context.get('has_memory')}")
    print(f"   User profile: {context.get('user_profile')}")


async def test_log_interaction():
    """اختبار تسجيل التفاعل"""
    print("\n" + "="*50)
    print("🧪 اختبار 5: تسجيل التفاعل")
    print("="*50)
    
    test_phone = "966501234567"
    
    result = await log_customer_request(
        phone=test_phone,
        message="اختبار محلي للذاكرة",
        service_type="سباكة",
        city="الرياض",
        ai_response="هذا رد تجريبي"
    )
    
    if result:
        print(f"✅ Interaction logged: {result}")
    else:
        print("⚠️ Could not log interaction")


async def test_local_extraction():
    """اختبار الاستخراج المحلي"""
    print("\n" + "="*50)
    print("🧪 اختبار 6: الاستخراج المحلي")
    print("="*50)
    
    # Import extraction function
    from main import extract_info_locally
    
    test_cases = [
        [{"sender": "customer", "content": "ابي نقل عفش من الرياض إلى جدة"}],
        [{"sender": "customer", "content": "مطلوب سباك في الدمام عندي تسريب"}],
        [{"sender": "customer", "content": "احتاج كهربائي عاجل في مكة المكرمة"}],
        [{"sender": "customer", "content": "تنظيف فيلا في الخبر المساحة 300 متر"}],
    ]
    
    for messages in test_cases:
        result = extract_info_locally(messages)
        print(f"📝 '{messages[0]['content'][:40]}...'")
        print(f"   الخدمة: {result.get('service_type')}")
        print(f"   المدينة: {result.get('city')}")
        print(f"   مكتمل: {result.get('is_complete')}")
        print()


async def main():
    """تشغيل جميع الاختبارات"""
    print("\n" + "🚀 "*25)
    print("🦦 هدهد - اختبارات محلية")
    print("🚀 "*25)
    
    # تشغيل الاختبارات
    await test_memory_initialization()
    await test_supabase_connection()
    await test_smart_suggestion()
    await test_user_context()
    await test_log_interaction()
    await test_local_extraction()
    
    print("\n" + "="*50)
    print("✅ انتهت جميع الاختبارات!")
    print("="*50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
