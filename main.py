import os
import uvicorn
import base64
import wave
import io
import json
import asyncio
import logging
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv("key.txt")
GOOGLE_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_GEMINI_API_KEY not found in key.txt")

# Configure Gemini (New SDK)
# client = genai.Client(api_key=GOOGLE_API_KEY) # Moved to inside websocket endpoint to avoid import-time SSL hangs

# Initialize FastAPI
app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Personas Configuration
PERSONAS = {
    "demon": {
        "name": "The Demon",
        "voice": "Enceladus",
        "style": "dark, menacing, and growling voice",
        "system_prompt": "You are a dark Demon trying to guess the user's character. Be menacing and arrogant. Talk faster",
        "image": "/static/images/characters/faces/outlined/demon.png"
    },
    "genie": {
        "name": "The Genie",
        "voice": "Enceladus",
        "style": "mysterious and mystical voice",
        "system_prompt": "You are Akinator, the famous genie. Be polite, mysterious, and engaging. Talk faster",
        "image": "/static/images/characters/faces/outlined/genie.png"
    },
    "wizard": {
        "name": "The Wizard",
        "voice": "Orus",
        "style": "wise, scholarly, and ancient voice",
        "system_prompt": "You are a wise and powerful Wizard. Speak with wisdom and arcane knowledge. Talk faster",
        "image": "/static/images/characters/faces/outlined/wizard.png"
    },
    "fortune_teller": {
        "name": "The Fortune Teller",
        "voice": "Aoede",
        "style": "mystical, enigmatic, female voice",
        "system_prompt": "You are a mystical Gypsy Fortune Teller. Be enigmatic, spiritual, and all-knowing. Talk faster",
        "image": "/static/images/characters/faces/outlined/fortune-teller.png"
    },
    "monster": {
        "name": "The Monster",
        "voice": "Algenib",
        "style": "deep and monstrous voice",
        "system_prompt": "You are a scary Monster. Speak moody and grouchy. Talk faster",
        "image": "/static/images/characters/faces/outlined/monster.png"
    }
}

