import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import getpass
from typing import Optional, Union, Iterator, List
import sys
import re
import time
import json

def filter_string(s: str) -> str:
    return ''.join(re.findall(r'[a-zA-Z0-9.,]', s))

class LLM:
    _model_name = None
    _client = None

    @classmethod
    def initialize(cls, model_name: str = "gemini-2.0-flash-lite"):
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        
        if api_key is None:
            print("No GOOGLE_API_KEY found in environment or .env file.", file=sys.stderr)
            print("\nEnter Google API key for in-memory temporary use: ", file=sys.stderr)
            api_key = getpass.getpass("")
            
        cls._model_name = model_name
        cls._client = genai.Client(api_key=api_key)

    @classmethod
    def run(
        cls,
        system_prompt: str,
        user_prompt: str,
        *,
        config: Optional[types.GenerateContentConfig] = None,
        image: Optional[Union[bytes]] = None,
        stream: bool = False,
        force_json_output: bool = False
    ) -> Union[str, Iterator[str]]:
        """Run the Gemini model with system and user prompts.
        
        Args:
            system_prompt: The system instruction for the model
            user_prompt: The user input prompt
            config: Optional additional generation configuration
            image: Optional image data as bytes or PIL Image
            stream: Whether to stream the response
            force_json_output: If True, repeatedly prompt LLM for valid JSON output
        """
        if cls._client is None:
            cls.initialize()

        # Prepare contents with user prompt and optional image
        contents = []
        print(f"DEBUG: LLM.run received user_prompt: '{user_prompt}'")
        if not user_prompt:
            print("No user prompt provided", file=sys.stderr)
            return
       
        # system_prompt = filter_string(system_prompt) # This line was causing issues with JSON output.
       
        if force_json_output:
            # Strongly instruct the LLM to output JSON
            # json_instruction = "\n\nYOUR ENTIRE RESPONSE MUST BE A SINGLE, VALID JSON OBJECT. DO NOT INCLUDE ANY OTHER TEXT OR MARKDOWN OUTSIDE THE JSON BLOCK. ENSURE IT STARTS WITH '{' AND ENDS WITH '}'."
            # system_prompt = system_prompt.strip() + json_instruction
            if config is None:
                config = types.GenerateContentConfig()
            config.response_mime_type = "application/json"

        # print(f"System prompt: {system_prompt}")
        print(f"User prompt: {user_prompt}")

        contents.append(user_prompt)

        
        if image is not None:
            contents.append(image)

        generation_config = None
        if config is None:
            generation_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,  # Higher temperature for more varied responses
                max_output_tokens=1024,
                candidate_count=1,
                top_p=0.95,
                top_k=40
            )
        else:
            generation_config = config
            generation_config.system_instruction = system_prompt

        
        max_retries = 5
        base_delay = 1  # seconds
        max_json_retries = 3 # Max retries specifically for JSON parsing

        for retry_count in range(max_retries):
            try:
                if stream:
                    response = cls._client.models.generate_content_stream(
                        model=cls._model_name,
                        contents=contents,
                        config=generation_config
                    )
                    return (chunk.text for chunk in response)
                
                # Non-streaming response handling, with JSON retry logic
                for json_retry_count in range(max_json_retries):
                    response = cls._client.models.generate_content(
                        model=cls._model_name,
                        contents=contents,
                        config=generation_config
                    )
                    raw_response_text = response.text

                    if force_json_output:
                        try:
                            # With response_mime_type, the output should already be pure JSON
                            _ = json.loads(raw_response_text)
                            print("--------------------------------")
                            print(f"LLM responded with valid JSON (after {json_retry_count} JSON retries).")
                            return raw_response_text
                        except json.JSONDecodeError as json_e:
                            print(f"Warning: LLM response was not valid JSON (JSON retry {json_retry_count+1}/{max_json_retries}): {json_e}", file=sys.stderr)
                            if json_retry_count < max_json_retries - 1:
                                json_delay = base_delay * (2 ** json_retry_count)
                                print(f"Retrying LLM call for valid JSON in {json_delay} seconds...", file=sys.stderr)
                                time.sleep(json_delay)
                            else:
                                raise ValueError(f"LLM failed to produce valid JSON after {max_json_retries} retries. Raw response: {raw_response_text}")
                    else:
                        # If not forcing JSON, just return the text as is
                        print("--------------------------------")
                        # print(response) # Removed this line, raw response is logged elsewhere
                        return raw_response_text

            except Exception as e:
                print(f"An error occurred: {e}", file=sys.stderr)
                if retry_count < max_retries - 1:
                    delay = base_delay * (2 ** retry_count)
                    print(f"Retrying in {delay} seconds...", file=sys.stderr)
                    time.sleep(delay)
                else:
                    print("Max retries reached. Failing...", file=sys.stderr)
                    raise