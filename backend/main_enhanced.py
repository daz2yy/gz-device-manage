from fastapi import FastAPI, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import subprocess
import re
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio

# Import our modules
from database import get_db, create_tables, Device as DBDevice, User as DBUser, DeviceUsageLog as DBDeviceUsageLog, SessionLocal
from models import *
from auth import *

app = FastAPI(title="Device Management System", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Global state managed during application lifecycle
scheduler: Optional[BackgroundScheduler] = None
event_loop: Optional[asyncio.AbstractEventLoop] = None

def parse_bluetoothctl_info(text: str) -> Dict[str, Any]:
    """Parse `bluetoothctl info` output into structured fields."""
    parsed: Dict[str, Any] = {
        "mac": None,
        "name": None,
        "alias": None,
        "class": None,
        "icon": None,
        "connected": None,
        "paired": None,
        "trusted": None,
        "blocked": None,
        "rssi": None,
        "tx_power": None,
        "modalias": None,
        "services_resolved": None,
        "uuids": [],
        "manufacturer_data": {},
    }

    if not text:
        return parsed

    r_device = re.compile(r"^Device\s+([0-9A-Fa-f:]{17})")
    r_kv = re.compile(r"^(\w[\w\s]+?):\s*(.*)$")
    r_uuid = re.compile(r"^UUID:\s*([0-9a-fA-F\-]{4,})\s*(?:\((.*?)\))?$")

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        m_dev = r_device.match(line)
        if m_dev:
            parsed["mac"] = m_dev.group(1)
            continue

        m_uuid = r_uuid.match(line)
        if m_uuid:
            parsed["uuids"].append({
                "uuid": m_uuid.group(1),
                "desc": m_uuid.group(2) or None,
            })
            continue

        m = r_kv.match(line)
        if not m:
            continue
        key = m.group(1).strip()
        val = m.group(2).strip()

        k = key.lower().replace(" ", "_")
        if k == "name":
            parsed["name"] = val or None
        elif k == "alias":
            parsed["alias"] = val or None
        elif k == "class":
            parsed["class"] = val or None
        elif k == "icon":
            parsed["icon"] = val or None
        elif k == "connected":
            parsed["connected"] = val.lower() == "yes"
        elif k == "paired":
            parsed["paired"] = val.lower() == "yes"
        elif k == "trusted":
            parsed["trusted"] = val.lower() == "yes"
        elif k == "blocked":
            parsed["blocked"] = val.lower() == "yes"
        elif k == "rssi":
            try:
                parsed["rssi"] = int(val)
            except ValueError:
                parsed["rssi"] = None
        elif k == "txpower":
            try:
                parsed["tx_power"] = int(val)
            except ValueError:
                parsed["tx_power"] = None
        elif k == "modalias":
            parsed["modalias"] = val or None
        elif k == "services_resolved":
            parsed["services_resolved"] = val.lower() == "yes"
        elif key.startswith("ManufacturerData") or key.startswith("Manufacturer Data"):
            parts = val.split(None, 1)
            md_key = parts[0] if parts else None
            md_val = parts[1] if len(parts) > 1 else ""
            if md_key:
                parsed["manufacturer_data"][md_key] = md_val

    return parsed

def get_adb_bluetooth_info(device_id: str) -> Dict[str, Any]:
    """Get Bluetooth information for an ADB device."""
    bluetooth_info = {
        "bluetooth_name": None,
        "bluetooth_enabled": False,
        "connected_devices": []
    }
    
    try:
        # Get Bluetooth controller info using bluetoothctl show
        show_cmd = ["adb", "-s", device_id, "shell", "bluetoothctl", "show"]
        show_result = subprocess.run(show_cmd, capture_output=True, text=True, check=True)
        
        # Parse bluetooth controller info
        controller_name = None
        controller_alias = None
        
        for line in show_result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('Name:'):
                controller_name = line.split(':', 1)[1].strip()
            elif line.startswith('Alias:'):
                controller_alias = line.split(':', 1)[1].strip()
            elif line.startswith('Powered:'):
                bluetooth_info["bluetooth_enabled"] = 'yes' in line.lower()
        
        # Use Alias if available, otherwise use Name
        bluetooth_info["bluetooth_name"] = controller_alias or controller_name
        
        # Get connected devices using bluetoothctl devices Connected
        devices_cmd = ["adb", "-s", device_id, "shell", "bluetoothctl", "devices", "Connected"]
        devices_result = subprocess.run(devices_cmd, capture_output=True, text=True, check=True)
        
        # Parse connected devices
        for line in devices_result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('Device '):
                parts = line.split(' ', 2)
                if len(parts) >= 2:
                    mac_addr = parts[1]
                    device_name = parts[2] if len(parts) > 2 else "Unknown"
                    
                    # Get detailed info for this connected device
                    info_cmd = ["adb", "-s", device_id, "shell", "bluetoothctl", "info", mac_addr]
                    info_result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
                    parsed_info = parse_bluetoothctl_info(info_result.stdout)
                    
                    bluetooth_info["connected_devices"].append({
                        "mac": mac_addr,
                        "name": device_name,
                        "detailed_info": parsed_info
                    })
    
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return bluetooth_info

def get_adb_wifi_ap_info(device_id: str) -> Dict[str, Any]:
    """Get WiFi AP information for an ADB device."""
    wifi_ap_info = {
        "ap_name": None,
        "ap_password": None,
        "config_found": False
    }
    
    try:
        # Try to read the hostapd configuration file
        config_cmd = ["adb", "-s", device_id, "shell", "cat", "/data/misc/wifi/hostapd_ac40-wpa2.conf"]
        config_result = subprocess.run(config_cmd, capture_output=True, text=True, check=True)
        
        if config_result.stdout.strip():
            wifi_ap_info["config_found"] = True
            
            # Parse the configuration file
            for line in config_result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('ssid='):
                    wifi_ap_info["ap_name"] = line.split('=', 1)[1].strip()
                elif line.startswith('wpa_passphrase='):
                    wifi_ap_info["ap_password"] = line.split('=', 1)[1].strip()
    
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return wifi_ap_info

def get_adb_device_alias(device_id: str) -> str:
    """Get the Alias name for an ADB device from Bluetooth controller info."""
    try:
        # Get Bluetooth controller info to extract alias
        show_cmd = ["adb", "-s", device_id, "shell", "bluetoothctl", "show"]
        show_result = subprocess.run(show_cmd, capture_output=True, text=True, check=True)
        
        alias_name = None
        controller_name = None
        
        for line in show_result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('Alias:'):
                alias_name = line.split(':', 1)[1].strip()
            elif line.startswith('Name:'):
                controller_name = line.split(':', 1)[1].strip()
        
        # Prefer Alias over Name, but avoid generic names
        if alias_name and not alias_name.startswith('BlueZ'):
            return alias_name
        elif controller_name and not controller_name.startswith('BlueZ'):
            return controller_name
    
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return None

def scan_adb_devices() -> List[Dict[str, Any]]:
    """Scan for ADB devices and return structured data."""
    devices = []
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split("\n")[1:]
        for line in lines:
            if line and "\t" in line:
                parts = line.split("\t")
                device_id = parts[0]
                status = parts[1] if len(parts) > 1 else "unknown"
                
                # Get device alias name
                device_alias = get_adb_device_alias(device_id) if status == "device" else None
                device_name = device_alias or f"Camera Device {device_id}"
                
                # Get Bluetooth information for ADB devices
                bluetooth_info = get_adb_bluetooth_info(device_id) if status == "device" else {}
                
                # Get WiFi AP information for ADB devices
                wifi_ap_info = get_adb_wifi_ap_info(device_id) if status == "device" else {}
                
                connection_info = {
                    "adb_status": status,
                    "bluetooth_info": bluetooth_info,
                    "wifi_ap_info": wifi_ap_info
                }
                
                devices.append({
                    "device_id": device_id,
                    "device_type": "adb",
                    "name": device_name,
                    "status": "online" if status == "device" else "offline",
                    "connection_info": connection_info
                })
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return devices

def scan_bluetooth_devices() -> List[Dict[str, Any]]:
    """Scan for Bluetooth devices and return structured data."""
    devices = []
    try:
        # Get ADB devices first
        adb_result = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=True)
        adb_lines = adb_result.stdout.strip().split("\n")[1:]
        adb_device_ids = [line.split("\t")[0] for line in adb_lines if line and "\tdevice" in line]
        
        for adb_id in adb_device_ids:
            try:
                # Get bluetooth devices for this ADB device
                cmd = ["adb", "-s", adb_id, "shell", "bluetoothctl", "devices"]
                bt_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                for line in bt_result.stdout.split("\n"):
                    line = line.strip()
                    if line.startswith("Device "):
                        parts = line.split(" ", 2)
                        if len(parts) >= 2:
                            mac_addr = parts[1]
                            device_name = parts[2] if len(parts) > 2 else "Unknown"
                            
                            # Get detailed info
                            info_cmd = ["adb", "-s", adb_id, "shell", "bluetoothctl", "info", mac_addr]
                            info_result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
                            parsed_info = parse_bluetoothctl_info(info_result.stdout)
                            
                            devices.append({
                                "device_id": mac_addr,
                                "device_type": "bluetooth",
                                "name": device_name,
                                "status": "online" if parsed_info.get("connected") else "offline",
                                "connection_info": {
                                    "adb_host": adb_id,
                                    "bluetooth_info": parsed_info,
                                    "raw_output": info_result.stdout
                                }
                            })
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return devices

