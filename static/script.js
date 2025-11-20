let sessionId = null;
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

async function startGame(personaId) {
    controls.style.display = 'none';
    genieText.innerText = "Consulting the oracle...";
    
    try {
        const response = await fetch('/start_game', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ persona_id: personaId })
        });
        const data = await response.json();
        
        if (response.ok) {
            sessionId = data.session_id;
            genieText.innerText = data.message;
            
            // Update Avatar (redundant if selectPersona handled it, but good for safety)
            if (data.image) {
                genieImg.src = data.image;
            }

            if (data.audio) {
                playAudio(data.audio);
            }
            inputArea.style.display = 'block';
            questionCounter.style.display = 'block';
            qCountSpan.innerText = data.question_count;
        } else {
            genieText.innerText = "Error: " + data.detail;
            controls.style.display = 'block';
        }
    } catch (error) {
        console.error('Error:', error);
        genieText.innerText = "Failed to connect to the spirit world.";
        controls.style.display = 'block';
    }
}

async function sendAnswer(answer) {
    if (!sessionId) return;

    // Visual feedback
    genieText.innerText = "Thinking...";
    inputArea.style.display = 'none'; // Hide buttons while thinking
    document.querySelector('.genie-avatar').classList.add('thinking');

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                message: answer
            }),
        });
        
        const data = await response.json();
        
        document.querySelector('.genie-avatar').classList.remove('thinking');

        if (response.ok) {
            genieText.innerText = data.message;
            qCountSpan.innerText = data.question_count;

            if (data.audio) {
                playAudio(data.audio);
            }
            
            if (data.player_won) {
                // Player won, show reveal input
                revealArea.style.display = 'block';
            } else if (data.message.includes("Am I correct?") || data.message.includes("I guess")) {
                // AI thinks it won, keep buttons for confirmation
                inputArea.style.display = 'block';
            } else {
                // Continue game
                inputArea.style.display = 'block';
            }
            
        } else {
            genieText.innerText = "Error: " + data.detail;
        }
    } catch (error) {
        console.error('Error:', error);
        genieText.innerText = "Connection lost.";
        document.querySelector('.genie-avatar').classList.remove('thinking');
    }
}

async function submitCharacter() {
    const name = characterInput.value;
    if (!name) return;
    
    revealArea.style.display = 'none';
    genieText.innerText = "Reviewing fate...";
    
    try {
        const response = await fetch('/reveal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                character_name: name
            }),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            genieText.innerText = data.message;
            if (data.audio) {
                playAudio(data.audio);
            }
            // Show restart button? For now, user can refresh.
            setTimeout(() => {
                // Maybe show a "Play Again" button here in future
            }, 5000);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}
