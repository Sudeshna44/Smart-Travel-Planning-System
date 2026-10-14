
from google import genai
import os
from getpass import getpass

api_key = getpass("Paste your Gemini API key: ")

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents="Reply with only: Gemini API is working"
    )
    print("SUCCESS:", response.text)

except Exception as e:
    print("FAILED:", type(e).__name__)
    print("Error details:", e)
