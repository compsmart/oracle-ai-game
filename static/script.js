let socket = null;
const genieText = document.getElementById('genie-text');
const genieImg = document.getElementById('genie-img');
const controls = document.getElementById('controls');
const inputArea = document.getElementById('input-area');
const revealArea = document.getElementById('reveal-area');
const questionCounter = document.getElementById('question-counter');
const qCountSpan = document.getElementById('q-count');
const characterInput = document.getElementById('character-input');

// Audio Playback
function playAudio(base64Audio) {
    if (!base64Audio) return;
    
    const audio = new Audio("data:audio/wav;base64," + base64Audio);
    
    audio.onplay = () => {
        genieImg.classList.add('speaking');
    };
    
    audio.onended = () => {
        genieImg.classList.remove('speaking');
    };
    
    audio.play().catch(e => console.error("Error playing audio:", e));
}

async function selectPersona(personaId, imageUrl) {
    if (imageUrl) {
        genieImg.src = imageUrl;
    }
    startGame(personaId);
}

function startGame(personaId) {
    controls.style.display = 'none';
    genieText.innerText = "Consulting the oracle...";
    
    if (socket) {
        socket.close();
    }

    // Determine protocol (ws or wss)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log("Connected to WebSocket");
        socket.send(JSON.stringify({
            type: "start_game",
            persona_id: personaId
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
        } else if (data.type === "response") {
            document.querySelector('.genie-avatar').classList.remove('thinking');
            
            genieText.innerText = data.message;
            qCountSpan.innerText = data.question_count;
            
            if (data.audio) {
                playAudio(data.audio);
            }

            if (data.player_won) {
                revealArea.style.display = 'block';
                inputArea.style.display = 'none';
            } else if (data.message.toLowerCase().includes("play again")) {
                // Show Play Again buttons
                inputArea.innerHTML = `
                    <button class="btn answer-btn" onclick="location.reload()">Yes</button>
                    <button class="btn answer-btn" onclick="location.href='/'">No</button>
                `;
                inputArea.style.display = 'block';
            } else if (data.message.toLowerCase().includes("who was it") || data.message.toLowerCase().includes("who is it")) {
                // Show Reveal Input
                revealArea.style.display = 'block';
                inputArea.style.display = 'none';
            } else if (data.message.includes("Am I correct?") || data.message.includes("I guess")) {
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
    inputArea.style.display = 'none'; 
    document.querySelector('.genie-avatar').classList.add('thinking');

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
    
    socket.send(JSON.stringify({
        type: "reveal",
        character_name: name
    }));
}
