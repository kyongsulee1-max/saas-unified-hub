from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base

class BriefingRecord(Base):
    __tablename__ = "briefings"

    id = Column(Integer, primary_key=True, index=True)
    asset_type = Column(String(20), index=True)  # 'BTC', 'GOLD', 'OIL'
    title = Column(String(255))
    summary = Column(Text)
    full_content = Column(Text)
    key_metrics = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class CustomerKey(Base):
    __tablename__ = "customer_keys"

    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String(64), unique=True, index=True)
    customer_email = Column(String(100))
    tier = Column(String(20), default="standard")
    expires_at = Column(DateTime)
    is_active = Column(Integer, default=1)