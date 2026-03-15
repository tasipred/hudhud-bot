"""
Hudhudbot Models
نماذج البيانات - هدهد بوت
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ConversationStatus(str, Enum):
    """حالات المحادثة"""
    NEW = "new"
    COLLECTING = "collecting"
    CONFIRMING = "confirming"
    SEARCHING = "searching"
    WAITING = "waiting"
    PRESENTING = "presenting"
    COMPLETED = "completed"


class OfferStatus(str, Enum):
    """حالات العرض"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ServiceRequest(BaseModel):
    """طلب خدمة"""
    id: str
    customer_phone: str
    service_type: str
    city: str
    details: Optional[str] = None
    budget: Optional[str] = None
    status: ConversationStatus
    offer_page_slug: str
    expires_at: datetime
    created_at: datetime


class ProviderOffer(BaseModel):
    """عرض مزود"""
    id: str
    request_id: str
    provider_id: str
    price: str
    notes: Optional[str] = None
    status: OfferStatus
    created_at: datetime


class Provider(BaseModel):
    """مزود خدمة"""
    id: str
    name: str
    phone: str
    city: str
    services: List[str]
    rating: float
    total_reviews: int
    status: str = "active"


class Message(BaseModel):
    """رسالة"""
    id: str
    conversation_id: str
    sender: str  # "customer" | "bot" | "provider"
    content: str
    metadata: Optional[dict] = None
    created_at: datetime
