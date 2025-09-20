from fastapi import FastAPI, Query
import subprocess
from typing import List, Optional, Dict, Any
import re

app = FastAPI()


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
        "uuids": [],  # list of {uuid, desc}
        "manufacturer_data": {},
    }

    if not text:
        return parsed

    # Pre-compile regex
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
            # Various formats observed, try to capture key-value pairs
            # e.g. "ManufacturerData Key: 0x004C" OR "ManufacturerData: 0x004c 06 1a ..."
            parts = val.split(None, 1)
            md_key = parts[0] if parts else None
            md_val = parts[1] if len(parts) > 1 else ""
            if md_key:
                parsed["manufacturer_data"][md_key] = md_val

    return parsed


@app.get("/devices")
def get_devices():
    """
    Get the list of connected devices using adb.
    """
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=True)
        devices = result.stdout.strip().split("\n")[1:]
        device_ids = [line.split("\t")[0] for line in devices if line and "\tdevice" in line]
        return {"devices": device_ids}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"error": "adb command not found or failed to execute."}


@app.get("/bluetooth")
def get_bluetooth_info():
    """
    Get bluetooth controller information using bluetoothctl show (on the default/only controller).
    """
    try:
        result = subprocess.run(["adb", "shell", "bluetoothctl", "show"], capture_output=True, text=True, check=True)
        return {"bluetooth_info": result.stdout}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"error": "bluetoothctl command not found or failed to execute."}


@app.get("/bluetooth/info")
def get_bluetooth_device_info(device_id: Optional[str] = Query(default=None, alias="device_id")):
    """
    Run `adb shell bluetoothctl info` to query connected device information.
    If `device_id` is provided, run the command on that specific ADB device.
    """
    try:
        base_cmd: List[str] = ["adb"]
        if device_id:
            base_cmd += ["-s", device_id]
        base_cmd += ["shell", "bluetoothctl", "info"]
        result = subprocess.run(base_cmd, capture_output=True, text=True, check=True)
        output = result.stdout
        return {"device_id": device_id, "output": output, "parsed": parse_bluetoothctl_info(output)}
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return {"device_id": device_id, "error": "failed to execute bluetoothctl info", "detail": str(e)}


@app.get("/bluetooth/infos")
def get_bluetooth_device_infos():
    """
    For all connected ADB devices, get paired bluetooth devices and run `bluetoothctl info` for each.
    """
    infos = []
    try:
        # get connected adb devices first
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split("\n")[1:]
        device_ids = [line.split("\t")[0] for line in lines if line and "\tdevice" in line]
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return {"error": "adb command not found or failed to execute.", "detail": str(e)}

    for did in device_ids:
        try:
            # First get the list of paired bluetooth devices
            cmd = ["adb", "-s", did, "shell", "bluetoothctl", "devices"]
            r = subprocess.run(cmd, capture_output=True, text=True, check=True)
            devices_output = r.stdout.strip()
            
            if not devices_output:
                # No paired devices
                infos.append({
                    "device_id": did, 
                    "bluetooth_devices": [],
                    "message": "No paired bluetooth devices found"
                })
                continue
            
            # Parse device list (format: "Device XX:XX:XX:XX:XX:XX DeviceName")
            bluetooth_devices = []
            for line in devices_output.split("\n"):
                line = line.strip()
                if line.startswith("Device "):
                    parts = line.split(" ", 2)
                    if len(parts) >= 2:
                        mac_addr = parts[1]
                        device_name = parts[2] if len(parts) > 2 else "Unknown"
                        
                        # Get info for this specific bluetooth device
                        try:
                            info_cmd = ["adb", "-s", did, "shell", "bluetoothctl", "info", mac_addr]
                            info_result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
                            bluetooth_devices.append({
                                "mac": mac_addr,
                                "name": device_name,
                                "output": info_result.stdout,
                                "parsed": parse_bluetoothctl_info(info_result.stdout)
                            })
                        except (subprocess.CalledProcessError, FileNotFoundError) as e:
                            bluetooth_devices.append({
                                "mac": mac_addr,
                                "name": device_name,
                                "error": "failed to get device info",
                                "detail": str(e)
                            })
            
            infos.append({
                "device_id": did, 
                "bluetooth_devices": bluetooth_devices
            })
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            infos.append({"device_id": did, "error": "failed to execute bluetoothctl devices", "detail": str(e)})

    return {"results": infos}