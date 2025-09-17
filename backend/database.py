from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

SQLALCHEMY_DATABASE_URL = "sqlite:///./devices.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="user")  # user, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True)  # ADB device ID or MAC address
    device_type = Column(String)  # adb, bluetooth, wifi, etc.
    name = Column(String)
    status = Column(String)  # online, offline, occupied
    connection_info = Column(Text)  # JSON string with detailed info
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Device occupation
    occupied_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    occupied_at = Column(DateTime, nullable=True)
    
    # Tags and groups
    tags = Column(Text)  # JSON array of tags
    group_name = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="occupied_devices")
    usage_logs = relationship("DeviceUsageLog", back_populates="device")

class DeviceUsageLog(Base):
    __tablename__ = "device_usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)  # occupy, release
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    
    # Relationships
    device = relationship("Device", back_populates="usage_logs")
    user = relationship("User", back_populates="usage_logs")

# Add back references
User.occupied_devices = relationship("Device", back_populates="user")
User.usage_logs = relationship("DeviceUsageLog", back_populates="user")

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()