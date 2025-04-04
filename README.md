[...]

## Configuration

1.  **API Key Setup (Using `.env` file):**
    *   **Create the File:** In the main project directory (the same place `main.py` is located), create a file named exactly `.env`.
    *   **Add the Key:** Open the `.env` file with a text editor and add the following line, replacing `your_actual_google_api_key_here` with your real key:
        ```dotenv
        GOOGLE_API_KEY=your_actual_google_api_key_here
        ```
    *   **Save the File.**
    *   **Security:** **Crucially, DO NOT commit this `.env` file to Git or share it.** Make sure `.env` is listed in your `.gitignore` file (as mentioned in the Installation section).
    *   **How the App Uses It:** The application uses the `python-dotenv` library to automatically load this key when it starts. If the `.env` file or the `GOOGLE_API_KEY` variable is missing, the application will fall back to prompting you for the key via the GUI (File -> Settings), and it will attempt to save it to the `.env` file for future use. You can always update the key directly in the `.env` file or via the Settings menu.

2.  **API Endpoint and Model (Advanced):**
    *   The `BASE_URL` for the OpenAI-compatible endpoint and the specific `MODEL_NAME` (like `gemini-1.5-flash-latest` or `gemini-1.5-pro-latest`) can be configured directly within the `openai_api.py` file if you need to change them from the defaults. Always consult the API provider's documentation (e.g., Google AI for Developers) for the correct values.

## Understanding `.env` and API Key Security

Using a `.env` file is a standard practice for managing sensitive information like API keys securely and separately from your source code. Here's why and how it works in PrivaChat:

*   **What is `.env`?** It's a simple text file in the project's root directory containing key-value pairs (like `KEY=VALUE`).
*   **What is `python-dotenv`?** It's a Python library (listed in `requirements.txt`) that reads the `.env` file and loads the variables defined inside it into the application's environment variables when the program starts.
*   **How PrivaChat uses it:**
    1.  When you run `python main.py`, near the beginning of the script, the `load_dotenv()` function from `python-dotenv` is called.
    2.  This function looks for a `.env` file in the current directory.
    3.  If found, it reads lines like `GOOGLE_API_KEY=your_key` and makes `your_key` available to the Python script via `os.getenv('GOOGLE_API_KEY')`.
    4.  The rest of the application code can then securely access the API key using `os.getenv('GOOGLE_API_KEY')` without the key ever being written directly into the `.py` files.
*   **Why is this Secure?**
    *   **No Hardcoding:** Your secret key isn't embedded within the code that might be shared or publicly visible (like on GitHub).
    *   **Exclusion from Version Control:** By adding `.env` to your `.gitignore` file, you prevent accidentally uploading your secret key to platforms like GitHub. Each user running the code locally maintains their own private `.env` file.

This approach ensures your API key remains confidential on your local machine while allowing the application to function correctly.

[...]
