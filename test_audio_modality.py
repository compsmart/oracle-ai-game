from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv("key.txt")
client = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

models_to_test = [
    "gemini-2.0-flash-exp",
]

for model_name in models_to_test:
    print(f"Testing {model_name}...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents="Hello, say something.",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Puck", 
                        )
                    )
                ),
            )
        )
        print(f"Success with {model_name}")
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.text:
                    print(f"Text: {part.text}")
                if part.inline_data:
                    print(f"Audio: {len(part.inline_data.data)} bytes")
    except Exception as e:
        print(f"Failed with {model_name}: {e}")

for model_name in models_to_test:
    print(f"Testing {model_name}...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents="Hello, say something.",
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Puck", 
                        )
                    )
                ),
            )
        )
        print(f"Success with {model_name}")
    except Exception as e:
        print(f"Failed with {model_name}: {e}")