def update_devices_in_db():
    """Background task to update device information in database."""
    db = SessionLocal()
    try:
        # Scan for devices
        adb_devices = scan_adb_devices()
        bluetooth_devices = scan_bluetooth_devices()
        all_scanned_devices = adb_devices + bluetooth_devices
        
        current_time = datetime.utcnow()
        scanned_device_ids = set()
        
        # Update or create devices
        for device_data in all_scanned_devices:
            scanned_device_ids.add(device_data["device_id"])
            
            db_device = db.query(DBDevice).filter(DBDevice.device_id == device_data["device_id"]).first()
            if db_device:
                # Update existing device
                db_device.name = device_data["name"]  # Update name to use Alias
                db_device.status = device_data["status"]
                db_device.connection_info = json.dumps(device_data["connection_info"])
                db_device.last_seen = current_time
            else:
                # Create new device
                db_device = DBDevice(
                    device_id=device_data["device_id"],
                    device_type=device_data["device_type"],
                    name=device_data["name"],
                    status=device_data["status"],
                    connection_info=json.dumps(device_data["connection_info"]),
                    last_seen=current_time,
                    tags="[]"
                )
                db.add(db_device)
        
        # Mark devices as offline if not seen
        offline_threshold = current_time - timedelta(minutes=5)
        offline_devices = db.query(DBDevice).filter(
            DBDevice.last_seen < offline_threshold,
            DBDevice.status != "offline"
        ).all()
        
        for device in offline_devices:
            if device.device_id not in scanned_device_ids:
                device.status = "offline"
        
        db.commit()
        
        # Broadcast update to WebSocket clients from the main event loop
        if event_loop and not event_loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast({
                        "type": "device_update",
                        "timestamp": current_time.isoformat()
                    }),
                    event_loop,
                )
            except RuntimeError as exc:
                print(f"Failed to schedule broadcast: {exc}")
        else:
            print("Event loop unavailable, skipping device update broadcast")
        
    except Exception as e:
        print(f"Error updating devices: {e}")
        db.rollback()
    finally:
        db.close()

