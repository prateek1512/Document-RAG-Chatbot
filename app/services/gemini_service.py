# app/services/gemini_service.py
# Shared Gemini client initialisation.

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Read the API key from the .env file and create a client once.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
