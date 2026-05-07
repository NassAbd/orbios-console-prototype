let map;
let satMarkers = {};
let fireMarkers = {};
let currentState = null;

// Initialize Leaflet Map
function initMap() {
    map = L.map('tactical-map', {
        center: [0, 0],
        zoom: 2,
        zoomControl: false,
        attributionControl: false
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
    }).addTo(map);
}

async function pollState() {
    try {
        const response = await fetch('/api/state');
        currentState = await response.json();
        updateUI();
        updateMap();
    } catch (e) {
        console.error("Link failed:", e);
        const status = document.getElementById('sys-status');
        if (status) {
            status.innerText = "STATUS: LINK ERROR";
            status.style.color = "var(--crit-color)";
        }
    }
}

function safeSetText(id, text) {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
}

function safeSetWidth(id, width) {
    const el = document.getElementById(id);
    if (el) el.style.width = width;
}

function updateUI() {
    if (!currentState) return;

    const tel = currentState.telemetry;
    safeSetText('cpu-val', `${tel.cpu_percent.toFixed(1)}%`);
    safeSetWidth('cpu-bar', `${tel.cpu_percent}%`);
    
    safeSetText('ram-val', `${tel.ram_percent.toFixed(1)}%`);
    safeSetWidth('ram-bar', `${tel.ram_percent}%`);
    
    safeSetText('temp-val', `${tel.temp_c.toFixed(1)}°C`);
    safeSetWidth('temp-bar', `${Math.min(100, (tel.temp_c/100)*100)}%`);
    
    safeSetText('disk-val', `${tel.disk_usage.toFixed(1)}%`);
    safeSetWidth('disk-bar', `${tel.disk_usage}%`);

    safeSetText('net-rx-val', `${tel.network_rx} MB/s`);
    safeSetText('net-tx-val', `${tel.network_tx} MB/s`);
    safeSetText('uptime-display', tel.uptime);
    safeSetText('proc-val', tel.processes_count);
    safeSetText('users-val', tel.users_count);
    
    const container = document.getElementById('container-val');
    if (container) {
        container.innerText = tel.container_status;
        container.style.color = tel.container_status === "HEALTHY" ? "var(--primary-color)" : "var(--warn-color)";
    }

    safeSetText('sat-count', `SATS: ${currentState.satellites.length}`);
    safeSetText('task-count', `ACTIVE: ${currentState.queue.filter(t => t.status !== "COMPLETED").length}`);

    // Update qstat Table
    const taskList = document.getElementById('task-list');
    if (taskList) {
        taskList.innerHTML = currentState.queue.map(task => {
            const statusChar = task.status === "QUEUED" ? "Q" : (task.status === "RUNNING" ? "R" : "C");
            return `
                <tr>
                    <td>${task.task_id}</td>
                    <td class="status-${statusChar}">${statusChar}</td>
                    <td>AI_INF</td>
                    <td>
                        <div class="progress-bar" style="width: 80px;">
                            <div class="progress-fill" style="width: ${task.progress}%"></div>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // Update Terminal
    const term = document.getElementById('terminal-log');
    if (term) {
        const oldScroll = term.scrollHeight - term.scrollTop <= term.clientHeight + 10;
        term.innerHTML = currentState.messages.map(msg => `
            <div class="msg-item ${msg.origin} ${msg.level}">
                [${new Date(msg.timestamp).toLocaleTimeString()}] [${msg.origin}] ${msg.payload}
            </div>
        `).join('');
        if (oldScroll) term.scrollTop = term.scrollHeight;
    }

    safeSetText('sys-clock', new Date().toLocaleString().toUpperCase());
}

function updateMap() {
    if (!currentState) return;

    // Satellites
    currentState.satellites.forEach(sat => {
        const pos = [sat.lat, sat.lon];
        if (satMarkers[sat.id]) {
            satMarkers[sat.id].setLatLng(pos);
        } else {
            satMarkers[sat.id] = L.circleMarker(pos, {
                radius: 5,
                color: '#00ff41',
                fillOpacity: 1
            }).addTo(map).bindTooltip(sat.name, { permanent: false, direction: 'right' });
        }
        
        // Color update
        satMarkers[sat.id].setStyle({
            color: sat.status === 'IDLE' ? '#00ff41' : '#ffcc00'
        });
    });

    // Fire Zones
    currentState.fire_zones.forEach(fz => {
        const pos = [fz.lat, fz.lon];
        if (!fireMarkers[fz.id]) {
            fireMarkers[fz.id] = L.circle(pos, {
                radius: 500000 * fz.intensity,
                color: '#ff3b30',
                fillColor: '#ff3b30',
                fillOpacity: 0.3,
                weight: 1
            }).addTo(map);
        } else {
            fireMarkers[fz.id].setRadius(500000 * fz.intensity);
        }
    });
}

async function igniteFire() {
    await fetch('/api/ignite', { method: 'POST' });
}

async function clearState() {
    await fetch('/api/clear', { method: 'POST' });
}

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    setInterval(pollState, 1000);
    pollState();
});
