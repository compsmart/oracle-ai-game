import asyncio
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv("key.txt")
GOOGLE_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

async def test_live_api():
    print("Testing Live API connection...")
    
    client = genai.Client(api_key=GOOGLE_API_KEY)
    
    # Use the exact model name from docs
    model = "gemini-2.5-flash-native-audio-preview-09-2025"
    
    # Test 1: Exact format from documentation
    print("\nTest 1: Exact format from docs")
    try:
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": "You are a helpful assistant and answer in a friendly tone.",
        }
        
        async with client.aio.live.connect(model=model, config=config) as session:
            print("✓ Connected successfully!")
            
            # Send simple text input
            await session.send(input="Hello", end_of_turn=True)
            print("✓ Sent message")
            
            response_text = ""
            audio_count = 0
            async for response in session.receive():
                if response.data is not None:
                    audio_count += 1
                    print(f"  Audio chunk {audio_count}: {len(response.data)} bytes")
                    
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.text:
                            response_text += part.text
                
                if response.server_content and response.server_content.turn_complete:
                    break
            
            print(f"✓ Received text response: {response_text}")
            print(f"✓ Received {audio_count} audio chunks")
            
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: With system instruction
    print("\nTest 2: With system instruction")
    try:
        config = {
            "response_modalities": ["TEXT", "AUDIO"],
            "system_instruction": "You are a helpful assistant. Be brief."
        }
        
        async with client.aio.live.connect(model=model, config=config) as session:
            print("✓ Connected with system instruction!")
            
            await session.send(input="What is 2+2?", end_of_turn=True)
            
            response_text = ""
            async for response in session.receive():
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.text:
                            response_text += part.text
                
                if response.server_content and response.server_content.turn_complete:
                    break
            
            print(f"✓ Received response: {response_text}")
            
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        return
    
    # Test 3: With AUDIO response modality
    print("\nTest 3: With AUDIO response modality")
    try:
        config = {
            "response_modalities": ["TEXT", "AUDIO"],
            "system_instruction": "You are a helpful assistant."
        }
        
        async with client.aio.live.connect(model=model, config=config) as session:
            print("✓ Connected with AUDIO modality!")
            
            await session.send(input="Say hello.", end_of_turn=True)
            
            response_text = ""
            audio_received = False
            async for response in session.receive():
                if response.data is not None:
                    audio_received = True
                    print(f"✓ Received audio chunk: {len(response.data)} bytes")
                
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.text:
                            response_text += part.text
                
                if response.server_content and response.server_content.turn_complete:
                    break
            
            print(f"✓ Received text: {response_text}")
            print(f"✓ Audio received: {audio_received}")
            
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
        return
    
    print("\n✓ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_live_api())
