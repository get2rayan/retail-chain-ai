import asyncio
import os
import json
from logger_config import logger
from dotenv import load_dotenv
from openai import AsyncOpenAI
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import gradio as gr
from PictureAgent import PictureAgent
from guardrails import GuardrailViolation, sanitize_input

load_dotenv()
        
class StoreProductChatMcp:
    """
    interact with a chat interface about the store and product information
    """
    def __init__(self):
        # Initialization
        self.inference_api_key = os.getenv('INFERENCE_API_KEY')
        self.inference_model = os.getenv('INFERENCE_MODEL')
        self.inference_base_url = os.getenv('INFERENCE_BASE_URL')
        self.mcp_server_url = os.getenv('MCP_SERVER_URL')

        if not self.inference_api_key:
            logger.warning("Inference API Key not set")
        if not self.mcp_server_url:
            raise ValueError("MCP_SERVER_URL is not configured")

        self.MODEL =self.inference_model
        self.system_message="""You are a helpful assistant for a retail store ordering system.
        Customers may check with you for a list of available products in a store, their prices, availability or items that are in promotion at a store. Alternatively, they may also check for items in a specific department such as produce, deli etc.
        **Crucially, do not make any assumptions about products or stores unless explicitly specified by the user.**  If a product is not specified, do not substitute or guess a product; your tool calls should reflect the lack of product information.
        If a customer checks on a product without specifying a store, search the product in all available stores.
        Store information, if one provided is represented by a store number, which is an integer.
        When making tool calls, ensure that the 'store', 'product' or 'department' fields are populated *only* if the user has explicitly provided that information.  **Do not fill these fields with default values or guesses.** Leave the fields empty (null or equivalent in your tool call structure) if the user has not provided the information.
        Give short, courteous, and accurate answers. If you don't know the answer or lack the necessary information from the user, say so politely.
        """
        self.openai = AsyncOpenAI(api_key=self.inference_api_key, base_url=self.inference_base_url)
        logger.debug(f"AI tools setup complete. Model: {self.MODEL}")

    # Convert the live MCP catalog to the function-tool schema expected by chat completions.
    @staticmethod
    def openai_tools_from_mcp(mcp_tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in mcp_tools
        ]

    async def handle_tool_call(self, session, tool_calls):
        """
        method to handle tool calls

        Parameter(s):
        tool_calls: LLM tool calls to be executed

        Returns:
        response: response message for the tool call invocation
        """
        # list to store tool call response
        tool_results = []

        for tool_call in tool_calls:
            logger.debug(f"\nInvoking tool call: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
            arguments = json.loads(tool_call.function.arguments)
            try:
                result = await session.call_tool(tool_call.function.name, arguments)
                content_parts = []
                for block in result.content:
                    text = getattr(block, "text", None)
                    content_parts.append(
                        text if text is not None else json.dumps(block.model_dump(mode="json"))
                    )
                tool_content = "\n".join(content_parts)
                if not tool_content and result.structuredContent is not None:
                    tool_content = json.dumps(result.structuredContent)
                if result.isError and not tool_content:
                    tool_content = json.dumps({"error": "MCP tool call failed"})
            except Exception:
                logger.exception("MCP tool call failed: %s", tool_call.function.name)
                tool_content = json.dumps({"error": "MCP tool call failed"})

            logger.debug(f"\nTool call result for {tool_call.function.name}: {tool_content}")
            tool_results.append({
                "role": "tool",
                "content": tool_content,
                "tool_call_id": tool_call.id
            })

        return tool_results
        
    async def chat(self, history):
        """
        method with signature appropriate to be used for Gradio chat interface

        Parameter(s):
        message: latest prompt message from the user
        history: history of the user and LLM call messages

        Returns:
        response: response.choices[0].message.content output from ai after feeding tool call execution result
        toolCallResponse: indicator whether a tool_call was made
        """
        # user prompt will be the last message in chat history
        userprompt = history[-1]        
        message = userprompt.get('content')
        try:
            message = sanitize_input(message, "message")
            history[-1] = {**history[-1], "content": message}
        except GuardrailViolation as exc:
            logger.warning("Rejected chat request: %s", exc)
            # raise gr.Error(f"I can't process that request because it failed input safety checks: {exc}")
            return "I can't process that request because it failed input safety checks.", None

        messages = [{"role": "system", "content": self.system_message}] + history
        logger.debug(f"\nchat messages to ai : {history}")
        tool_call_response=None

        # Keep discovery and tool execution in one session with the configured server.
        async with streamablehttp_client(self.mcp_server_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                mcp_tools = await session.list_tools()
                tools = self.openai_tools_from_mcp(mcp_tools.tools)
                response = await self.openai.chat.completions.create(
                    model=self.MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    reasoning_effort="none",
                )

                if response.choices[0].finish_reason == "tool_calls":
                    assistant_message = response.choices[0].message
                    tool_call_response = await self.handle_tool_call(
                        session, assistant_message.tool_calls
                    )
                    messages.append(assistant_message)
                    messages.extend(tool_call_response)
                    response = await self.openai.chat.completions.create(
                        model=self.MODEL,
                        messages=messages,
                    )

        logger.debug(f"\nai chat response : {response}")
        return response.choices[0].message.content, tool_call_response

#####
# Validation for simple Chat
# if __name__=="__main__":
#     gr.ChatInterface(fn=StoreProductChat().chat, type="messages").launch()
#####

    async def chatWithImage(self, history, agent_list):
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
        # get the LLM response for the user prompt
        response, toolCallResponse = await self.chat(history)
        # update bot response in chatbot history
        history.append({"role": "assistant", "content": response})
        
        # initialize image object
        image = None
                
        if "Image" in (agent_list or []):
            product_items = []
            for tool_result in toolCallResponse or []:
                try:
                    product_info = json.loads(tool_result["content"]).get("product_info")
                except (KeyError, TypeError, json.JSONDecodeError):
                    continue
                if isinstance(product_info, list):
                    product_items.extend(
                        item["product"]
                        for item in product_info
                        if isinstance(item, dict) and item.get("product")
                    )
            if product_items:
                # Image generation is synchronous, so keep it off Gradio's async event loop.
                image = await asyncio.to_thread(PictureAgent().generateImage, product_items)

        return history, image

# Validation for chatWithImage
if __name__ == "__main__":

    with gr.Blocks() as ui:
        with gr.Row():
            chatbot = gr.Chatbot(height=500, type='messages')
            image_output = gr.Image(height=500)
        with gr.Row():
            entry=gr.Textbox(label='Chat with our Store AI')        
        with gr.Row():
            with gr.Accordion("Agent options", open=False):
                enabled_agents = gr.CheckboxGroup(["Image"], label="Select agents to enable")                

            clear = gr.Button("Clear")

        def do_entry(message, chat_history):
            chat_history.append({"role": "user", "content": message})
            return "", chat_history

        entry.submit(fn=do_entry, inputs=[entry, chatbot], outputs=[entry, chatbot]).then(
                    fn=StoreProductChatMcp().chatWithImage, inputs=[chatbot, enabled_agents], outputs=[chatbot, image_output])

        clear.click(lambda: None, inputs= None, outputs=chatbot, queue=False)

    ui.queue().launch(inbrowser=True, debug=True)