# Lifecycle management hooks
def start_scheduler():
    """Start the background scheduler if it is not already running."""
    global scheduler
    if scheduler and scheduler.running:
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(update_devices_in_db, "interval", seconds=30)
    scheduler.start()


def stop_scheduler():
    """Stop the background scheduler if it is running."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler = None


@app.on_event("startup")
async def on_startup() -> None:
    """Initialize database and background services."""
    global event_loop
    create_tables()
    event_loop = asyncio.get_running_loop()
    start_scheduler()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Clean up background services."""
    stop_scheduler()

# Authentication endpoints
@app.post("/auth/register", response_model=User)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(DBUser).filter(DBUser.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = DBUser(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/auth/login", response_model=Token)
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=User)
def read_users_me(current_user: DBUser = Depends(get_current_active_user)):
    return current_user

# Device management endpoints
@app.get("/api/devices", response_model=List[DeviceWithUser])
def get_devices(
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    group: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(DBDevice)
    
    if device_type:
        query = query.filter(DBDevice.device_type == device_type)
    if status:
        query = query.filter(DBDevice.status == status)
    if search:
        query = query.filter(
            DBDevice.name.contains(search) | 
            DBDevice.device_id.contains(search)
        )
    if group:
        query = query.filter(DBDevice.group_name == group)
    
    devices = query.offset(skip).limit(limit).all()
    
    # Convert to response model with user info
    result = []
    for device in devices:
        device_dict = {
            "id": device.id,
            "device_id": device.device_id,
            "device_type": device.device_type,
            "name": device.name,
            "status": device.status,
            "connection_info": json.loads(device.connection_info) if device.connection_info else {},
            "last_seen": device.last_seen,
            "created_at": device.created_at,
            "occupied_by": device.occupied_by,
            "occupied_at": device.occupied_at,
            "group_name": device.group_name,
            "tags": json.loads(device.tags) if device.tags else [],
            "user": None
        }
        
        if device.occupied_by:
            user = db.query(DBUser).filter(DBUser.id == device.occupied_by).first()
            if user:
                device_dict["user"] = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at
                }
        
        result.append(device_dict)
    
    return result

@app.get("/api/devices/stats", response_model=DeviceStats)
def get_device_stats(db: Session = Depends(get_db)):
    total = db.query(DBDevice).count()
    online = db.query(DBDevice).filter(DBDevice.status == "online").count()
    occupied = db.query(DBDevice).filter(DBDevice.occupied_by.isnot(None)).count()
    offline = db.query(DBDevice).filter(DBDevice.status == "offline").count()
    
    # Count by device type
    devices_by_type = {}
    for device_type, count in db.query(DBDevice.device_type, func.count(DBDevice.id)).group_by(DBDevice.device_type).all():
        devices_by_type[device_type] = count
    
    return DeviceStats(
        total_devices=total,
        online_devices=online,
        occupied_devices=occupied,
        offline_devices=offline,
        devices_by_type=devices_by_type
    )

@app.post("/api/devices/{device_id}/occupy")
def occupy_device(
    device_id: str,
    request: DeviceOccupyRequest,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.occupied_by:
        raise HTTPException(status_code=400, detail="Device is already occupied")
    
    if device.status == "offline":
        raise HTTPException(status_code=400, detail="Cannot occupy offline device")
    
    # Occupy the device
    device.occupied_by = current_user.id
    device.occupied_at = datetime.utcnow()
    device.status = "occupied"
    
    # Log the action
    log = DBDeviceUsageLog(
        device_id=device.id,
        user_id=current_user.id,
        action="occupy",
        notes=request.notes
    )
    db.add(log)
    db.commit()
    
    return {"message": "Device occupied successfully"}

@app.post("/api/devices/{device_id}/release")
def release_device(
    device_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if not device.occupied_by:
        raise HTTPException(status_code=400, detail="Device is not occupied")
    
    # Check if user can release (owner or admin)
    if device.occupied_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to release this device")
    
    # Release the device
    device.occupied_by = None
    device.occupied_at = None
    device.status = "online" if device.status == "occupied" else device.status
    
    # Log the action
    log = DBDeviceUsageLog(
        device_id=device.id,
        user_id=current_user.id,
        action="release"
    )
    db.add(log)
    db.commit()
    
    return {"message": "Device released successfully"}

@app.put("/api/devices/{device_id}")
def update_device(
    device_id: str,
    device_update: DeviceUpdate,
    current_user: DBUser = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device_update.name is not None:
        device.name = device_update.name
    if device_update.status is not None:
        device.status = device_update.status
    if device_update.group_name is not None:
        device.group_name = device_update.group_name
    if device_update.tags is not None:
        device.tags = json.dumps(device_update.tags)
    if device_update.connection_info is not None:
        existing_info = json.loads(device.connection_info) if device.connection_info else {}
        existing_info.update(device_update.connection_info)
        device.connection_info = json.dumps(existing_info)
    
    db.commit()
    return {"message": "Device updated successfully"}

@app.get("/api/devices/{device_id}/logs", response_model=List[DeviceUsageLogWithDetails])
def get_device_logs(
    device_id: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    logs = db.query(DBDeviceUsageLog).filter(
        DBDeviceUsageLog.device_id == device.id
    ).order_by(DBDeviceUsageLog.timestamp.desc()).offset(skip).limit(limit).all()
    
    result = []
    for log in logs:
        user = db.query(DBUser).filter(DBUser.id == log.user_id).first()
        result.append({
            "id": log.id,
            "device_id": log.device_id,
            "user_id": log.user_id,
            "action": log.action,
            "timestamp": log.timestamp,
            "notes": log.notes,
            "device": {
                "id": device.id,
                "device_id": device.device_id,
                "device_type": device.device_type,
                "name": device.name,
                "status": device.status,
                "connection_info": json.loads(device.connection_info) if device.connection_info else {},
                "last_seen": device.last_seen,
                "created_at": device.created_at,
                "occupied_by": device.occupied_by,
                "occupied_at": device.occupied_at,
                "group_name": device.group_name,
                "tags": json.loads(device.tags) if device.tags else []
            },
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at
            } if user else None
        })
    
    return result

# Legacy endpoints for backward compatibility
@app.get("/devices")
def get_devices_legacy():
    """Legacy endpoint - get ADB devices only."""
    devices = scan_adb_devices()
    return {"devices": [d["device_id"] for d in devices if d["device_type"] == "adb"]}

@app.get("/bluetooth/infos")
def get_bluetooth_infos_legacy():
    """Legacy endpoint - get bluetooth device info."""
    devices = scan_bluetooth_devices()
    
    # Group by ADB host
    result = {}
    for device in devices:
        adb_host = device["connection_info"].get("adb_host", "unknown")
        if adb_host not in result:
            result[adb_host] = {
                "device_id": adb_host,
                "bluetooth_devices": []
            }
        
        result[adb_host]["bluetooth_devices"].append({
            "mac": device["device_id"],
            "name": device["name"],
            "output": device["connection_info"].get("raw_output", ""),
            "parsed": device["connection_info"].get("bluetooth_info", {})
        })
    
    return {"results": list(result.values())}

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Trigger manual device scan
@app.post("/api/devices/scan")
def trigger_device_scan(current_user: DBUser = Depends(get_current_active_user)):
    update_devices_in_db()
    return {"message": "Device scan triggered successfully"}

# Bluetooth control endpoints
@app.post("/api/devices/{device_id}/bluetooth/connect")
def bluetooth_connect(
    device_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.device_type != "bluetooth":
        raise HTTPException(status_code=400, detail="Device is not a Bluetooth device")
    
    try:
        # Get connection info to find ADB host
        connection_info = json.loads(device.connection_info) if device.connection_info else {}
        adb_host = connection_info.get("adb_host")
        
        if not adb_host:
            raise HTTPException(status_code=400, detail="No ADB host found for this Bluetooth device")
        
        # Execute bluetooth connect command
        cmd = ["adb", "-s", adb_host, "shell", "bluetoothctl", "connect", device_id]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Log the action
        log = DBDeviceUsageLog(
            device_id=device.id,
            user_id=current_user.id,
            action="bluetooth_connect",
            notes=f"Bluetooth connect command executed: {' '.join(cmd)}"
        )
        db.add(log)
        db.commit()
        
        # Trigger device scan to update status
        update_devices_in_db()
        
        return {
            "message": "Bluetooth connect command sent successfully",
            "output": result.stdout,
            "command": ' '.join(cmd)
        }
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Bluetooth connect failed: {e.stderr}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/devices/{device_id}/bluetooth/disconnect")
def bluetooth_disconnect(
    device_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.device_type != "bluetooth":
        raise HTTPException(status_code=400, detail="Device is not a Bluetooth device")
    
    try:
        # Get connection info to find ADB host
        connection_info = json.loads(device.connection_info) if device.connection_info else {}
        adb_host = connection_info.get("adb_host")
        
        if not adb_host:
            raise HTTPException(status_code=400, detail="No ADB host found for this Bluetooth device")
        
        # Execute bluetooth disconnect command
        cmd = ["adb", "-s", adb_host, "shell", "bluetoothctl", "disconnect", device_id]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Log the action
        log = DBDeviceUsageLog(
            device_id=device.id,
            user_id=current_user.id,
            action="bluetooth_disconnect",
            notes=f"Bluetooth disconnect command executed: {' '.join(cmd)}"
        )
        db.add(log)
        db.commit()
        
        # Trigger device scan to update status
        update_devices_in_db()
        
        return {
            "message": "Bluetooth disconnect command sent successfully",
            "output": result.stdout,
            "command": ' '.join(cmd)
        }
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Bluetooth disconnect failed: {e.stderr}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/devices/{device_id}/bluetooth/pair")
def bluetooth_pair(
    device_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.device_type != "bluetooth":
        raise HTTPException(status_code=400, detail="Device is not a Bluetooth device")
    
    try:
        # Get connection info to find ADB host
        connection_info = json.loads(device.connection_info) if device.connection_info else {}
        adb_host = connection_info.get("adb_host")
        
        if not adb_host:
            raise HTTPException(status_code=400, detail="No ADB host found for this Bluetooth device")
        
        # Execute bluetooth pair command
        cmd = ["adb", "-s", adb_host, "shell", "bluetoothctl", "pair", device_id]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Log the action
        log = DBDeviceUsageLog(
            device_id=device.id,
            user_id=current_user.id,
            action="bluetooth_pair",
            notes=f"Bluetooth pair command executed: {' '.join(cmd)}"
        )
        db.add(log)
        db.commit()
        
        # Trigger device scan to update status
        update_devices_in_db()
        
        return {
            "message": "Bluetooth pair command sent successfully",
            "output": result.stdout,
            "command": ' '.join(cmd)
        }
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Bluetooth pair failed: {e.stderr}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices/{device_id}/bluetooth/info")
def get_device_bluetooth_info(
    device_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get Bluetooth information for an ADB device."""
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.device_type != "adb":
        raise HTTPException(status_code=400, detail="Device is not an ADB device")
    
    try:
        bluetooth_info = get_adb_bluetooth_info(device_id)
        return {
            "device_id": device_id,
            "bluetooth_info": bluetooth_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Bluetooth info: {str(e)}")

@app.get("/api/devices/{device_id}/wifi/ap/info")
def get_device_wifi_ap_info(
    device_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get WiFi AP information for an ADB device."""
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.device_type != "adb":
        raise HTTPException(status_code=400, detail="Device is not an ADB device")
    
    try:
        wifi_ap_info = get_adb_wifi_ap_info(device_id)
        return {
            "device_id": device_id,
            "wifi_ap_info": wifi_ap_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get WiFi AP info: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)