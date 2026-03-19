#!/usr/bin/env python3
"""
هدهد - إضافة بيانات تدريبية إضافية
Seed additional training data to Supabase
"""

import os
import httpx
import json
import random

# Supabase config
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://lvgnmmqhfoinsyfowkwy.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# المدن والخدمات
CITIES = [
    "الرياض", "جدة", "مكة المكرمة", "المدينة المنورة", "الدمام", "الخبر",
    "الطائف", "تبوك", "بريدة", "خميس مشيط", "حائل", "نجران", "أبها",
    "جازان", "الأحساء", "القطيف", "الخرج", "عنيزة", "الرس", "الباحة"
]

SERVICES = {
    "نقل عفش": [
        "ابي نقل عفش", "مطلوب نقل اثاث", "احتاج نقل العفش", "نقل أثاث",
        "شركة نقل عفش", "نقل عفش شقة", "نقل عفش فيلا", "نقل أثاث مكتبي",
        "نقل عفش مع تغليف", "نقل عفش وتفريغ", "نقل عفش عاجل"
    ],
    "سباكة": [
        "ابي سباك", "مطلوب سباك", "احتاج سباك", "عندي تسريب مويا",
        "تسريب في الحمام", "تسريب المطبخ", "صيانة سباكة", "تركيب حوض",
        "تركيب خلاط", "فتح مجاري", "عطل السخان", "تركيب سخان"
    ],
    "كهرباء": [
        "ابي كهربائي", "مطلوب كهربائي", "احتاج كهربائي", "عطل كهرباء",
        "ماس كهربائي", "تركيب انارة", "صيانة كهرباء", "تركيب مروحة",
        "توصيل كهرباء", "لوحة كهربائية", "قاطع كهرباء", "تمديد كهرباء"
    ],
    "تكييف": [
        "ابي فني تكييف", "مطلوب فني مكيفات", "احتاج تركيب مكيف",
        "صيانة مكيف", "تنظيف مكيف", "تعبئة فريون", "تركيب سبليت",
        "إصلاح مكيف", "مكيف ما يبرد", "تسريب مياه من المكيف"
    ],
    "تنظيف": [
        "ابي شركة تنظيف", "مطلوب تنظيف", "احتاج تنظيف البيت",
        "تنظيف شقة", "تنظيف فيلا", "تنظيف مكتب", "تنظيف سجاد",
        "تنظيف كنب", "تنظيف موكيت", "تنظيف ستائر", "تنظيف خزانات"
    ],
    "صباغة": [
        "ابي صباغ", "مطلوب صباغ", "احتاج صباغ", "دهان البيت",
        "صباغة شقة", "صباغة فيلا", "دهان داخلي", "دهان خارجي",
        "تصليح دهان", "ورق جدران", "ديكور صباغة"
    ],
    "نجارة": [
        "ابي نجار", "مطلوب نجار", "احتاج نجار", "تصليح أبواب",
        "تركيب أبواب", "صيانة نجارة", "نجارة مطبخ", "خزائن خشب",
        "أسقف مستعارة", "ديكور خشب", "أرضيات خشب"
    ]
}

# تفاصيل إضافية
DETAILS_TEMPLATES = [
    "عاجل {service}",
    "{service} في {city}",
    "احتاج {service} اليوم",
    "مطلوب {service} بكرة",
    "{service} السعر المناسب",
    "{service} مع ضمان",
    "أفضل {service} في {city}",
    "{service} مضمون",
    "تجربتكم مع {service}",
    "أول مرة أطلب {service}"
]

def generate_training_data(count: int = 500):
    """توليد بيانات تدريبية متنوعة"""
    training_data = []
    
    for _ in range(count):
        service = random.choice(list(SERVICES.keys()))
        city = random.choice(CITIES)
        
        # اختيار نمط الطلب
        pattern_type = random.choice(["simple", "detailed", "urgent", "with_details"])
        
        if pattern_type == "simple":
            phrase = random.choice(SERVICES[service])
            input_text = f"{phrase} في {city}"
        
        elif pattern_type == "detailed":
            phrase = random.choice(SERVICES[service])
            detail = random.choice(DETAILS_TEMPLATES)
            input_text = f"{phrase}، {detail.format(service=service, city=city)}"
        
        elif pattern_type == "urgent":
            phrase = random.choice(SERVICES[service])
            urgency = random.choice(["عاجل!", "ضروري اليوم!", "أسرع ما يمكن!"])
            input_text = f"{urgency} {phrase} في {city}"
        
        else:  # with_details
            phrase = random.choice(SERVICES[service])
            details_additions = [
                "المساحة تقريباً 100 متر",
                "الدور الثاني",
                "بدون مصعد",
                "فيلا دورين",
                "شقة 3 غرف",
                "مكتب صغير",
                "محل تجاري",
                "مستودع"
            ]
            input_text = f"{phrase} في {city}، {random.choice(details_additions)}"
        
        training_data.append({
            "source": "synthetic",
            "input_text": input_text,
            "expected_service_type": service,
            "expected_city": city,
            "expected_intent": "service_request",
            "is_verified": False
        })
    
    return training_data


async def seed_to_supabase(data: list, batch_size: int = 50):
    """إرسال البيانات لـ Supabase"""
    
    async with httpx.AsyncClient() as client:
        total = len(data)
        inserted = 0
        
        for i in range(0, total, batch_size):
            batch = data[i:i + batch_size]
            
            try:
                response = await client.post(
                    f"{SUPABASE_URL}/rest/v1/memory_training_data",
                    headers=headers,
                    json=batch,
                    timeout=30.0
                )
                
                if response.status_code in [200, 201]:
                    inserted += len(batch)
                    print(f"✅ Batch {i//batch_size + 1}: {len(batch)} records inserted")
                else:
                    print(f"❌ Batch {i//batch_size + 1} failed: {response.status_code}")
                    print(f"   Error: {response.text[:200]}")
                    
            except Exception as e:
                print(f"❌ Batch {i//batch_size + 1} error: {e}")
        
        return inserted


async def main():
    print("🚀 Starting training data seeding...")
    print(f"📊 Target: 500 training samples")
    
    # توليد البيانات
    training_data = generate_training_data(500)
    print(f"✅ Generated {len(training_data)} training samples")
    
    # إرسال لـ Supabase
    inserted = await seed_to_supabase(training_data)
    print(f"\n🎯 Result: {inserted} records inserted")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
