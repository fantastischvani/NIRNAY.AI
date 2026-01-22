import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.SUPABASE_URL = os.getenv("SUPABASE_URL")
        self.SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        self.PROMPTS_PATH = os.getenv("PROMPTS_PATH")  
        self.PH_API_TOKEN = os.getenv("PH_API_TOKEN")
settings = Settings()