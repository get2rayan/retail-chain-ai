import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
from utilities import StoreProducts

class StoreProductChat():
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
            "description": "Get the details of the product requested by the user. Call this whenever you need to know the product availability, price or to check if it is in promotion, for example when a customer asks 'do you have this product' or 'what is the price of this product' or 'is this product available' or 'which stores have this product available'",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The product that the customer wants details about"
                    },            
                },
                "required": ["product_name"],
                "additionalProperties": False
            }
        }

        self.tools = [{"type": "function", "function": products_tool}]
        self.tool_functions = [{"name": "get_store_products", "function": self.get_store_products}]

        self.MODEL =self.openai_model

        self.system_message="""You are a helpful assistant for a retail store ordering system. \
        Customers may check with you for available products, prices or promotions. \
        Give short, courteous answers. Always be accurate. If you don't know the answer, say so
        """
        self.openai = OpenAI(api_key=self.openai_api_key)


    def get_store_products(self, product_name):
        """
        filter the store and product list for the specific product name
        
        Returns:
        product details for the requested product as dictionary
        """
        sp = StoreProducts().available_products
        if not sp.empty:
            product = sp.query(f'product=="{product_name}"')
            return product.to_dict('records')
        else:
            return None
        

    def handle_tool_call(self, message):
        """
        method to handle tool calls

        Returns:
        response: response message for the tool call invocation
        """
        for item in message.tool_calls:
            function_entry = [ func for func in self.tool_functions if 'name' in func and func['name']==item.function.name]
            function = function_entry[0].get('function')
            arguments = json.loads(item.function.arguments)
            argument = arguments[next(iter(arguments))]
            product_info = function(argument)
            response = {
                "role": "tool",
                "content": json.dumps({"product_name": argument, "product_info": product_info}),
                "tool_call_id": item.id
            }
            return response
        

    def chat(self, message, history):
        """
        method with signature appropriate to be used for Gradio chat interface
        """
        messages = [{"role": "system", "content": self.system_message}] + history + [{"role": "user", "content": message}]
        response = self.openai.chat.completions.create(model=self.MODEL, messages=messages, tools=self.tools, tool_choice="auto")
        
        if response.choices[0].finish_reason=="tool_calls":
            message = response.choices[0].message
            response = self.handle_tool_call(message)
            messages.append(message)
            messages.append(response)
            response = self.openai.chat.completions.create(model = self.MODEL, messages=messages)
                            
        return response.choices[0].message.content


if __name__=="__main__":
    gr.ChatInterface(fn=StoreProductChat().chat, type="messages").launch()
