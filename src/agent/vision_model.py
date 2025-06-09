from .llm import LLM
from .prompt_j2_management import get_vision_model_prompt
from PIL import Image
import io
import time

class VisionModel:
    def __init__(self):
        self.llm = LLM()

    def analyze(self, image_bytes: bytes, question: str) -> str:
        """Analyzes an image (bytes) with a question using the LLM.

        Args:
            image_bytes: The image data in bytes.
            question: The question to ask about the image.

        Returns:
            An unstructured text response from the vision model.
        """
        system_prompt = get_vision_model_prompt()
        
        # Convert image_bytes to a PIL Image object
        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            return f"Error: Could not process image bytes. {e}"

        max_retries = 5
        base_delay = 1  # seconds

        for retry_count in range(max_retries):
            try:
                # The user_prompt for LLM.run will be the question itself.
                # The image will be the PIL Image object.
                response = self.llm.run(
                    system_prompt=system_prompt,
                    user_prompt=question, 
                    image=pil_image
                )
                
                if isinstance(response, str):
                    return response
                else:
                    try:
                        return "".join(list(response))
                    except TypeError:
                        raise Exception("LLM did not return a valid string or stream.")

            except Exception as e:
                print(f"An error occurred during Vision Model analysis: {e}")
                if retry_count < max_retries - 1:
                    delay = base_delay * (2 ** retry_count)
                    print(f"Retrying Vision Model analysis in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print("Max retries reached for Vision Model analysis. Failing...")
                    return f"Error: Max retries reached for Vision Model analysis. Last error: {e}"