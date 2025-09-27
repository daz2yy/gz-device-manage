from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    Query,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import PlainTextResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import subprocess
import re
import json
import os
import tempfile
import posixpath
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import logging
import threading
import time

# Import our modules
from database import get_db, create_tables, Device as DBDevice, User as DBUser, DeviceUsageLog as DBDeviceUsageLog, SessionLocal
from models import *
from auth import *

app = FastAPI(title="Device Management System", version="1.0.0")

logger = logging.getLogger(__name__)

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
update_lock = threading.Lock()


def _broadcast_device_update(timestamp: datetime) -> None:
    """Send device update notifications to connected WebSocket clients."""
    loop = getattr(app.state, "event_loop", None)
    if not loop or not loop.is_running():
        logger.debug("Event loop is not available for WebSocket broadcast")
        return

    future = asyncio.run_coroutine_threadsafe(
        manager.broadcast({
            "type": "device_update",
            "timestamp": timestamp.isoformat(),
        }),
        loop,
    )

    def _log_future_result(fut: asyncio.Future) -> None:
        try:
            fut.result()
        except Exception as exc:  # pragma: no cover - log unexpected broadcast errors
            logger.error("WebSocket broadcast failed: %s", exc)

    future.add_done_callback(_log_future_result)

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
        elif k == "tx_power":
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



def parse_mount_output(mount_output: str) -> Dict[str, Dict[str, Any]]:
    """Parse `mount` command output into a dictionary keyed by mount point."""
    mounts: Dict[str, Dict[str, Any]] = {}
    pattern = re.compile(r"^(?P<source>\S+) on (?P<mountpoint>\S+) type (?P<fstype>\S+) \((?P<options>[^)]*)\)")

    for raw_line in mount_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = pattern.match(line)
        if not match:
            continue

        options = [opt.strip() for opt in match.group("options").split(',') if opt.strip()]
        mounts[match.group("mountpoint")] = {
            "source": match.group("source"),
            "fstype": match.group("fstype"),
            "options": options,
            "writable": any(opt.startswith("rw") for opt in options)
        }

    return mounts


def _parse_int(value: str) -> Optional[int]:
    """Convert numeric strings that may include commas into integers."""
    if value is None:
        return None
    stripped = value.replace(',', '').strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _parse_percent(value: str) -> Optional[float]:
    """Parse percentage strings such as '45%' into float values."""
    if value is None:
        return None
    stripped = value.strip().rstrip('%')
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def parse_df_output(df_output: str) -> Optional[Dict[str, Any]]:
    """Parse `df` command output (single path) into structured usage details."""
    if not df_output:
        return None

    data_lines = []
    for raw_line in df_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("filesystem"):
            continue
        data_lines.append(line)

    if not data_lines:
        return None

    last_line = data_lines[-1]
    parts = re.split(r"\s+", last_line)
    if len(parts) < 6:
        return None

    filesystem = parts[0]
    size_kb = _parse_int(parts[-5])
    used_kb = _parse_int(parts[-4])
    available_kb = _parse_int(parts[-3])
    used_percent = _parse_percent(parts[-2])
    mounted_on = parts[-1]

    used_ratio = None
    if size_kb and used_kb is not None and size_kb > 0:
        used_ratio = used_kb / size_kb

    return {
        "filesystem": filesystem,
        "mounted_on": mounted_on,
        "size_kb": size_kb,
        "used_kb": used_kb,
        "available_kb": available_kb,
        "used_percent": used_percent,
        "used_ratio": used_ratio,
        "raw_line": last_line,
    }


def collect_path_usage(device_id: str, paths: List[str]) -> Dict[str, Dict[str, Any]]:
    """Gather filesystem usage statistics for the given paths via `adb df`."""
    usage: Dict[str, Dict[str, Any]] = {}

    for path in paths:
        cmd = ["adb", "-s", device_id, "shell", "df", "-k", path]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            usage[path] = {
                "path": path,
                "success": False,
                "error": str(exc),
                "raw_output": None,
            }
            continue

        parsed = parse_df_output(result.stdout)
        if parsed:
            used_percent = parsed.get("used_percent")
            if used_percent is None:
                size_kb = parsed.get("size_kb")
                used_kb = parsed.get("used_kb")
                if size_kb and used_kb is not None and size_kb > 0:
                    parsed["used_percent"] = (used_kb / size_kb) * 100

            usage[path] = {
                "path": path,
                "success": True,
                **parsed,
                "raw_output": result.stdout,
            }
        else:
            error_message = result.stderr.strip() or "Unable to parse df output"
            usage[path] = {
                "path": path,
                "success": False,
                "error": error_message,
                "raw_output": result.stdout,
            }

    return usage


