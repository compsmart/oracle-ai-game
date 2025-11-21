let socket = null;
const genieText = document.getElementById('genie-text');
const genieImg = document.getElementById('genie-img');
const controls = document.getElementById('controls');
const inputArea = document.getElementById('input-area');
const revealArea = document.getElementById('reveal-area');
const questionCounter = document.getElementById('question-counter');
const qCountSpan = document.getElementById('q-count');
const characterInput = document.getElementById('character-input');

// Settings Elements
const settingsModal = document.getElementById('settings-modal');
const playerNameInput = document.getElementById('player-name');
const questionLimitInput = document.getElementById('question-limit');

// Load Settings on Start
window.onload = () => {
    const savedName = localStorage.getItem('playerName');
    const savedLimit = localStorage.getItem('questionLimit') || 20;
    
    playerNameInput.value = savedName || "";
    questionLimitInput.value = savedLimit;

    if (!savedName) {
        openSettings();
    }
};

function openSettings() {
    settingsModal.style.display = "block";
}

function closeSettings() {
    settingsModal.style.display = "none";
}

function saveSettings() {
    const name = playerNameInput.value.trim();
    const limit = questionLimitInput.value;
    
    if (name) {
        localStorage.setItem('playerName', name);
    }
    localStorage.setItem('questionLimit', limit);
    closeSettings();
}

// Close modal if clicked outside
window.onclick = function(event) {
    if (event.target == settingsModal) {
        // Only close if name is set
        if (localStorage.getItem('playerName')) {
            closeSettings();
        }
    }
}

let currentText = "";
let textQueue = [];
let isProcessingQueue = false;
let currentPersonaId = null;

function processTextQueue() {
    if (textQueue.length > 0) {
        const char = textQueue.shift();
        const span = document.createElement('span');
        span.textContent = char;
        span.className = 'letter-fade';
        genieText.appendChild(span);
        setTimeout(processTextQueue, 30);
    } else {
        isProcessingQueue = false;
    }
}

// Audio Context for streaming
let audioContext = null;
let nextStartTime = 0;

function initAudio() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    } else if (audioContext.state === 'suspended') {
        audioContext.resume();
    }
}

function playPcmChunk(base64Audio) {
    initAudio();
    const binaryString = atob(base64Audio);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    
    // Convert 16-bit PCM to Float32
    const int16Data = new Int16Array(bytes.buffer);
    const float32Data = new Float32Array(int16Data.length);
    for (let i = 0; i < int16Data.length; i++) {
        float32Data[i] = int16Data[i] / 32768.0;
    }

    const buffer = audioContext.createBuffer(1, float32Data.length, 24000);
    buffer.getChannelData(0).set(float32Data);

    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.destination);

    if (nextStartTime < audioContext.currentTime) {
        nextStartTime = audioContext.currentTime;
    }
    
    source.start(nextStartTime);
    nextStartTime += buffer.duration;
    
    // Visuals
    genieImg.classList.add('speaking');
    // Simple visual sync: stop speaking when the last scheduled chunk finishes
    // This is a bit approximate if chunks come in slowly, but works for continuous streams
    setTimeout(() => {
        if (audioContext.currentTime >= nextStartTime - 0.1) {
             genieImg.classList.remove('speaking');
        }
    }, (nextStartTime - audioContext.currentTime) * 1000);
}

async function selectPersona(personaId, imageUrl) {
    if (imageUrl) {
        genieImg.src = imageUrl;
    }
    startGame(personaId);
}

function startGame(personaId) {
    currentPersonaId = personaId;
    controls.style.display = 'none';
    genieText.innerText = "Consulting the oracle...";
    initAudio(); // Initialize audio context on user interaction
    
    if (socket) {
        socket.close();
    }

    // Determine protocol (ws or wss)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log("Connected to WebSocket");
        const playerName = localStorage.getItem('playerName') || "Traveler";
        const questionLimit = parseInt(localStorage.getItem('questionLimit')) || 20;
        
        // Update UI counter max
        document.getElementById('question-counter').innerHTML = `Question: <span id="q-count">0</span>/${questionLimit}`;

        socket.send(JSON.stringify({
            type: "start_game",
            persona_id: personaId,
            player_name: playerName,
            question_count_limit: questionLimit
        }));
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "game_started") {
            if (data.image) {
                genieImg.src = data.image;
            }
            inputArea.style.display = 'none'; // Wait for first greeting
            questionCounter.style.display = 'block';
            qCountSpan.innerText = data.question_count;
            currentText = ""; // Reset text
            
        } else if (data.type === "audio") {
            playPcmChunk(data.audio);
            
        } else if (data.type === "text") {
            // If this is the start of a new response (and we haven't cleared yet), clear it
            if (currentText === "") {
                genieText.innerHTML = "";
            }
            currentText += data.text;
            
            // Add to queue for smooth typing effect
            for (const char of data.text) {
                textQueue.push(char);
            }
            
            if (!isProcessingQueue) {
                isProcessingQueue = true;
                processTextQueue();
            }
            
        } else if (data.type === "turn_complete") {
            document.querySelector('.genie-avatar').classList.remove('thinking');
            qCountSpan.innerText = data.question_count;
            
            const messageLower = currentText.toLowerCase();

            if (data.player_won) {
                revealArea.style.display = 'block';
                inputArea.style.display = 'none';
            } else if (messageLower.includes("play again")) {
                // Show Play Again buttons
                inputArea.innerHTML = `
                    <button class="btn answer-btn" onclick="startGame(currentPersonaId)">Yes</button>
                    <button class="btn answer-btn" onclick="location.reload()">No</button>
                `;
                inputArea.style.display = 'block';
            } else if (messageLower.includes("who was it") || messageLower.includes("who is it")) {
                // Show Reveal Input
                revealArea.style.display = 'block';
                inputArea.style.display = 'none';
            } else if (currentText.includes("Am I correct?") || currentText.includes("I guess")) {
                 // AI thinks it won, keep buttons for confirmation
                 inputArea.style.display = 'block';
            } else {
                inputArea.style.display = 'block';
            }
        }
    };


    socket.onclose = (event) => {
        console.log("WebSocket closed", event);
        if (event.code !== 1000 && event.code !== 1005) { // Normal closure
             genieText.innerText = "Connection lost. Please refresh.";
             controls.style.display = 'block';
             inputArea.style.display = 'none';
        }
    };

    socket.onerror = (error) => {
        console.error("WebSocket error", error);
        genieText.innerText = "Error connecting to the spirit world.";
    };
}

function sendAnswer(answer) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;

    // Visual feedback
    genieText.innerText = "Thinking...";
    currentText = ""; // Clear previous text
    textQueue = []; // Clear queue
    inputArea.style.display = 'none'; 
    document.querySelector('.genie-avatar').classList.add('thinking');

    // Reset audio context time tracking for new turn
    if (audioContext) {
        nextStartTime = audioContext.currentTime;
    }

    socket.send(JSON.stringify({
        type: "answer",
        message: answer
    }));
}

function submitCharacter() {
    const name = characterInput.value;
    if (!name) return;
    
    if (!socket || socket.readyState !== WebSocket.OPEN) return;

    revealArea.style.display = 'none';
    genieText.innerText = "Reviewing fate...";
    currentText = ""; // Clear previous text
    textQueue = []; // Clear queue
    
    socket.send(JSON.stringify({
        type: "reveal",
        character_name: name
    }));
}
