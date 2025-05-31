import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import getpass
from typing import Optional, Union, Iterator, List
import sys

class LLM:
    _model_name = "gemini-2.0-flash"
    _client = None

    @classmethod
    def initialize(cls, model_name: str = "gemini-2.0-flash"):
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
        stream: bool = False
    ) -> Union[str, Iterator[str]]:
        """Run the Gemini model with system and user prompts.
        
        Args:
            system_prompt: The system instruction for the model
            user_prompt: The user input prompt
            config: Optional additional generation configuration
            image: Optional image data as bytes or PIL Image
            stream: Whether to stream the response
        """
        if cls._client is None:
            cls.initialize()

        # Prepare contents with user prompt and optional image
        contents = []
        
        if not user_prompt:
            print("No user prompt provided", file=sys.stderr)
            return
        
        contents.append(user_prompt)
        
        if image is not None:
            contents.append(image)

        generation_config = None
        if config is None:
            generation_config = types.GenerateContentConfig(system_instruction=system_prompt)
        else:
            generation_config = config
            generation_config.system_instruction = system_prompt

        if stream:
            response = cls._client.models.generate_content_stream(
                model=cls._model_name,
                contents=contents,
                config=generation_config
            )
            return (chunk.text for chunk in response)
        
        response = cls._client.models.generate_content(
            model=cls._model_name,
            contents=contents,
            config=generation_config
        )
        return response.text
