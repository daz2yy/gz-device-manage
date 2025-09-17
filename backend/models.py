from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: str
    role: str = "user"

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class DeviceBase(BaseModel):
    device_id: str
    device_type: str
    name: Optional[str] = None
    status: str = "offline"
    group_name: Optional[str] = None
    tags: Optional[List[str]] = []

class DeviceCreate(DeviceBase):
    connection_info: Optional[Dict[str, Any]] = {}

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    group_name: Optional[str] = None
    tags: Optional[List[str]] = None
    connection_info: Optional[Dict[str, Any]] = None

class Device(DeviceBase):
    id: int
    connection_info: Dict[str, Any]
    last_seen: datetime
    created_at: datetime
    occupied_by: Optional[int] = None
    occupied_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class DeviceWithUser(Device):
    user: Optional[User] = None

class DeviceOccupyRequest(BaseModel):
    notes: Optional[str] = None

class DeviceUsageLogBase(BaseModel):
    action: str
    notes: Optional[str] = None

class DeviceUsageLog(DeviceUsageLogBase):
    id: int
    device_id: int
    user_id: int
    timestamp: datetime
    
    class Config:
        from_attributes = True

class DeviceUsageLogWithDetails(DeviceUsageLog):
    device: Device
    user: User

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class DeviceStats(BaseModel):
    total_devices: int
    online_devices: int
    occupied_devices: int
    offline_devices: int
    devices_by_type: Dict[str, int]