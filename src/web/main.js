const canvas = document.getElementById('tactical-map');
const ctx = canvas.getContext('2d');
let currentState = null;

const mapImg = new Image();
mapImg.src = 'assets/map.png';

function resizeCanvas() {
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = canvas.parentElement.clientHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

async function pollState() {
    try {
        const response = await fetch('/api/state');
        currentState = await response.json();
        updateUI();
        drawMap();
    } catch (e) {
        console.error("Link failed:", e);
        document.getElementById('sys-status').innerText = "STATUS: LINK ERROR";
        document.getElementById('sys-status').style.color = "var(--crit-color)";
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

    // Update Task List
    const taskList = document.getElementById('task-list');
    if (taskList) {
        taskList.innerHTML = currentState.queue.map(task => `
            <div class="task-item ${task.status.toLowerCase()}">
                <span class="task-stage">${task.stage.replace('_', ' ')}</span>
                <div style="font-size: 0.85rem; color: #fff;">${task.description}</div>
                <div class="task-progress-container">
                    <div class="task-progress-fill" style="width: ${task.progress}%"></div>
                </div>
                <div style="font-size: 0.6rem; text-align: right; margin-top: 5px; opacity: 0.7;">
                    SAT-${task.assigned_satellite_id || 'NONE'} | ${task.status}
                </div>
            </div>
        `).join('');
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
    
    // Clear Link Error if we are here
    const status = document.getElementById('sys-status');
    if (status && status.innerText === "STATUS: LINK ERROR") {
        status.innerText = "STATUS: NOMINAL";
        status.style.color = "var(--primary-color)";
    }
}

function drawMap() {
    if (!currentState) return;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (mapImg.complete) {
        ctx.globalAlpha = 0.4;
        ctx.drawImage(mapImg, 0, 0, canvas.width, canvas.height);
        ctx.globalAlpha = 1.0;
    }

    const mapX = (lon) => ((lon + 180) / 360) * canvas.width;
    const mapY = (lat) => ((90 - lat) / 180) * canvas.height;

    // Satellites
    currentState.satellites.forEach(sat => {
        const x = mapX(sat.lon);
        const y = mapY(sat.lat);
        
        ctx.fillStyle = sat.status === 'IDLE' ? '#00ff41' : '#ffcc00';
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();

        // Pulsing if imaging
        if (sat.status === 'IMAGING') {
            ctx.strokeStyle = '#00d4ff';
            ctx.beginPath();
            ctx.arc(x, y, 10 + (Date.now()%1000)/100, 0, Math.PI * 2);
            ctx.stroke();
        }

        ctx.font = '10px Courier New';
        ctx.fillText(sat.name, x + 8, y + 4);
    });

    // Fire Zones
    currentState.fire_zones.forEach(fz => {
        const x = mapX(fz.lon);
        const y = mapY(fz.lat);
        const grad = ctx.createRadialGradient(x, y, 0, x, y, 15);
        grad.addColorStop(0, 'rgba(255, 0, 0, 0.8)');
        grad.addColorStop(1, 'rgba(255, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(x, y, 15, 0, Math.PI * 2);
        ctx.fill();
    });
}

async function igniteFire() {
    await fetch('/api/ignite', { method: 'POST' });
}

async function clearState() {
    await fetch('/api/clear', { method: 'POST' });
}

setInterval(pollState, 1000);
pollState();
