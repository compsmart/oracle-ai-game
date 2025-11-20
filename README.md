# AI Mind Reader (Akinator Clone)

A mystical, AI-powered guessing game that attempts to read your mind! Inspired by Akinator, this application uses Google's Gemini AI to ask questions and guess the character you are thinking of. It features an engaging UI and high-quality Text-to-Speech (TTS) to bring the Genie to life.

## Features

*   **AI-Powered Logic**: Uses `gemini-2.5-flash` to generate intelligent questions and narrow down possibilities.
*   **Voice Interaction**: The Genie speaks to you using `gemini-2.5-flash-preview-tts` with a custom voice ("Puck").
*   **Immersive UI**: Dark, mystical theme with floating animations, glowing effects, and a crystal ball.
*   **Real-time Interaction**: Fast responses and seamless game flow.

## Prerequisites

*   Python 3.9 or higher
*   A Google Gemini API Key

## Installation

1.  **Clone the repository** (or navigate to the project folder):
    ```bash
    cd c:\projects\games\akinator
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  Create a file named `key.txt` in the root directory.
2.  Add your Google Gemini API key to the file in the following format:
    ```env
    GOOGLE_GEMINI_API_KEY=your_api_key_here
    ```

## Running the Game

1.  **Start the server**:
    ```bash
    python main.py
    ```

2.  **Open the game**:
    Open your web browser and navigate to:
    [http://127.0.0.1:8000](http://127.0.0.1:8000)

## How to Play

1.  Click **"Start Game"** to summon the Genie.
2.  Think of a character (real or fictional).
3.  The Genie will ask you a series of Yes/No questions.
4.  Answer truthfully using the buttons provided.
5.  Watch (and listen) as the Genie attempts to guess your character!

## Project Structure

*   `main.py`: FastAPI backend server handling game logic and API calls.
*   `templates/index.html`: The main game interface.
*   `static/style.css`: Custom styling and animations.
*   `static/script.js`: Frontend logic and audio playback handling.
*   `requirements.txt`: List of Python dependencies.
*   `key.txt`: Configuration file for API keys (not included in version control).

## Technologies Used

*   **Backend**: Python, FastAPI, Uvicorn
*   **AI**: Google Gemini API (Generative AI & TTS)
*   **Frontend**: HTML5, CSS3, JavaScript
