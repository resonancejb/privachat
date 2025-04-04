# PrivaChat Local Multi-Modal Chat Client (via OpenAI-Compatible API)

## Overview

This is a desktop application built with Python and PyQt6 that allows you to interact with Large Language Models (LLMs) like Google's Gemini series through an OpenAI-compatible API endpoint. It provides a user-friendly interface for text and multi-modal chat (including images, PDFs, and text files) while **keeping your chat history and API key stored securely and privately on your local machine.**

<!-- Optional: Add a screenshot here -->
<!-- ![Screenshot](screenshot.png) -->

## Features

*   **Chat Interface:** Clean and intuitive interface displaying user messages and model responses separately.
*   **API Integration:** Connects to OpenAI-compatible API endpoints (currently configured for Google's Generative Language API).
*   **Streaming Responses:** Model responses are displayed word-by-word as they are generated.
*   **Multi-Modal Input:** Attach Images (`.png`, `.jpg`, etc.), PDFs, and Text Files.
*   **Image Pasting:** Directly paste images from your clipboard.
*   **Private, Local Persistence:**
    *   Your entire chat history (text content and references to non-temporary attached files) is saved **only on your local computer** in an SQLite database (`chats.db`).
    *   No chat data is sent to any external servers, except for the necessary interaction with the specified LLM API during message generation.
    *   Chats persist between application sessions locally.
*   **Chat Management:** Create, switch between, and delete local chat sessions.
*   **Secure, Local API Key Handling:**
    *   Your API key is **never hardcoded** in the source code.
    *   It is stored **only on your local machine** within a `.env` file.
    *   This `.env` file should **never** be shared or committed to version control (like Git).
*   **Code Block Rendering:** Displays code snippets with a "Copy" button.
*   **"Thinking" Indicator:** Shows which model is processing your request.
*   **Dark Theme:** Comfortable dark UI.
*   **Configurable Model:** The LLM model can be changed in `openai_api.py`.

## Privacy and Local Data Handling

This application prioritizes keeping your data private and under your control:

*   **Chat History:** All conversation data, including your messages, the assistant's responses, and the file paths of your non-temporary attachments, are stored **exclusively** within the `chats.db` SQLite file located in the application's directory on your computer. This data **does not leave your machine**, except when being sent to the configured LLM API endpoint during an active request.
*   **API Key:** Your sensitive API key is stored in a `.env` file in the application's root directory. This file is read locally by the application and the key is used directly for API calls. **It is strongly recommended to add `.env` to your `.gitignore` file** to prevent accidental exposure if you use version control.
*   **Temporary Files:** Images pasted from the clipboard are saved as temporary files locally. These temporary files are automatically deleted after the message containing them is sent or when the application is closed.
*   **No External Servers (Beyond LLM API):** The application itself does not communicate with any third-party servers other than the LLM API endpoint you configure (e.g., Google's Generative Language API).

Essentially, your interactions and configuration remain on your own computer, offering a private environment for interacting with the LLM.

## Prerequisites

*   **Python:** Python 3.8 or newer is recommended.
*   **pip:** Python's package installer.
*   **Google API Key:** An API key from Google Cloud enabled for the **Generative Language API**.

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **`.gitignore`:** Crucial for privacy. Ensure your `.gitignore` file prevents committing your API key and potentially your local database. Create or update `.gitignore` with at least:
    ```
    # Local configuration - Contains API Key!
    .env

    # Virtual environment
    venv/

    # Python cache
    __pycache__/
    *.pyc

    # Local database (optional, depends if you want to sync/backup manually)
    # chats.db

    # Temporary/test files (optional)
    *.png
    *.jpg
    ```

## Configuration

1.  **API Key (Stored Locally):**
    *   On first run, you'll be prompted for your **Google API Key**.
    *   This key is saved **only** to the local `.env` file in the project directory. **Do not share this file.**
    *   Update the key later via `File -> Settings`.

2.  **API Endpoint and Model (Advanced):**
    *   Configure the `BASE_URL` and `MODEL_NAME` in `openai_api.py` if needed. Verify against Google's documentation for the OpenAI-compatible endpoint.

## Running the Application

1.  Activate your virtual environment (if used).
2.  Navigate to the project directory.
3.  Run:
    ```bash
    python main.py
    ```

## Usage Guide

1.  **Launch:** Run `python main.py`.
2.  **API Key:** Enter your Google API key (stored locally in `.env`) if prompted.
3.  **Main Window:** Left pane for chat list, right pane for the current chat, attachments, and input.
4.  **Chats:** Use "➕ New Chat" or click a title in the history. All chats are saved locally in `chats.db`.
5.  **Messages:** Type in the input box, press `Enter` (or click "Send"). `Shift+Enter` for new lines.
6.  **Attachments:** Click `+` to select local files or paste images directly. Attachments are processed locally and sent with the prompt to the API. Paths for non-temporary files are stored locally in the database.
7.  **Attachment Preview:** Manage attachments before sending.
8.  **Responses:** See the "`<model_name>` is thinking..." indicator, then watch the response stream in.
9.  **Code Blocks:** Copy code easily from formatted blocks.
10. **Managing Chats:** Right-click a chat in the history to delete it locally.
11. **Settings:** Update your locally stored API key via `File -> Settings`.

## Technology Stack

*   **GUI:** PyQt6
*   **API Client:** OpenAI Python Library
*   **Configuration:** python-dotenv
*   **Database (Local):** SQLite3
*   **Image Handling:** Pillow
*   **PDF Handling:** PyMuPDF
*   **Text Formatting:** Markdown

See `requirements.txt` for specific versions.

## License

Distributed under the MIT License. See `LICENSE` file for more information.