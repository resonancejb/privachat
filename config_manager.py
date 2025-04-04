# config_manager.py
import os
from dotenv import load_dotenv, set_key, find_dotenv
from pathlib import Path

# Define the environment variable name
API_KEY_VAR = "GOOGLE_API_KEY"
# Specify the .env file path (could be in the project root or elsewhere)
# find_dotenv() will search parent directories if not found in the current one.
DOTENV_PATH = find_dotenv()
if not DOTENV_PATH:
    # If .env doesn't exist anywhere, create it in the current directory
    DOTENV_PATH = Path(".env").resolve()
    DOTENV_PATH.touch() # Create the file if it doesn't exist
    print(f"Created .env file at: {DOTENV_PATH}")
else:
    print(f"Using .env file at: {DOTENV_PATH}")


def load_api_key() -> str | None:
    """Loads the API key from the .env file."""
    load_dotenv(dotenv_path=DOTENV_PATH, override=True) # Load/reload variables
    api_key = os.getenv(API_KEY_VAR)
    return api_key if api_key else None

def save_api_key(api_key: str):
    """Saves or updates the API key in the .env file."""
    try:
        set_key(dotenv_path=DOTENV_PATH, key_to_set=API_KEY_VAR, value_to_set=api_key)
        print(f"{API_KEY_VAR} saved to {DOTENV_PATH}")
        load_dotenv(dotenv_path=DOTENV_PATH, override=True)
    except IOError as e:
        print(f"Error saving API key to .env file: {e}")
