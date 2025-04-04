# openai_api.py
import os
import base64
import io
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, BadRequestError
from typing import List, Dict, Optional, Iterator, Union, Any
from PIL import Image # Needed for image processing

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/" # Adjusted based on common 
MODEL_NAME = 'gemini-2.5-pro-exp-03-25'

# --- Helper Functions ---

def _prepare_openai_client(api_key: str) -> OpenAI:
    """Configures and returns the OpenAI client instance pointed at Google's endpoint."""
    if not api_key:
        raise ValueError("API Key is missing. Please provide it.")
    try:
        effective_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/" # From user prompt
        print(f"Using OpenAI client with base_url: {effective_base_url}")

        client = OpenAI(
            api_key=api_key,
            base_url=effective_base_url
        )
        return client
    except Exception as e:
        # Catch potential configuration errors early
        if "api_key" in str(e).lower():
             raise ValueError(f"Invalid API Key provided or configuration error. Details: {e}")
        raise RuntimeError(f"Failed to configure OpenAI client. Details: {e}")

def _pil_image_to_base64_data_url(image: Image.Image, format="JPEG") -> str:
    """Converts a PIL Image object to a base64 data URL."""
    buffered = io.BytesIO()
    # Handle transparency for PNG, otherwise save as JPEG
    if format.upper() == "PNG" and image.mode in ("RGBA", "LA"):
        image.save(buffered, format="PNG")
        mime_type = "image/png"
    else:
        # Convert to RGB if it has alpha channel for JPEG saving
        if image.mode in ("RGBA", "LA"):
            image = image.convert("RGB")
        image.save(buffered, format="JPEG")
        mime_type = "image/jpeg"

    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:{mime_type};base64,{img_str}"

def _format_openai_messages(history: List[Dict[str, Any]], prompt_data: Union[str, List[Any]]) -> List[Dict[str, Any]]:
    """Formats the history and current prompt into the OpenAI messages structure."""
    messages = []

    # Add history, mapping roles
    for msg in history:
        role = msg.get("role")
        parts = msg.get("parts") # Expecting parts to be a list containing a single text string from previous turns
        content = parts[0] if parts and isinstance(parts[0], str) else ""

        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role == "model":
            messages.append({"role": "assistant", "content": content})
        # Ignore 'system' or 'error' roles from internal history for the API call

    # --- Construct the current user message ---
    current_message_content = []
    if isinstance(prompt_data, str):
        # Text-only input
        current_message_content.append({"type": "text", "text": prompt_data})
    elif isinstance(prompt_data, list):
        # Multimodal input (list of strings and PIL Images)
        text_parts = []
        for part in prompt_data:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, Image.Image):
                try:
                    # Add accumulated text first if any
                    if text_parts:
                        current_message_content.append({"type": "text", "text": "\n".join(text_parts)})
                        text_parts = []
                    # Convert image to base64 data URL
                    data_url = _pil_image_to_base64_data_url(part)
                    current_message_content.append({
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    })
                    print(f"  Formatted image part for OpenAI API (MIME type inferred).")
                except Exception as e:
                    print(f"Error processing image for OpenAI API: {e}")
                    # Optionally add an error message or skip
                    current_message_content.append({"type": "text", "text": f"[Error processing image: {e}]"})

            else:
                print(f"Warning: Unsupported part type in prompt_data: {type(part)}")

        # Add any remaining text parts
        if text_parts:
            current_message_content.append({"type": "text", "text": "\n".join(text_parts)})

    else:
        raise TypeError("prompt_data must be a string or a list of parts (str/PIL.Image).")

    if not current_message_content:
        raise ValueError("Cannot send empty message content.")

    # Add the fully constructed user message
    messages.append({"role": "user", "content": current_message_content})

    # Add a system prompt if desired (optional)
    # messages.insert(0, {"role": "system", "content": "You are a helpful assistant."})

    print(f"Formatted messages for OpenAI API. Total messages: {len(messages)}")
    # print(f"Last message content structure: {messages[-1]['content']}") # Debugging complex content
    return messages


# --- API Functions ---

