const API_URL = "https://smart-office-monitor-d41y.onrender.com/api/devices";//API_URL = "http://127.0.0.1:8000/api/devices";
const ALERTS_URL = "https://smart-office-monitor-d41y.onrender.com/api/alerts";//ALERTS_URL = "http://127.0.0.1:8000/api/alerts";
const RATE_PER_KWH = 12.73;

const devicePositions = {
    "DR_F1": { top: "15%", left: "19%" },
    "DR_F2": { top: "52%", left: "19%" },
    "DR_L1": { top: "12%", left: "10%" },
    "DR_L2": { top: "12%", left: "28%" },
    "DR_L3": { top: "63%", left: "19%" },
    "WR1_F1": { top: "15%", left: "51%" },
    "WR1_F2": { top: "48%", left: "51%" },
    "WR1_L1": { top: "12%", left: "43%" },
    "WR1_L2": { top: "12%", left: "60%" },
    "WR1_L3": { top: "63%", left: "51%" },
    "WR2_F1": { top: "15%", left: "82%" },
    "WR2_F2": { top: "48%", left: "82%" },
    "WR2_L1": { top: "12%", left: "74%" },
    "WR2_L2": { top: "12%", left: "91%" },
    "WR2_L3": { top: "63%", left: "82%" }
};

// Inline SVG for a realistic fan icon; converted to a data URI at runtime
const FAN_SVG = `
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
    <g transform='translate(32 32)'>
        <rect x='4' y='-6' width='24' height='12' rx='3' transform='rotate(0)' fill='#6b4f3a'/>
        <rect x='4' y='-6' width='24' height='12' rx='3' transform='rotate(120)' fill='#6b4f3a'/>
        <rect x='4' y='-6' width='24' height='12' rx='3' transform='rotate(240)' fill='#6b4f3a'/>
        <circle cx='0' cy='0' r='6' fill='#3e2f27'/>
    </g>
</svg>`;

const FAN_DATA_URI = 'data:image/svg+xml;utf8,' + encodeURIComponent(FAN_SVG);

function formatTime(isoString) {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function setConnStatus(state) {
    const el = document.getElementById("conn-status");
    const text = document.getElementById("conn-status-text");
    if (!el || !text) return;
    el.classList.remove("is-live", "is-down");
    if (state === "live") {
        el.classList.add("is-live");
        text.textContent = "Live";
    } else if (state === "down") {
        el.classList.add("is-down");
        text.textContent = "Disconnected";
    } else {
        text.textContent = "Connecting…";
    }
}

async function toggleDevice(deviceId) {
    try {
        const response = await fetch(`${API_URL}/${deviceId}/toggle`, { method: 'POST' });
        if (!response.ok) throw new Error('Toggle request failed');
        await fetchAndUpdateData();
    } catch (error) {
        console.error('Error toggling device:', error);
    }
}

async function fetchAndUpdateData() {
    try {
        const response = await fetch(API_URL);
        if (!response.ok) {
            setConnStatus("down");
            return;
        }
        const devices = await response.json();

        if (!devices || devices.length === 0) {
            setConnStatus("down");
            return;
        }
        setConnStatus("live");

        const alertResponse = await fetch(ALERTS_URL);
        const alerts = alertResponse.ok ? await alertResponse.json() : [];

        const rooms = {};
        devices.forEach(device => {
            if (!rooms[device.room]) {
                rooms[device.room] = { devices: [], power: 0 };
            }
            rooms[device.room].devices.push(device);
            if (device.status === 'ON') {
                rooms[device.room].power += device.power_draw;
            }
        });

        const totalPower = Object.values(rooms).reduce((sum, room) => sum + room.power, 0);
        const totalCost = (totalPower / 1000) * RATE_PER_KWH;

        document.getElementById('total-power').innerHTML = `${totalPower} <small>W</small>`;
        document.getElementById('total-cost').innerHTML = `${totalCost.toFixed(2)} <small>Tk/hr</small>`;

        // --- Sidebar: room-wise usage ---
        const roomSummary = document.getElementById('room-summary');
        const maxRoomPower = Math.max(1, ...Object.values(rooms).map(r => r.power));

        roomSummary.innerHTML = Object.entries(rooms)
            .map(([roomName, roomData]) => {
                const roomCost = (roomData.power / 1000) * RATE_PER_KWH;
                const onCount = roomData.devices.filter(d => d.status === 'ON').length;
                const pct = Math.round((roomData.power / maxRoomPower) * 100);
                return `
                    <div class="room-row">
                        <div class="room-row-top">
                            <span class="room-row-name">${roomName}</span>
                            <span class="room-row-cost">${roomCost.toFixed(2)} Tk/hr</span>
                        </div>
                        <div class="room-row-bar-track">
                            <div class="room-row-bar-fill" style="width:${pct}%"></div>
                        </div>
                        <div class="room-row-meta">
                            <span>${roomData.power} W</span>
                            <span>${onCount}/${roomData.devices.length} active</span>
                        </div>
                    </div>
                `;
            })
            .join('');

        // --- Sidebar: alerts ---
        const alertsList = document.getElementById('alerts-list');
        const noAlerts = document.getElementById('no-alerts');

        if (alerts.length > 0) {
            noAlerts.style.display = 'none';
            alertsList.style.display = 'flex';
            alertsList.innerHTML = alerts
                .map(a => `<div class="alert-item"><span class="alert-time">[${formatTime(a.timestamp)}]</span>${a.message}</div>`)
                .join('');
        } else {
            alertsList.style.display = 'none';
            alertsList.innerHTML = '';
            noAlerts.style.display = 'block';
        }

        // --- 2D plan: unchanged from the original working version ---
        const devicesContainer = document.getElementById('dynamic-devices');
        if (!devicesContainer) return;

        devicesContainer.innerHTML = '';

        devices.forEach(device => {
            const isOn = device.status === 'ON';
            const pos = devicePositions[device.id] || { top: '0%', left: '0%' };

            const deviceDiv = document.createElement('div');
            deviceDiv.className = `interactive-device ${isOn ? 'device-on' : 'device-off'}`;
            deviceDiv.style.top = pos.top;
            deviceDiv.style.left = pos.left;
            deviceDiv.title = `${device.room} - ${device.name} (${device.status})`;
            deviceDiv.onclick = () => toggleDevice(device.id);

            if (device.type === 'Fan') {
                const img = document.createElement('img');
                img.src = FAN_DATA_URI;
                img.alt = 'fan';
                img.className = `fan-img ${isOn ? 'spin' : ''}`;
                deviceDiv.appendChild(img);
            } else {
                const span = document.createElement('span');
                span.className = isOn ? 'icon glow' : 'icon';
                span.textContent = '💡';
                deviceDiv.appendChild(span);
            }

            devicesContainer.appendChild(deviceDiv);
        });
    } catch (error) {
        console.error('Error fetching live data:', error);
        setConnStatus("down");
    }
}

fetchAndUpdateData();
setInterval(fetchAndUpdateData, 2000);
