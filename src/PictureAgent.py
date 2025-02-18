import os
from openai import OpenAI
from dotenv import load_dotenv
import base64
from io import BytesIO
from PIL import Image

class PictureAgent:
    """
    Image generation AI agent 
    """

    def __init__(self):
        # Initialization
        load_dotenv()
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            print("OpenAI API Key not set")      

        self.openai = OpenAI(api_key=openai_api_key)


    def generateImage(self,content):
        """
        method to invoke image generating ai by passing a list of items / products to diplay in the image

        Parameter(s):
        content: List of items to display in the image

        Returns:
        image content of the generated image
        """
        prompt = f"""Generate a collage of product images for {', '.join(content)}.  The most important requirement is that *no product image should overlap any other* and show only the products mentioned.  \n
                Each item must be clearly visible and distinct. Arrange the images in a clean and organized manner, with sufficient spacing between them.  \n
                The images should be high-quality and realistic, evoking the feeling of browsing in a store. The items should appear only once."""
        
        response=self.openai.images.generate(
                model="dall-e-3",
                prompt = prompt,
                size="1024x1024",
                n=1,
                response_format="b64_json"
            )

        image_base64 = response.data[0].b64_json
        image_data = base64.b64decode(image_base64)
        return Image.open(BytesIO(image_data))


#####
# local Validation
if __name__=="__main__":
    image = PictureAgent().generateImage(["milk", "fish", "orange"])
    display(image)
#####