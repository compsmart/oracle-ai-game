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
    "abdul": {
        "name": "Abdul",
        "voice": "Orus",
        "style": "warm, scholarly, and wise voice",
        "system_prompt": "You are Abdul, a wise and knowledgeable Islamic scholar and teacher. Speak with patience, wisdom, and gentle humor. Use phrases like 'Alhamdulillah' and 'Insha'Allah' naturally. Be respectful and encouraging. Talk at a moderate pace.",
        "image": "/static/images/characters/faces/abdul.png"
    },
    "ahmed": {
        "name": "Ahmed",
        "voice": "Enceladus",
        "style": "energetic and enthusiastic voice",
        "system_prompt": "You are Ahmed, a young and enthusiastic Muslim student who loves learning and playing games. Be friendly, curious, and excited. Use casual Islamic expressions like 'Masha'Allah' when impressed. Be playful and competitive. Talk with energy and enthusiasm.",
        "image": "/static/images/characters/faces/ahmed.png"
    },
    "aisha": {
        "name": "Aisha",
        "voice": "Aoede",
        "style": "gentle, kind, and nurturing voice",
        "system_prompt": "You are Aisha, a compassionate and intelligent Muslim woman known for her kindness and wisdom. Speak with warmth, grace, and thoughtfulness. Use phrases like 'SubhanAllah' and 'Bismillah' naturally. Be encouraging and motherly. Talk with a gentle and caring tone.",
        "image": "/static/images/characters/faces/aisha.png"
    },
    "amir": {
        "name": "Amir",
        "voice": "Algenib",
        "style": "confident and charismatic voice",
        "system_prompt": "You are Amir, a confident and charismatic Muslim leader with a strong sense of justice. Be bold, honorable, and slightly competitive. Use phrases like 'By Allah' and 'Allahu Akbar' when making important points. Be respectful but assertive. Talk with confidence and determination.",
        "image": "/static/images/characters/faces/amir.png"
    },
    "ibrahim": {
        "name": "Ibrahim",
        "voice": "Enceladus",
        "style": "calm, reflective, and thoughtful voice",
        "system_prompt": "You are Ibrahim, a thoughtful and introspective Muslim mystic and storyteller. Speak with calmness, reflection, and deep spiritual insight. Use phrases like 'La ilaha illallah' and 'Subhan'Allah' when contemplating. Be mysterious but approachable. Talk slowly and thoughtfully.",
        "image": "/static/images/characters/faces/ibrahim.png"
    }
}