def parse_version_output(version_output: str) -> Dict[str, Any]:
    """Parse ql-getversion output into structured build/module versions."""

    build_info: Dict[str, Optional[str]] = {
        "version": None,
        "build_time": None,
        "hostname": None,
        "commit": None,
        "branch": None,
    }

    module_versions: Dict[str, Optional[str]] = {
        "camera_soc": None,
        "camera_mcu": None,
        "cabin_soc": None,
        "cabin_mcu": None,
    }

    ic_version: Optional[str] = None
    in_build_section = False

    for raw_line in version_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower_line = line.lower()

        if "build info start" in lower_line:
            in_build_section = True
            continue
        if "build info end" in lower_line:
            in_build_section = False
            continue

        if in_build_section:
            match = re.search(r"build info\s+(?P<key>\w+)\s*(?P<value>.+)", line, re.IGNORECASE)
            if match:
                key = match.group("key").lower()
                value = match.group("value").strip() or None
                if key in build_info:
                    build_info[key] = value
            continue

        if "geticversion" in lower_line and "version" in lower_line:
            matches = re.findall(r"version[:：]\s*([^,\s]+)", line, re.IGNORECASE)
            if matches:
                ic_version = matches[-1].strip() or None
            continue

        if "getallversion" in lower_line and "version:" in lower_line:
            version_str = line.rsplit("version:", 1)[1]
            for pair in version_str.split(','):
                key, _, value = pair.partition(':')
                key = key.strip().lower()
                value = value.strip() or None
                if key in module_versions:
                    module_versions[key] = value
            continue

    if not module_versions.get("camera_mcu") and ic_version:
        module_versions["camera_mcu"] = ic_version

    normalized: Dict[str, Any] = {
        "host": module_versions.get("camera_soc") or build_info.get("version"),
        "host_starflash": module_versions.get("camera_mcu"),
        "cabin": module_versions.get("cabin_soc"),
        "cabin_starflash": module_versions.get("cabin_mcu"),
        "build_info": {k: v for k, v in build_info.items() if v},
        "module_versions": module_versions,
    }

    return normalized


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
    if not update_lock.acquire(blocking=False):
        logger.debug("Device update skipped because a previous run is still in progress")
        return

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
        logger.exception("Error updating devices: %s", e)
        db.rollback()
    finally:
        db.close()
        update_lock.release()


