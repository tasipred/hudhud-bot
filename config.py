"""
Hudhudbot Configuration
إعدادات منصة هدهد
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# Twilio Configuration
# ============================================
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# ============================================
# DeepSeek Configuration
# ============================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"  # أو deepseek-reasoner

# ============================================
# Supabase Configuration
# ============================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ============================================
# App Configuration
# ============================================
APP_NAME = "Hudhudbot"
APP_URL = os.getenv("APP_URL", "https://hudhud-platform-coral.vercel.app")
OFFER_PAGE_BASE_URL = f"{APP_URL}/offers"

# ============================================
# Business Logic
# ============================================
OFFER_PAGE_VALIDITY_HOURS = 2  # صلاحية صفحة العروض
MAX_PROVIDERS_PER_REQUEST = 5  # أقصى عدد مزودين للطلب الواحد
NOTIFICATION_FIRST_OFFER = True  # إشعار أول عرض
NOTIFICATION_REMINDER_MINUTES = 30  # تذكير قبل انتهاء الصلاحية

# ============================================
# Logging
# ============================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
