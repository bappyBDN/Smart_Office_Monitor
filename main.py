import json
import random
import asyncio
from datetime import datetime
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Smart Office Monitor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = 'data.json'
file_lock = asyncio.Lock() # Race condition সল্ভ করার জন্য গ্লোবাল লক

# --- Helper Functions for Safe File Handling ---
async def read_data_safe():
    async with file_lock:
        if not os.path.exists(DATA_FILE): return []
        with open(DATA_FILE, 'r') as f:
            return json.load(f)

async def write_data_safe(data):
    async with file_lock:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)

# --- Realistic Background Simulator ---
async def smart_simulator():
    """সময় অনুযায়ী প্রবাবিলিটি বেসড সিমুলেটর"""
    while True:
        try:
            devices = await read_data_safe()
            if not devices:
                await asyncio.sleep(5)
                continue
                
            current_hour = datetime.now().hour
            changed = False
            
            for device in devices:
                # ডেমোর জন্য প্রতি সাইকেলে প্রতিটি ডিভাইসের স্টেট চেঞ্জ হওয়ার ২০% চান্স রাখছি
                if random.random() < 0.2:
                    if 9 <= current_hour < 17:
                        # অফিস টাইম: ৮০% সম্ভাবনা অন থাকার
                        new_status = "ON" if random.random() < 0.8 else "OFF"
                    else:
                        # ছুটির পর: ৯০% সম্ভাবনা অফ থাকার (বাকি ১০% অ্যালার্ট ট্রিগার করবে)
                        new_status = "OFF" if random.random() < 0.9 else "ON"
                        
                    if device["status"] != new_status:
                        device["status"] = new_status
                        device["last_changed"] = datetime.now().isoformat()
                        changed = True
            
            if changed:
                await write_data_safe(devices)
                
        except Exception as e:
            print(f"Simulator Error: {e}")
            
        await asyncio.sleep(40)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(smart_simulator())

# --- Core APIs ---
@app.get("/api/devices")
async def get_devices():
    return await read_data_safe()

@app.post("/api/devices/{device_id}/toggle")
async def toggle_device(device_id: str):
    devices = await read_data_safe()
    for device in devices:
        if device["id"] == device_id:
            device["status"] = "ON" if device["status"] == "OFF" else "OFF"
            device["last_changed"] = datetime.now().isoformat()
            await write_data_safe(devices)
            return {"message": "Success", "status": device["status"]}
    return {"error": "Device not found"}

# --- New: Backend Alerts API ---
@app.get("/api/alerts")
async def get_alerts():
    """
    Single source of truth for alert logic. Both the dashboard and the
    Discord bot read from this endpoint so they can never disagree.
    Each alert is a structured object with its own timestamp (the moment
    the alert was detected), not just a raw string.
    """
    devices = await read_data_safe()
    alerts = []
    now = datetime.now()
    current_hour = now.hour
    is_after_hours = current_hour < 9 or current_hour >= 17
    seen = set()  # de-dupe by (device_id, rule) instead of by message text

    for d in devices:
        if d["status"] != "ON":
            continue

        # Rule 1: still ON after office hours
        if is_after_hours:
            key = (d["id"], "after_hours")
            if key not in seen:
                seen.add(key)
                alerts.append({
                    "device_id": d["id"],
                    "room": d["room"],
                    "device_name": d["name"],
                    "rule": "after_hours",
                    "message": f"{d['room']}: {d['name']} is still ON after office hours!",
                    "timestamp": now.isoformat(),
                })

        # Rule 2: ON continuously for 2+ hours
        last_changed = datetime.fromisoformat(d["last_changed"])
        hours_on = (now - last_changed).total_seconds() / 3600
        if hours_on >= 2:
            key = (d["id"], "long_running")
            if key not in seen:
                seen.add(key)
                alerts.append({
                    "device_id": d["id"],
                    "room": d["room"],
                    "device_name": d["name"],
                    "rule": "long_running",
                    "message": f"{d['room']}: {d['name']} has been running for over 2 hours.",
                    "timestamp": now.isoformat(),
                })

    return alerts

# --- New: Room Summary API (For Discord Bot) ---
@app.get("/api/room/{room_name}")
async def get_room_summary(room_name: str):
    devices = await read_data_safe()
    room_devices = [d for d in devices if d["room"].lower().replace(" ", "") == room_name.lower().replace(" ", "")]
    
    if not room_devices:
        return {"error": "Room not found"}
        
    on_fans = sum(1 for d in room_devices if d["type"] == "Fan" and d["status"] == "ON")
    off_fans = sum(1 for d in room_devices if d["type"] == "Fan" and d["status"] == "OFF")
    on_lights = sum(1 for d in room_devices if d["type"] == "Light" and d["status"] == "ON")
    off_lights = sum(1 for d in room_devices if d["type"] == "Light" and d["status"] == "OFF")
    power = sum(d["power_draw"] for d in room_devices if d["status"] == "ON")
    
    return {
        "room_name": room_devices[0]["room"],
        "active_devices": {"fans": on_fans, "lights": on_lights},
        "inactive_devices": {"fans": off_fans, "lights": off_lights},
        "total_power_watts": power
    }