@app.on_event("startup")
async def startup_event():
    """Initialize resources when the application starts."""
    global scheduler

    create_tables()
    loop = asyncio.get_running_loop()
    app.state.event_loop = loop

    # Run an immediate device scan without blocking the event loop
    await loop.run_in_executor(None, update_devices_in_db)

    if scheduler is None:
        scheduler = BackgroundScheduler()

    if not scheduler.running:
        scheduler.add_job(
            update_devices_in_db,
            "interval",
            seconds=30,
            id="device_monitor",
            replace_existing=True,
        )
        scheduler.start()


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
        connection_info = json.loads(device.connection_info) if device.connection_info else {}
        adb_host = connection_info.get("adb_host")

        if not adb_host:
            raise HTTPException(status_code=400, detail="No ADB host found for this Bluetooth device")

        cmd = ["adb", "-s", adb_host, "shell", "bluetoothctl", "connect", device_id]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = stdout or stderr

        message = "Bluetooth connect command sent successfully"
        if result.returncode != 0:
            lower_combined = combined.lower()
            if "already" in lower_combined:
                message = "Bluetooth device is already connecting or connected"
            else:
                error_detail = combined or "Unknown error"
                raise HTTPException(status_code=500, detail=f"Bluetooth connect failed: {error_detail}")

        log = DBDeviceUsageLog(
            device_id=device.id,
            user_id=current_user.id,
            action="bluetooth_connect",
            notes=f"Bluetooth connect command executed: {' '.join(cmd)} | stdout: {stdout} | stderr: {stderr}"
        )
        db.add(log)
        db.commit()

        update_devices_in_db()

        return {
            "message": message,
            "output": stdout,
            "error_output": stderr,
            "command": ' '.join(cmd)
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
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
        connection_info = json.loads(device.connection_info) if device.connection_info else {}
        adb_host = connection_info.get("adb_host")

        if not adb_host:
            raise HTTPException(status_code=400, detail="No ADB host found for this Bluetooth device")

        cmd = ["adb", "-s", adb_host, "shell", "bluetoothctl", "disconnect", device_id]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode != 0:
            error_detail = stdout or stderr or "Unknown error"
            raise HTTPException(status_code=500, detail=f"Bluetooth disconnect failed: {error_detail}")

        log = DBDeviceUsageLog(
            device_id=device.id,
            user_id=current_user.id,
            action="bluetooth_disconnect",
            notes=f"Bluetooth disconnect command executed: {' '.join(cmd)} | stdout: {stdout} | stderr: {stderr}"
        )
        db.add(log)
        db.commit()

        update_devices_in_db()

        return {
            "message": "Bluetooth disconnect command sent successfully",
            "output": stdout,
            "error_output": stderr,
            "command": ' '.join(cmd)
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
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
        connection_info = json.loads(device.connection_info) if device.connection_info else {}
        adb_host = connection_info.get("adb_host")

        if not adb_host:
            raise HTTPException(status_code=400, detail="No ADB host found for this Bluetooth device")

        cmd = ["adb", "-s", adb_host, "shell", "bluetoothctl", "pair", device_id]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = stdout or stderr

        message = "Bluetooth pair command sent successfully"
        if result.returncode != 0:
            lower_combined = combined.lower()
            if "already" in lower_combined:
                message = "Bluetooth device already paired"
            else:
                error_detail = combined or "Unknown error"
                raise HTTPException(status_code=500, detail=f"Bluetooth pair failed: {error_detail}")

        log = DBDeviceUsageLog(
            device_id=device.id,
            user_id=current_user.id,
            action="bluetooth_pair",
            notes=f"Bluetooth pair command executed: {' '.join(cmd)} | stdout: {stdout} | stderr: {stderr}"
        )
        db.add(log)
        db.commit()

        update_devices_in_db()

        return {
            "message": message,
            "output": stdout,
            "error_output": stderr,
            "command": ' '.join(cmd)
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
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


@app.get("/api/devices/{device_id}/filesystem/mounts")
def get_device_mounts(
    device_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Inspect mount information for critical paths on an ADB device."""
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.device_type != "adb":
        raise HTTPException(status_code=400, detail="Filesystem inspection is only supported for ADB devices")

    adb_cmd = ["adb", "-s", device_id, "shell", "mount"]
    try:
        result = subprocess.run(
            adb_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to execute mount command: {str(exc)}")

    if result.returncode != 0 and result.returncode == 255:
        subprocess.run(
            ["adb", "-s", device_id, "wait-for-device"],
            capture_output=True,
            text=True,
            check=False,
        )
        time.sleep(0.5)
        result = subprocess.run(
            adb_cmd,
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode != 0:
        error_message = result.stderr.strip() or result.stdout.strip() or f"adb exited with code {result.returncode}"
        raise HTTPException(status_code=500, detail=f"Failed to execute mount command: {error_message}")

    mounts = parse_mount_output(result.stdout)
    mount_points = ["/", "/data", "/data/zhuimi"]
    usage_map = collect_path_usage(device_id, mount_points)
    mount_details = []

    for mount_point in mount_points:
        entry = mounts.get(mount_point)
        usage_entry = usage_map.get(mount_point)
        mount_details.append({
            "mount_point": mount_point,
            "found": entry is not None,
            "source": entry.get("source") if entry else None,
            "fstype": entry.get("fstype") if entry else None,
            "options": entry.get("options") if entry else [],
            "writable": bool(entry.get("writable")) if entry else False,
            "usage": usage_entry,
        })

    zhuimi_info = next((item for item in mount_details if item["mount_point"] == "/data/zhuimi"), None)

    return {
        "device_id": device_id,
        "mounts": mount_details,
        "path_usage": list(usage_map.values()),
        "zhuimi_writable": zhuimi_info.get("writable") if zhuimi_info else False,
        "raw_output": result.stdout,
    }


@app.get("/api/devices/{device_id}/versions")
def get_device_versions(
    device_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Fetch version information from an ADB device via ql-getversion."""
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.device_type != "adb":
        raise HTTPException(status_code=400, detail="Version query is only supported for ADB devices")

    try:
        result = subprocess.run(
            ["adb", "-s", device_id, "shell", "ql-getversion"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        error_message = getattr(exc, "stderr", None) or str(exc)
        raise HTTPException(status_code=500, detail=f"Failed to execute ql-getversion: {error_message}")

    versions = parse_version_output(result.stdout)

    return {
        "device_id": device_id,
        "versions": versions,
        "raw_output": result.stdout,
    }


@app.post("/api/devices/{device_id}/filesystem/push")
async def push_file_to_device(
    device_id: str,
    file: UploadFile = File(...),
    remote_dir: str = Form("/data"),
    remote_filename: Optional[str] = Form(None),
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Upload a file from the API host to the device via ADB push."""
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.device_type != "adb":
        raise HTTPException(status_code=400, detail="File push is only supported for ADB devices")

    if device.status not in {"online", "occupied"}:
        raise HTTPException(status_code=400, detail="Device must be online to receive files")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename")

    try:
        contents = await file.read()
    except Exception as exc:  # pragma: no cover - defensive read guard
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {exc}")

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    target_dir = (remote_dir or "/data").strip() or "/data"
    if not target_dir.startswith("/"):
        raise HTTPException(status_code=400, detail="Remote directory must be an absolute path")

    filename = remote_filename.strip() if remote_filename else file.filename
    filename = os.path.basename(filename)
    if not filename:
        raise HTTPException(status_code=400, detail="Remote filename cannot be empty")

    remote_path = posixpath.join(target_dir.rstrip("/"), filename)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(contents)
            tmp.flush()
            tmp_path = tmp.name

        result = subprocess.run(
            ["adb", "-s", device_id, "push", tmp_path, remote_path],
            capture_output=True,
            text=True,
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = stdout or stderr

        if result.returncode != 0:
            error_detail = combined or "Unknown error"
            raise HTTPException(status_code=500, detail=f"ADB push failed: {error_detail}")

        log = DBDeviceUsageLog(
            device_id=device.id,
            user_id=current_user.id,
            action="filesystem_push",
            notes=f"Pushed {filename} to {remote_path} ({len(contents)} bytes)",
        )
        db.add(log)
        db.commit()

        return {
            "message": "File pushed successfully",
            "remote_path": remote_path,
            "command": f"adb -s {device_id} push <uploaded> {remote_path}",
            "output": stdout,
        }

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@app.get("/api/devices/{device_id}/logs/fastapi")
def download_fastapi_log(
    device_id: str,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download the FastAPI log file from the device."""
    device = db.query(DBDevice).filter(DBDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.device_type != "adb":
        raise HTTPException(status_code=400, detail="Log retrieval is only supported for ADB devices")

    log_paths = [
        "/tmp/log_FastCGIServer.log",
    ]

    stdout = ""
    stderr = ""
    selected_path = None
    error_state: Optional[HTTPException] = None

    for log_path in log_paths:
        result = subprocess.run(
            ["adb", "-s", device_id, "shell", "cat", log_path],
            capture_output=True,
            text=True,
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = stdout or stderr

        if result.returncode == 0:
            selected_path = log_path
            break

        lower_combined = combined.lower()
        if "no such file" in lower_combined or "not found" in lower_combined:
            error_state = HTTPException(status_code=404, detail=f"FastAPI log file not found on device at {log_path}")
        else:
            error_state = HTTPException(status_code=500, detail=f"Failed to read log file {log_path}: {combined or 'Unknown error'}")

    if not selected_path:
        raise error_state or HTTPException(status_code=500, detail="Failed to read FastAPI log from device")

    log_entry = DBDeviceUsageLog(
        device_id=device.id,
        user_id=current_user.id,
        action="download_fastapi_log",
        notes=f"Downloaded {selected_path} via API",
    )
    db.add(log_entry)
    db.commit()

    filename = f"{device_id}_log_FastCGIServer.log"

    return PlainTextResponse(
        stdout,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
