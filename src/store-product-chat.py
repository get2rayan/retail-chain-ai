import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
from PictureAgent import PictureAgent
from utilities import StoreProducts

class StoreProductChat:
    """
    interact with a chat interface about the store and product information 
    """
    def __init__(self):
        # Initialization
        load_dotenv()
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_model = os.getenv('OPENAI_MODEL')

        if not self.openai_api_key:
            print("OpenAI API Key not set")      
        
        self.setupAiTools()

        
    def setupAiTools(self):
        """
        initialize the attributes necessary for ai interaction
        """
        products_tool={
            "name": "get_store_products",
            "description": "Get the details of the product and/or store requested by the user. Call this whenever you need to know the product availability, \
                  price or to check what products are available in a specific store or which items are in promotion, for example when a customer asks 'do you have this product' or \
                    'what is the price of this product' or 'is this product available' or 'which stores have this product available'",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The product that the customer wants details about"
                    },            
                    "store_id": {
                        "type": "integer",
                        "description": "The store that the customer wants details about"
                    }
                },
                "required": ["product_name", "store_id"],
                "additionalProperties": False
            }
        }

        self.tools = [{"type": "function", "function": products_tool}]
        self.tool_functions = [{"name": "get_store_products", "function": StoreProducts().get_store_products}]

        self.MODEL =self.openai_model

        self.system_message="""You are a helpful assistant for a retail store ordering system. 
        Customers may check with you for a list of available products in a store, their prices, availability or items that are in promotion at a store. 
        **Crucially, do not make any assumptions about products or stores unless explicitly specified by the user.**  If a product is not specified, do not substitute or guess a product; your tool calls should reflect the lack of product information.
        If a customer checks on a product without specifying a store, search the product in all available stores.
        Store information, if one provided is represented by a store number, which is an integer. 
        When making tool calls, ensure that the 'store' and 'product' fields are populated *only* if the user has explicitly provided that information.  **Do not fill these fields with default values or guesses.** Leave the fields empty (null or equivalent in your tool call structure) if the user has not provided the information.
        
        Give short, courteous, and accurate answers. If you don't know the answer or lack the necessary information from the user, say so politely.
        """
        self.openai = OpenAI(api_key=self.openai_api_key)


    def handle_tool_call(self, message):
        """
        method to handle tool calls

        Parameter(s):
        message: LLM message specifying a tool_call

        Returns:
        response: response message for the tool call invocation
        """
        for item in message.tool_calls:
            function_entry = [ func for func in self.tool_functions if 'name' in func and func['name']==item.function.name]
            function = function_entry[0].get('function')
            arguments = json.loads(item.function.arguments)
            
            match item.function.name:
                case 'get_store_products':
                    product_name = arguments.get("product_name")
                    store_id = arguments.get("store_id")

                    product_info = function(product_name, store_id)
                case _:
                    print(f"Error: function not configured - {item.function.name}")
                    product_info = "unknown"
                    
            response = {
                "role": "tool",
                "content": json.dumps({"product_info": product_info}),
                "tool_call_id": item.id
            }
            return response
        

    def chat(self, message, history):
        """
        method with signature appropriate to be used for Gradio chat interface

        Parameter(s):
        message: latest prompt message from the user
        history: history of the user and LLM call messages
        
        Returns:
        response: response.choices[0].message.content output from ai after feeding tool call execution result
        toolCallResponse: indicator whether a tool_call was made 
        """
        messages = [{"role": "system", "content": self.system_message}] + history + [{"role": "user", "content": message}]
        response = self.openai.chat.completions.create(model=self.MODEL, messages=messages, tools=self.tools, tool_choice="auto")
        tool_call_response=None

        # If tool_call specified, invoke custom tool call function
        if response.choices[0].finish_reason=="tool_calls":
            print(f"handle_tool_call invoked for prompt : {message}")
            print(response.choices[0].message)
            message = response.choices[0].message
            # tool call method invocation
            response = self.handle_tool_call(message)
            tool_call_response = response
            messages.append(message)
            messages.append(response)
            response = self.openai.chat.completions.create(model = self.MODEL, messages=messages)
                            
        return response.choices[0].message.content, tool_call_response

#####    
# Validation for simple Chat
# if __name__=="__main__":
#     gr.ChatInterface(fn=StoreProductChat().chat, type="messages").launch()    
#####

    def chatWithImage(self, message, history):
        """
        same as chatSimple but with image agent added

        Parameter(s):
        message: latest prompt message from the user
        history: history of the user and LLM call messages
        
        Returns:
        message: empty string to clear the last typed messaged by the user
        history: history of the chat communication for the AI calls
        image : image output generated by PictureAgent 
        """        
        response, toolCallResponse = self.chat(message, history)
        image = None
        
        if toolCallResponse is not None and toolCallResponse.get('content') is not None:
            content_str=toolCallResponse.get('content')
            product_info = json.loads(content_str)['product_info']
            print(f"product_info : {product_info}")
            
            if product_info !='unknown':
                
                # Get the product items from the list of dictionary
                product_items= [item.get('product') for item in product_info if item.get('product')]

                # Invoke image generation AI method
                image = PictureAgent().generateImage(product_items)
        
        history += [{"role": "user", "content": message}, {"role": "assistant", "content": response}]
        return "", history, image
          


# Validation for chatWithImage
if __name__ == "__main__":

    with gr.Blocks() as ui:
        with gr.Row():
            chatbot = gr.Chatbot(height=500, type="messages")
            image_output = gr.Image(height=500)
        with gr.Row():
            entry=gr.Textbox(label='Chat with our Store AI')
        with gr.Row():
            clear = gr.Button("Clear")

        # def do_entry(message, history):
        #     history += [{"role":"user", "content": message}]
        #     return "", history
        
        entry.submit(fn=StoreProductChat().chatWithImage, inputs=[entry, chatbot], outputs=[entry, chatbot, image_output])

        clear.click(lambda: None, inputs= None, outputs=chatbot, queue=False)

    ui.queue().launch(inbrowser=True)
