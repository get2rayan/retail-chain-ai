import asyncio
import json
import os
from typing import Any

import gradio as gr
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, Runner
from agents.mcp import MCPServerStreamableHttp
from dotenv import load_dotenv
from openai import AsyncOpenAI
from openai.types.shared import Reasoning

from PictureAgent import PictureAgent
from guardrails import GuardrailViolation, sanitize_input
from logger_config import logger

load_dotenv()


INSTRUCTIONS = """You are a helpful assistant for a retail store ordering system.
Use the connected MCP tools to answer questions about products, prices,
availability, departments, and promotions. Never invent store or product
information.

Do not assume a product, store, or department unless the user explicitly
provided it. If a product is requested without a store, search all available
stores. Use the all-products-by-store tool when the user asks for all products
at a specific store. Store identifiers are integers.

Keep answers short, courteous, and accurate. If the request is ambiguous or
required information is missing, ask a clarifying question."""


class StoreProductMcpAgentAigw:
    def __init__(self) -> None:
        api_key = os.getenv("INFERENCE_API_KEY")
        model_name = os.getenv("INFERENCE_MODEL")
        self.mcp_server_url = os.getenv("MCP_SERVER_AIGW_URL")
        mcp_api_key = os.getenv("MCP_SERVER_AIGW_API_KEY")
        auth_header = os.getenv("MCP_SERVER_AIGW_AUTH_HEADER", "Authorization").strip()
        auth_scheme = os.getenv("MCP_SERVER_AIGW_AUTH_SCHEME", "Bearer").strip()

        if not api_key:
            raise ValueError("INFERENCE_API_KEY is not configured")
        if not model_name:
            raise ValueError("INFERENCE_MODEL is not configured")
        if not self.mcp_server_url:
            raise ValueError("MCP_SERVER_AIGW_URL is not configured")
        if not mcp_api_key:
            raise ValueError("MCP_SERVER_AIGW_API_KEY is not configured")
        if not auth_header:
            raise ValueError("MCP_SERVER_AIGW_AUTH_HEADER cannot be empty")

        auth_value = f"{auth_scheme} {mcp_api_key}" if auth_scheme else mcp_api_key
        self.mcp_headers = {auth_header: auth_value}

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=os.getenv("INFERENCE_BASE_URL") or None,
        )
        self.model = OpenAIChatCompletionsModel(
            model=model_name,
            openai_client=client,
        )

    async def chat(self, history: list[dict[str, Any]]) -> tuple[str, list[str]]:
        if not history or not isinstance(history[-1], dict):
            raise ValueError("Chat history must contain the latest user message")

        message = history[-1].get("content")
        try:
            # Validate the new turn and prior user turns before sending them to the model.
            sanitized_message = sanitize_input(message, "message")
            conversation: list[dict[str, str]] = []
            for item in history:
                if not isinstance(item, dict):
                    continue
                role = item.get("role")
                content = item.get("content")
                if role not in {"user", "assistant"} or not isinstance(content, str):
                    continue
                if role == "user":
                    content = sanitize_input(content, "message") or ""
                conversation.append({"role": role, "content": content})
        except GuardrailViolation as exc:
            logger.warning("Rejected chat request: %s", exc)
            return "I can't process that request because it failed input safety checks.", []

        conversation.append({"role": "user", "content": sanitized_message or ""})
        server = MCPServerStreamableHttp(
            params={"url": self.mcp_server_url, "headers": self.mcp_headers},
            name="retail-chain-mcp-aigw",
        )
        # Attaching the MCP server lets the SDK discover and call its tools as needed.
        agent = Agent(
            name="Retail Store Assistant",
            instructions=INSTRUCTIONS,
            model=self.model,
            model_settings=ModelSettings(reasoning=Reasoning.model_construct(effort="none")),
            mcp_servers=[server],
        )

        # Keep the connection open for the entire agent run, including tool calls.
        async with server:
            result = await Runner.run(agent, input=conversation)

        if not isinstance(result.final_output, str) or not result.final_output.strip():
            raise RuntimeError("The retail agent returned no text response")
        product_items = self._products_from_run(result.new_items)
        return result.final_output, product_items

    @staticmethod
    def _products_from_run(run_items: list[Any]) -> list[str]:
        """Extract product names from MCP tool outputs for optional image generation."""
        products: list[str] = []
        for item in run_items:
            if getattr(item, "type", None) != "tool_call_output_item":
                continue
            output = getattr(item, "output", None)
            if not isinstance(output, str):
                continue
            try:
                product_info = json.loads(output).get("product_info")
            except (json.JSONDecodeError, AttributeError):
                continue
            if not isinstance(product_info, list):
                continue
            products.extend(
                product["product"]
                for product in product_info
                if isinstance(product, dict) and isinstance(product.get("product"), str)
            )
        return products

    async def chat_with_image(
        self, history: list[dict[str, Any]], enabled_agents: list[str] | None
    ) -> tuple[list[dict[str, Any]], Any]:
        response, product_items = await self.chat(history)
        updated_history = [*history, {"role": "assistant", "content": response}]
        image = None

        if "Image" in (enabled_agents or []) and product_items:
            # PictureAgent uses synchronous image APIs, so avoid blocking Gradio's event loop.
            image = await asyncio.to_thread(PictureAgent().generateImage, product_items)

        return updated_history, image


if __name__ == "__main__":
    app = StoreProductMcpAgentAigw()
    with gr.Blocks() as ui:
        with gr.Row():
            chatbot = gr.Chatbot(height=500, type="messages")
            image_output = gr.Image(height=500)
        with gr.Row():
            entry = gr.Textbox(label="Chat with our Store AI")
        with gr.Row():
            with gr.Accordion("Agent options", open=False):
                enabled_agents = gr.CheckboxGroup(
                    ["Image"], label="Select agents to enable"
                )
            clear = gr.Button("Clear")

        def add_user_message(
            message: str, chat_history: list[dict[str, Any]]
        ) -> tuple[str, list[dict[str, Any]]]:
            return "", [*chat_history, {"role": "user", "content": message}]

        entry.submit(
            fn=add_user_message,
            inputs=[entry, chatbot],
            outputs=[entry, chatbot],
        ).then(
            fn=app.chat_with_image,
            inputs=[chatbot, enabled_agents],
            outputs=[chatbot, image_output],
        )

        clear.click(
            lambda: (None, None),
            inputs=None,
            outputs=[chatbot, image_output],
            queue=False,
        )

    ui.queue().launch(inbrowser=True, debug=True)