def get_openai_response(
    api_key: str,
    history: List[Dict[str, Any]],
    prompt_data: Union[str, List[Any]],
    # generation_config is less directly applicable, use standard params
) -> str:

    client = _prepare_openai_client(api_key)
    messages = _format_openai_messages(history, prompt_data)

    print(f"Sending request to OpenAI endpoint ({MODEL_NAME}) with {len(messages)} messages...")

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1, # As requested
            top_p=1.0,       # As requested
            n=1,
            stream=False
        )

        # Basic check for response structure
        if not response.choices:
            raise APIError("API returned no choices.", response=None, body=None) # Simulate APIError structure if possible

        # Check finish reason if needed (e.g., 'stop', 'length', 'content_filter')
        finish_reason = response.choices[0].finish_reason
        print(f"OpenAI API Finish Reason: {finish_reason}")
        if finish_reason == 'content_filter':
             raise Exception("Content generation stopped due to OpenAI content filter.")
        elif finish_reason == 'length':
             print("Warning: Response may be truncated due to length limits.")

        response_content = response.choices[0].message.content
        if response_content is None:
             print("Warning: API returned null content.")
             return "" # Return empty string for null content

        return response_content.strip()

    except AuthenticationError as e:
        print(f"OpenAI Authentication Error: {e}")
        raise RuntimeError(f"Invalid API Key or Authentication Failed. Check settings. Details: {e}") from e
    except RateLimitError as e:
        print(f"OpenAI Rate Limit Error: {e}")
        raise RuntimeError(f"API Rate Limit Exceeded. Details: {e}") from e
    except BadRequestError as e:
         print(f"OpenAI Bad Request Error: {e}")
         # This often indicates issues with the input format, model name, or parameters
         raise ValueError(f"Invalid request sent to API (check model name, input format, parameters). Details: {e}") from e
    except APIError as e:
        print(f"OpenAI API Error: {e}")
        raise RuntimeError(f"Generic API Error occurred. Details: {e}") from e
    except Exception as e:
        print(f"An unexpected error occurred during OpenAI API call: {e}")
        raise RuntimeError(f"Could not get response from API. Details: {e}") from e


def generate_openai_stream(
    api_key: str,
    history: List[Dict[str, Any]],
    prompt_data: Union[str, List[Any]],
    # generation_config is less directly applicable, use standard params
) -> Iterator[str]:
    client = _prepare_openai_client(api_key)
    messages = _format_openai_messages(history, prompt_data)

    print(f"Streaming from OpenAI endpoint ({MODEL_NAME}) with {len(messages)} messages...")

    try:
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1, # As requested
            top_p=1.0,       # As requested
            n=1,
            stream=True
        )

        finish_reason = None
        for chunk in stream:
            # Check for content filter or other stop reasons in the chunk
            if chunk.choices:
                delta = chunk.choices[0].delta
                chunk_finish_reason = chunk.choices[0].finish_reason
                if chunk_finish_reason:
                    finish_reason = chunk_finish_reason
                    print(f"OpenAI Stream Finish Reason received: {finish_reason}")
                    if finish_reason == 'content_filter':
                         # Stop yielding and raise an exception
                         raise Exception("Content generation stopped by API due to content filter.")
                    # Other reasons like 'stop', 'length' will just end the stream naturally

                # Yield content if present
                if delta and delta.content:
                    yield delta.content
            else:
                # Handle cases where a chunk might not have choices (e.g., errors, unusual responses)
                print(f"Warning: Received stream chunk with no choices: {chunk}")


        # After loop, check final finish reason if needed
        if finish_reason == 'length':
            print("Warning: Stream may have been truncated due to length limits.")

    except AuthenticationError as e:
        print(f"OpenAI Authentication Error during stream: {e}")
        raise RuntimeError(f"Invalid API Key or Authentication Failed. Check settings. Details: {e}") from e
    except RateLimitError as e:
        print(f"OpenAI Rate Limit Error during stream: {e}")
        raise RuntimeError(f"API Rate Limit Exceeded. Details: {e}") from e
    except BadRequestError as e:
         print(f"OpenAI Bad Request Error during stream: {e}")
         raise ValueError(f"Invalid request sent to API (check model name, input format, parameters). Details: {e}") from e
    except APIError as e:
        # Handle potential API errors during streaming
        print(f"OpenAI API Error during stream: {e}")
        # Check if it's related to content filtering if possible (might be in e.body or e.message)
        if "content management policy" in str(e).lower() or "content filter" in str(e).lower():
             raise Exception(f"Content generation stopped by API filter (reported as APIError). Details: {e}") from e
        raise RuntimeError(f"API Error during streaming. Details: {e}") from e
    except Exception as e:
        # Catch the specific exception raised for content filter above
        if "Content generation stopped" in str(e):
            raise # Re-raise the specific content filter exception
        print(f"An unexpected error occurred during OpenAI API streaming: {e}")
        raise RuntimeError(f"Could not stream from API. Details: {e}") from e


