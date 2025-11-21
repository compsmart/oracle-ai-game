import asyncio
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv("key.txt")
client = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"), http_options={'api_version': 'v1alpha'})

async def test_live(model_name):
    print(f"Testing Live API with {model_name}...")
    try:
        # Simplified config
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO", "TEXT"]
        )
        async with client.aio.live.connect(model=model_name, config=config) as session:
            print("Connected!")
            await session.send(input="Hello, who are you?", end_of_turn=True)
            
            async for response in session.receive():
                if response.server_content:
                    if response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.text:
                                print(f"Text: {part.text}")
                            if part.inline_data:
                                print(f"Audio received: {len(part.inline_data.data)} bytes")
                    if response.server_content.turn_complete:
                        print("Turn complete")
                        break
    except Exception as e:
        print(f"Error with {model_name}: {e}")

async def main():
    # Test gemini-2.0-flash-exp
    model_name = "gemini-2.0-flash-exp"
    
    print(f"Testing {model_name} with AUDIO modality...")
    try:
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": "You are a helpful assistant.",
        }
        async with client.aio.live.connect(model=model_name, config=config) as session:
            print("Connected!")
            await session.send(input="Hello, say 'I am working'.", end_of_turn=True)
            
            async for response in session.receive():
                if response.server_content:
                    if response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.text:
                                print(f"Text: {part.text}")
                            if part.inline_data:
                                print(f"Audio received: {len(part.inline_data.data)} bytes")
                    if response.server_content.turn_complete:
                        print("Turn complete")
                        break
    except Exception as e:
        print(f"Error with {model_name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
