from src.screen import VM
from src.llm import LLM
from src.prompt_j2_management import get_vision_model_prompt
from PIL import Image
import io

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
                return "Error: LLM did not return a valid string or stream."