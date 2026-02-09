import os
from dotenv import load_dotenv
import pandas as pd
load_dotenv()
def ask_ai(user_input):
    database_url = os.getenv("API_KEY")
    # secret_key = os.getenv("SECRET_KEY")
    print(f"Using database: {database_url}")
    return f"Echo: {user_input}"