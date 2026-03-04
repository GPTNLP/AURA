const chatContainer = document.getElementById('chat-container');
const statusBadge = document.getElementById('status-badge');

// Connect to the local FastAPI WebSocket
const ws = new WebSocket(`ws://${window.location.host}/ws`);

ws.onopen = () => {
    updateStatus("Connected", "ready");
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "status") {
        let stateClass = "ready";
        if (data.data.includes("Listening")) stateClass = "listening";
        if (data.data.includes("Processing")) stateClass = "processing";
        updateStatus(data.data, stateClass);
    } 
    else if (data.type === "chat") {
        appendMessage(data.sender, data.text);
    }
};

ws.onclose = () => {
    updateStatus("Offline - Reconnecting...", "processing");
    // Optional: implement automatic reconnect logic here
};

function updateStatus(text, stateClass) {
    statusBadge.textContent = text;
    statusBadge.className = `status ${stateClass}`;
}

function appendMessage(sender, text) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', sender);
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.classList.add('bubble');
    bubbleDiv.textContent = text; // Prevents HTML injection
    
    msgDiv.appendChild(bubbleDiv);
    chatContainer.appendChild(msgDiv);
    
    // Auto-scroll to the newest message
    chatContainer.scrollTop = chatContainer.scrollHeight;
}