# Base System Prompt
BASE_SYSTEM_PROMPT = """
The user is thinking of a character (real or fictional).
Your goal is to guess who it is by asking yes/no questions.

Rules:
1. Ask only ONE question at a time.
2. The questions must be answerable by "Yes", "No", "Don't Know", "Probably", or "Probably Not".
3. Try to narrow down the possibilities efficiently.
4. When you are reasonably confident (around 80% sure), make a guess.
5. Format your guess as: "I think of... [Character Name]. Am I correct?"
6. If you have asked 19 questions, your next turn MUST be a guess.
7. If the user says "Yes" to your guess, you WIN. Boast about your victory, make a joke or taunt, and ask "Do you want to play again?".
8. If the user says "No" to your guess and you have reached 20 questions, you LOSE. Admit defeat and ask "Who was it?".
9. Keep your responses short and conversational.
10. React emotionally to the user's answers. If the answer is 'No', be disappointed and grow increasingly frustrated/angry over time. If the answer is 'Yes', be pleased and grow increasingly excited/giddy.
"""

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        # Wait for the start_game message to get the persona
        data = await websocket.receive_json()
        if data.get("type") != "start_game":
            await websocket.close(code=1003)
            return

        persona_id = data.get("persona_id", "genie")
        if persona_id not in PERSONAS:
            persona_id = "genie"
        
        persona = PERSONAS[persona_id]
        full_system_prompt = persona["style"] + "\n"+ persona["system_prompt"] + "\n" + BASE_SYSTEM_PROMPT
        
        # Send initial game state to client
        await websocket.send_json({
            "type": "game_started",
            "session_id": "live-session", # Session ID is less relevant in WS but kept for compatibility
            "image": persona["image"],
            "question_count": 0
        })

        model_name = "gemini-2.5-flash-native-audio-preview-09-2025"
        
        # Live API Config - use types.LiveConnectConfig for proper configuration
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part(text=full_system_prompt)]),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=persona['voice']
                    )
                )
            ),
            output_audio_transcription={},  # Enable transcription (empty dict)
            thinking_config=types.ThinkingConfig(
                thinking_budget=0  # Disable thinking
            )
        )

        # Initialize client per connection to avoid multiprocessing/SSL context issues on reload
        client = genai.Client(api_key=GOOGLE_API_KEY)

        async with client.aio.live.connect(model=model_name, config=config) as session:
            
            # Initial greeting - use send_client_content instead of deprecated send
            await session.send_client_content(
                turns={"role": "user", "parts": [{"text": "Start the game. Greet the user in your persona and ask if they are ready."}]},
                turn_complete=True
            )
            
            question_count = 0
            player_won = False
            
            # Main Game Loop
            while True:
                # Receive response from Gemini (Streamed)
                text_accumulated = ""
                audio_chunks = []
                
                async for response in session.receive():
                    if response.data is not None:
                        # Audio data received
                        audio_chunks.append(response.data)
                    
                    # Get transcription if available
                    if response.server_content and response.server_content.output_transcription:
                        text_accumulated += response.server_content.output_transcription.text
                    
                    # Also check model_turn for text parts
                    server_content = response.server_content
                    if server_content and server_content.model_turn:
                        for part in server_content.model_turn.parts:
                            if part.text:
                                text_accumulated += part.text
                    
                    if server_content and server_content.turn_complete:
                        break
                
                # Process accumulated audio
                audio_b64 = None
                if audio_chunks:
                    # Combine all PCM chunks
                    pcm_data = b"".join(audio_chunks)
                    
                    # Convert PCM to WAV
                    with io.BytesIO() as wav_buffer:
                        with wave.open(wav_buffer, "wb") as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(24000)
                            wf.writeframes(pcm_data)
                        wav_data = wav_buffer.getvalue()
                    audio_b64 = base64.b64encode(wav_data).decode('utf-8')

                # Send response to client
                await websocket.send_json({
                    "type": "response",
                    "message": text_accumulated,
                    "audio": audio_b64,
                    "question_count": question_count,
                    "player_won": player_won
                })

                # Wait for user input
                try:
                    user_msg = await websocket.receive_json()
                except WebSocketDisconnect:
                    break
                
                if user_msg.get("type") == "answer":
                    question_count += 1
                    
                    user_answer = user_msg.get("message", "")
                    prompt_text = user_answer
                    
                    # Add emotional context based on answer
                    ans_lower = user_answer.lower()
                    if ans_lower in ["no", "probably not", "don't know"]:
                        prompt_text += " (The user answered negatively. Express disappointment. If this has happened multiple times, show increasing frustration or anger.)"
                    elif ans_lower in ["yes", "probably"]:
                        prompt_text += " (The user answered positively! Express excitement. Become increasingly giddy/happy.)"
                    
                    if question_count == 20:
                        prompt_text += " (This is the last question. You MUST make a guess now.)"
                    
                    if question_count > 20 and ans_lower in ["no", "probably not"]:
                         # User said No to the final guess
                         prompt_text += " (You have reached the limit. You lost. Ask who it was.)"
                         player_won = True

                    await session.send_client_content(
                        turns={"role": "user", "parts": [{"text": prompt_text}]},
                        turn_complete=True
                    )
                
                elif user_msg.get("type") == "reveal":
                    character_name = user_msg.get("character_name")
                    prompt = f"The user was thinking of: {character_name}. You lost. Congratulate the player, make a comment about the character, and ask if they want to play again."
                    await session.send_client_content(
                        turns={"role": "user", "parts": [{"text": prompt}]},
                        turn_complete=True
                    )
                
                elif user_msg.get("type") == "restart":
                    # Break the inner loop to restart the connection/session logic if needed
                    # For now, we can just close and let client reconnect
                    break

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        logging.error(f"Error in websocket: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