# --- Example Usage (for testing) ---
if __name__ == "__main__":
    # Load API key from environment variable (recommended)
    # Make sure to set GOOGLE_API_KEY in your environment
    api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        exit(1)

    # Example conversation history (internal format)
    chat_history = [
        {"role": "user", "parts": ["Hello!"]},
        {"role": "model", "parts": ["Hi there! How can I help you today?"]},
    ]

    # --- Test Non-Streaming ---
    print("\n--- Testing Non-Streaming (OpenAI Client) ---")
    try:
        prompt = "Explain the difference between temperature and top_p in LLMs in simple terms."
        response = get_openai_response(api_key, chat_history, prompt)
        print("\nAPI Response:")
        print(response)
        # Add response to history for next turn (using internal format)
        chat_history.append({"role": "user", "parts": [prompt]})
        chat_history.append({"role": "model", "parts": [response]})
    except Exception as e:
        print(f"\nError getting non-streaming response: {e}")

    # --- Test Streaming ---
    print("\n--- Testing Streaming (OpenAI Client) ---")
    try:
        next_prompt = "Thanks! Now tell me a short story about a curious robot."
        print(f"\nUser: {next_prompt}")
        print("\nAPI Streaming Response:")
        full_streamed_response = ""
        stream = generate_openai_stream(api_key, chat_history, next_prompt)
        for chunk in stream:
            print(chunk, end="", flush=True)
            full_streamed_response += chunk
        print("\n--- End of Stream ---")
        # Add response to history (using internal format)
        chat_history.append({"role": "user", "parts": [next_prompt]})
        chat_history.append({"role": "model", "parts": [full_streamed_response]})

    except Exception as e:
        print(f"\nError getting streaming response: {e}")

    # --- Test Multimodal Streaming (Requires a sample image) ---
    print("\n--- Testing Multimodal Streaming (OpenAI Client) ---")
    # Create a dummy image file for testing if needed
    sample_image_path = "sample_image.png"
    try:
        if not os.path.exists(sample_image_path):
             print(f"Creating dummy image: {sample_image_path}")
             img = Image.new('RGB', (60, 30), color = 'red')
             img.save(sample_image_path)

        img_prompt = "Describe this image and tell me a joke."
        print(f"\nUser: {img_prompt} (with image: {sample_image_path})")
        print("\nAPI Streaming Response:")

        # Prepare prompt_data with text and image object
        image_obj = Image.open(sample_image_path)
        multimodal_prompt_data = [img_prompt, image_obj]

        full_streamed_response = ""
        stream = generate_openai_stream(api_key, chat_history, multimodal_prompt_data)
        for chunk in stream:
            print(chunk, end="", flush=True)
            full_streamed_response += chunk
        print("\n--- End of Stream ---")
        chat_history.append({"role": "user", "parts": [img_prompt]})
        chat_history.append({"role": "model", "parts": [full_streamed_response]})

    except ImportError:
         print("\nSkipping multimodal test: Pillow library not installed.")
    except FileNotFoundError:
         print(f"\nSkipping multimodal test: Sample image not found at {sample_image_path}")
    except Exception as e:
        print(f"\nError getting multimodal streaming response: {e}")
