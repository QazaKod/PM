import asyncio
from app import chatbot
from app.database import load_programs, load_faq
import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
print("Key exists:", bool(GEMINI_API_KEY))

programs = chatbot.get_scored_programs("Are scholarships available?")
faqs = chatbot.get_scored_faqs("Are scholarships available?")

top_p = [p[0] for p in programs[:3]]
top_f = [f[0] for f in faqs[:3]]

print(f"Top FAQS passed to Gemini: {[f['id'] for f in top_f]}")

res = chatbot.get_ai_fallback_response("Are scholarships available?", top_p, top_f)
print("Result:", res)
