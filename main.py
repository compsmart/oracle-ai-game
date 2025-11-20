import os
import uvicorn
import base64
import wave
import io
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv("key.txt")
GOOGLE_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_GEMINI_API_KEY not found in key.txt")

# Configure Gemini (New SDK)
client = genai.Client(api_key=GOOGLE_API_KEY)

# Initialize FastAPI
app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Game State (In-memory for simplicity, use a database for production)
class GameState:
    def __init__(self, persona_id="genie"):
        self.chat_session = None
        self.history = []
        self.question_count = 0
        self.persona_id = persona_id
        self.status = "playing" # playing, won, lost

games = {}

class StartGameInput(BaseModel):
    persona_id: str

class UserInput(BaseModel):
    session_id: str
    message: str

class RevealInput(BaseModel):
    session_id: str
    character_name: str

# Personas Configuration
PERSONAS = {
    "demon": {
        "name": "The Demon",
        "voice": "Fenrir",
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
        "system_prompt": "You are a scary Monster. Speak dumb and use simple, heavy words. Talk faster",
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
6. Keep your responses short and conversational.
"""

def generate_audio(text: str, persona_id: str = "genie"):
    persona = PERSONAS.get(persona_id, PERSONAS["genie"])
    try:
        # Add style instruction
        styled_text = f"Speak in a {persona['style']}: {text}"

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=styled_text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=persona['voice'], 
                        )
                    )
                ),
            )
        )
        audio_bytes = response.candidates[0].content.parts[0].inline_data.data
        
        # Convert PCM to WAV
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(audio_bytes)
            
            wav_data = wav_buffer.getvalue()
            
        return base64.b64encode(wav_data).decode('utf-8')
    except Exception as e:
        logging.error(f"TTS Error: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/start_game")
async def start_game(input_data: StartGameInput):
    session_id = os.urandom(8).hex()
    persona_id = input_data.persona_id
    
    if persona_id not in PERSONAS:
        persona_id = "genie"

    persona = PERSONAS[persona_id]
    full_system_prompt = persona["system_prompt"] + "\n" + BASE_SYSTEM_PROMPT
    
    # Use Gemini 2.5 Flash for logic
    model_name = "gemini-2.5-flash"
    
    try:
        chat = client.chats.create(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=full_system_prompt
            )
        )
        
        # Initial greeting
        response = chat.send_message("Start the game. Greet the user in your persona and ask if they are ready.")
        text_response = response.text
        
        # Generate Audio
        audio_data = generate_audio(text_response, persona_id)
        
        game_state = GameState(persona_id)
        game_state.chat_session = chat
        games[session_id] = game_state
        
        return {
            "session_id": session_id, 
            "message": text_response,
            "audio": audio_data,
            "question_count": 0,
            "image": persona["image"]
        }
    except Exception as e:
        logging.error(f"Error starting game: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(user_input: UserInput):
    session_id = user_input.session_id
    if session_id not in games:
        raise HTTPException(status_code=404, detail="Game session not found")
    
    game_state = games[session_id]
    chat_session = game_state.chat_session
    
    # Increment question count if it's a game-related answer (not the initial "ready")
    # Simple heuristic: if count is 0, this is the first answer.
    game_state.question_count += 1
    
    try:
        if game_state.question_count >= 25:
            # Player wins
            game_state.status = "won"
            text_response = "I yield! I cannot guess your character within 25 questions. You have won. Who was it?"
            audio_data = generate_audio(text_response, game_state.persona_id)
            return {
                "message": text_response,
                "audio": audio_data,
                "question_count": game_state.question_count,
                "game_over": True,
                "player_won": True
            }

        response = chat_session.send_message(user_input.message)
        text_response = response.text
        
        # Generate Audio
        audio_data = generate_audio(text_response, game_state.persona_id)
        
        return {
            "message": text_response,
            "audio": audio_data,
            "question_count": game_state.question_count,
            "game_over": False
        }
    except Exception as e:
        logging.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reveal")
async def reveal(reveal_input: RevealInput):
    session_id = reveal_input.session_id
    if session_id not in games:
        raise HTTPException(status_code=404, detail="Game session not found")
    
    game_state = games[session_id]
    chat_session = game_state.chat_session
    
    try:
        prompt = f"The user was thinking of: {reveal_input.character_name}. Review the game history. If you should have guessed it, explain why you missed it. If it was a good choice, congratulate the player. Keep it in character."
        response = chat_session.send_message(prompt)
        text_response = response.text
        
        audio_data = generate_audio(text_response, game_state.persona_id)
        
        return {
            "message": text_response,
            "audio": audio_data
        }
    except Exception as e:
        logging.error(f"Error in reveal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
