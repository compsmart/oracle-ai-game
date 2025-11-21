let socket = null;
const genieText = document.getElementById('genie-text');
const genieImg = document.getElementById('genie-img');
const controls = document.getElementById('controls');
const inputArea = document.getElementById('input-area');
const revealArea = document.getElementById('reveal-area');
const questionCounter = document.getElementById('question-counter');
let qCountSpan = document.getElementById('q-count'); // Use 'let' so it can be reassigned
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
    
    // Start rotating loading phrases
    startLoadingPhraseRotation();
};

// Loading phrase rotation
const loadingPhrases = [
    "Summoning the spirits...",
    "Gazing into the void...",
    "Reading the cosmic energies...",
    "Consulting the ancient ones...",
    "Peering beyond the veil...",
    "Channeling mystic forces...",
    "Awakening the oracle..."
];
let currentPhraseIndex = 0;
let phraseRotationInterval = null;

function startLoadingPhraseRotation() {
    // Only rotate if we're on the initial loading screen
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        currentPhraseIndex = 0;
        updateLoadingPhrase();
        
        phraseRotationInterval = setInterval(() => {
            if (!socket || socket.readyState !== WebSocket.OPEN) {
                updateLoadingPhrase();
            } else {
                stopLoadingPhraseRotation();
            }
        }, 10000); // Change phrase every 10 seconds
    }
}

function updateLoadingPhrase() {
    const phrase = loadingPhrases[currentPhraseIndex];
    genieText.style.opacity = '0';
    
    setTimeout(() => {
        genieText.innerText = phrase;
        genieText.style.opacity = '1';
        currentPhraseIndex = (currentPhraseIndex + 1) % loadingPhrases.length;
    }, 300); // Wait for fade out
}

function stopLoadingPhraseRotation() {
    if (phraseRotationInterval) {
        clearInterval(phraseRotationInterval);
        phraseRotationInterval = null;
    }
}

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

function quitGame() {
    // Close websocket if active
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
    }
    
    // Reset the game state
    closeSettings();
    location.reload();
}

function quitToHome() {
    // Close websocket if active
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
    }
    
    // Go back to home screen
    location.reload();
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
    stopLoadingPhraseRotation(); // Stop rotation when persona is selected
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
        
        // Update UI counter max - start at 0, will update when game starts
        document.getElementById('question-counter').innerHTML = `Question: <span id="q-count">0</span>/${questionLimit}`;
        
        // Re-get the reference to q-count span since innerHTML replaced it
        qCountSpan = document.getElementById('q-count');

        socket.send(JSON.stringify({
            type: "start_game",
            persona_id: personaId,
            player_name: playerName,
            question_count_limit: questionLimit
        }));
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if(data.type!=='audio') {
            console.log("Received:", data);
        }
        
        if (data.type === "game_started") {
            if (data.image) {
                genieImg.src = data.image;
            }
            inputArea.style.display = 'none'; // Wait for first greeting
            revealArea.style.display = 'none'; // Hide reveal area on restart
            questionCounter.style.display = data.question_count > 0 ? 'block' : 'none'; // Show counter only if count > 0
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
            
            // Get the question limit
            const questionLimit = parseInt(localStorage.getItem('questionLimit')) || 20;
            
            // Hide question counter if question_count is 0 or exceeds max questions
            if (data.question_count === 0 || data.question_count > questionLimit) {
                console.log("Hiding question counter", data.question_count);
                questionCounter.style.display = 'none';
            } else {
                console.log("Showing question counter");
                questionCounter.style.display = 'block';
            }

            // Determine which buttons to show based on game state
            if (data.awaiting_ready) {
                // Initial greeting - show Continue button to start game
                inputArea.innerHTML = `
                    <button class="btn answer-btn" style="width: 200px; margin: 0 auto;" onclick="sendAnswer('Continue')">Continue</button>
                `;
                inputArea.style.display = 'block';
            } else if (data.is_emotional_response) {
                // AI gave an emotional response without a question - show Continue button
                inputArea.innerHTML = `
                    <button class="btn answer-btn" style="width: 200px; margin: 0 auto;" onclick="sendAnswer('Continue')">Continue</button>
                `;
                inputArea.style.display = 'block';
            } else if (data.player_won) {
                // Player won (AI couldn't guess) - show reveal input
                revealArea.style.display = 'block';
                inputArea.style.display = 'none';
            } else if (data.awaiting_play_again) {
                // AI is asking if they want to play again - show Yes/No
                inputArea.innerHTML = `
                    <button class="btn answer-btn" style="width: 45%;" onclick="startGame('${currentPersonaId}')">Yes</button>
                    <button class="btn answer-btn" style="width: 45%;" onclick="quitToHome()">No</button>
                `;
                inputArea.style.display = 'block';
            } else if (data.is_final_guess) {
                // AI made the final guess - show Yes/No only
                inputArea.innerHTML = `
                    <button class="btn answer-btn" style="width: 45%;" onclick="sendAnswer('Yes')">Yes</button>
                    <button class="btn answer-btn" style="width: 45%;" onclick="sendAnswer('No')">No</button>
                `;
                inputArea.style.display = 'block';
            } else {
                // Regular question - show all 5 options
                inputArea.innerHTML = `
                    <button class="btn answer-btn" onclick="sendAnswer('Yes')">Yes</button>
                    <button class="btn answer-btn" onclick="sendAnswer('No')">No</button>
                    <button class="btn answer-btn" onclick="sendAnswer('Don\\'t Know')">Don't Know</button>
                    <button class="btn answer-btn" onclick="sendAnswer('Probably')">Probably</button>
                    <button class="btn answer-btn" onclick="sendAnswer('Probably Not')">Probably Not</button>
                `;
                inputArea.style.display = 'block';
            }
        } else if (data.type === "resync") {
            // Backend detected out of sync, update UI
            console.warn(data.message);
            qCountSpan.innerText = data.question_count;
            genieText.innerText = "Synchronizing...";
            inputArea.style.display = 'block';
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

    // Get current question count from UI
    const currentQuestionCount = parseInt(qCountSpan.innerText) || 0;

    socket.send(JSON.stringify({
        type: "answer",
        message: answer,
        question_number: currentQuestionCount
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
    
    // Clear the input field after submission
    characterInput.value = "";
}