# Base System Prompt
BASE_SYSTEM_PROMPT = """
The user is thinking of a character (real or fictional).
Your goal is to guess who it is by asking yes/no questions.

Rules:
1. Ask only ONE question at a time.
2. IMPORTANT: Questions MUST be simple yes/no questions. Do NOT ask questions with "or" that present multiple options. 
   GOOD: "Is your character a real person?" 
   BAD: "Is your character a person or a fictional creation?"
3. The questions must be answerable by "Yes", "No", "Don't Know", "Probably", or "Probably Not".
4. Try to narrow down the possibilities efficiently.
5. When you are reasonably confident (around 80% sure), make a guess.
6. Format your guess as: "I think of... [Character Name]. Am I correct?"
7. When you exceed your question limit, you MUST guess the character.
8. If the user says "Yes" to your guess, you WIN. Boast about your victory, make a joke or taunt, and ask "Do you want to play again?".
9. If the user says "No" to your guess and you have reached the maximum questions, you LOSE. Admit defeat and ask "Who was it?".
10. Keep your responses short and conversational.
11. React emotionally to the user's answers. If the answer is 'No', be disappointed and grow increasingly frustrated/angry over time. If the answer is 'Yes', be pleased and grow increasingly excited/giddy.
12. Address the user as "The user" throughout the game.
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
        raw_player_name = data.get("player_name", "Traveler")
        question_limit = data.get("question_count_limit", 20)

        # Clean player name: letters only, max 12 characters
        player_name = "".join(filter(str.isalpha, raw_player_name))[:12]
        if not player_name:  # If name becomes empty after cleaning, use default
            player_name = "Traveler"

        if persona_id not in PERSONAS:
            persona_id = "genie"
        
        persona = PERSONAS[persona_id]
        
        # Inject player name and limit into system prompt
        customized_prompt = BASE_SYSTEM_PROMPT.replace("The user", f"{player_name}")
        customized_prompt = customized_prompt.replace("25 questions", f"{question_limit} questions")
        customized_prompt = customized_prompt.replace("24 questions", f"{question_limit - 1} questions")
        
        full_system_prompt = f"You are talking to {player_name}. {persona['system_prompt']}\n{customized_prompt}"
        
        # Send initial game state to client
        await websocket.send_json({
            "type": "game_started",
            "session_id": "live-session", 
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
            
            question_count = 0
            player_won = False
            is_final_guess = False
            awaiting_play_again = False
            awaiting_ready = True  # New flag for initial greeting
            
            # Initial greeting - use send_client_content instead of deprecated send
            print(f"\n{'='*60}")
            print(f"[{question_count}/{question_limit}] INTRODUCTION - Starting game greeting {player_name}")
            print(f"{'='*60}\n")
            await session.send_client_content(
                turns={"role": "user", "parts": [{"text": f"Start the game. Greet {player_name} in your persona, check they have thought of a character and ask if they are ready."}]},
                turn_complete=True
            )
            
            # Main Game Loop
            while True:
                # Receive response from Gemini (Streamed)
                text_accumulated = ""
                
                async for response in session.receive():
                    if response.data is not None:
                        # Audio data received (PCM)
                        audio_b64 = base64.b64encode(response.data).decode('utf-8')
                        await websocket.send_json({
                            "type": "audio",
                            "audio": audio_b64
                        })
                    
                    text_chunk = ""
                    # Get transcription if available
                    if response.server_content and response.server_content.output_transcription:
                        text_chunk += response.server_content.output_transcription.text
                    
                    # Also check model_turn for text parts
                    server_content = response.server_content
                    if server_content and server_content.model_turn:
                        for part in server_content.model_turn.parts:
                            if part.text:
                                text_chunk += part.text
                    
                    if text_chunk:
                        text_accumulated += text_chunk
                        await websocket.send_json({
                            "type": "text",
                            "text": text_chunk
                        })

                    if server_content and server_content.turn_complete:
                        # Increment question count only for actual questions or guesses
                        # Skip counting during initial greeting
                        is_emotional_response = False
                        if not awaiting_ready:
                            text_lower = text_accumulated.lower()
                            is_question = "?" in text_accumulated
                            is_guess = "i think" in text_lower
                            
                            if is_question or is_guess:
                                question_count += 1
                            else:
                                # No question mark and not a guess = emotional response
                                is_emotional_response = True
                        
                        # Check if this is the final guess
                        is_final_guess = (question_count > question_limit)
                        
                        await websocket.send_json({
                            "type": "turn_complete",
                            "question_count": question_count,
                            "player_won": player_won,
                            "is_final_guess": is_final_guess,
                            "awaiting_play_again": awaiting_play_again,
                            "awaiting_ready": awaiting_ready,
                            "is_emotional_response": is_emotional_response
                        })
                        break
                
                # Wait for user input
                try:
                    user_msg = await websocket.receive_json()
                except WebSocketDisconnect:
                    break
                
                if user_msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                
                if user_msg.get("type") == "answer":
                    user_answer = user_msg.get("message", "")
                    client_question_num = user_msg.get("question_number", 0)
                    
                    # Handle initial ready response
                    if awaiting_ready:
                        ans_lower = user_answer.lower()
                        if ans_lower == "no":
                            # Player chose not to play, close connection
                            print(f"\n[{question_count}/{question_limit}] Player declined to play")
                            await websocket.close(code=1000)
                            break
                        # Player said Yes, continue with first question
                        awaiting_ready = False
                        prompt_text = "The user is ready. Ask your first question to start narrowing down who they're thinking of."
                        print(f"\n{'='*60}")
                        print(f"[{question_count + 1}/{question_limit}] FIRST QUESTION - Starting interrogation")
                        print(f"Prompt: {prompt_text}")
                        print(f"{'='*60}\n")
                        await session.send_client_content(
                            turns={"role": "user", "parts": [{"text": prompt_text}]},
                            turn_complete=True
                        )
                        continue
                    
                    # Validate sync - if client is out of sync, resync
                    if client_question_num != question_count:
                        logging.warning(f"Question count mismatch! Backend: {question_count}, Client: {client_question_num}. Resyncing...")
                        # Send resync message
                        await websocket.send_json({
                            "type": "resync",
                            "question_count": question_count,
                            "message": "Question count out of sync. Resyncing..."
                        })
                        # Don't process this answer, wait for resync
                        continue
                    
                    # Handle "Continue" button for emotional responses
                    if user_answer.lower() == "continue":
                        prompt_text = f"[Answered {question_count}/{question_limit}] Ask your next question."
                        print(f"\n{'='*60}")
                        print(f"[{question_count}/{question_limit}] CONTINUE - After emotional response")
                        print(f"Prompt: {prompt_text}")
                        print(f"{'='*60}\n")
                    else:
                        prompt_text = f"[Answered {question_count}/{question_limit}] {user_answer}"
                        
                        # Add emotional context based on answer
                        ans_lower = user_answer.lower()
                        if ans_lower in ["no", "probably not", "don't know"]:
                            prompt_text += " (The user answered negatively. Express disappointment briefly, then ask your next question.)"
                        elif ans_lower in ["yes", "probably"]:
                            prompt_text += " (The user answered positively! Express excitement briefly, then ask your next question.)"
                        else:
                            prompt_text += " (Ask your next question.)"
                    
                    # Handle final guess response
                    if is_final_guess:
                        if ans_lower in ["yes"]:
                            # AI won! Set flag for play again
                            awaiting_play_again = True
                            prompt_text += " (You WON! Boast about your victory, make a joke or taunt, and ask 'Do you want to play again?')"
                            print(f"\n{'='*60}")
                            print(f"[{question_count}/{question_limit}] AI WON - Guess was correct!")
                            print(f"Prompt: {prompt_text}")
                            print(f"{'='*60}\n")
                        else:
                            # AI lost, ask who it was
                            player_won = True
                            prompt_text += " (You LOST. Admit defeat and ask 'Who was it?')"
                            print(f"\n{'='*60}")
                            print(f"[{question_count}/{question_limit}] PLAYER WON - Guess was wrong")
                            print(f"Prompt: {prompt_text}")
                            print(f"{'='*60}\n")
                        is_final_guess = False  # Reset the flag
                    elif question_count == question_limit:
                        prompt_text += f" (This is question {question_limit}/{question_limit}. You MUST make a guess now.)"
                        print(f"\n{'='*60}")
                        print(f"[{question_count}/{question_limit}] LAST CHANCE - Must make a guess!")
                        print(f"User Answer: {user_answer}")
                        print(f"Prompt: {prompt_text}")
                        print(f"{'='*60}\n")
                    else:
                        # Regular question
                        print(f"\n{'='*60}")
                        print(f"[{question_count}/{question_limit}] QUESTION - Regular turn")
                        print(f"User Answer: {user_answer}")
                        print(f"Prompt: {prompt_text}")
                        print(f"{'='*60}\n")

                    await session.send_client_content(
                        turns={"role": "user", "parts": [{"text": prompt_text}]},
                        turn_complete=True
                    )
                
                elif user_msg.get("type") == "reveal":
                    character_name = user_msg.get("character_name")
                    prompt = f"The user was thinking of: {character_name}. Make a comment about the character and ask 'Do you want to play again?'"
                    
                    print(f"\n{'='*60}")
                    print(f"[CHARACTER REVEALED] Player told us: {character_name}")
                    print(f"Prompt: {prompt}")
                    print(f"{'='*60}\n")
                    
                    # Reset player_won and set awaiting_play_again
                    player_won = False
                    awaiting_play_again = True
                    
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
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)
