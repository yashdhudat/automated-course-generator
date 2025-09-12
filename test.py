import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ✅ Use a valid model name from list_models output
model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")

chat = model.start_chat()
response = chat.send_message("Explain AI in 1 line.")
print(response.text)