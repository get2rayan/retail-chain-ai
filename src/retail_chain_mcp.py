import json
import sys
from mcp.server.fastmcp.server import FastMCP
from utilities import StoreProducts
from logger_config import logger
from guardrails import GuardrailViolation, sanitize_search_inputs

mcp=FastMCP("retail-chain-mcp", instructions="A retail chain management tool that provides information about stores and products.")

@mcp.tool()
def get_store_product_info(
    product_name: str | None = None,
    store_id: int | None = None,
    department: str | None = None,
) -> str:
    """
    Retrieve store and product information for a given product and/or store, and/or department.

    Arguments:
    product_name: Name of the product to search for (optional).
    store_id: ID of the store to search in (optional).
    department: Department within the store to search in (optional).
    """
    try:
        product_name, store_id, department = sanitize_search_inputs(product_name, store_id, department)
    except GuardrailViolation as exc:
        logger.warning("Rejected MCP search request: %s", exc)
        return json.dumps({"error": str(exc)})
    sp = StoreProducts()
    product_info = sp.get_store_products(product_name, store_id, department)
    return json.dumps({"product_info": product_info})

@mcp.tool()
def get_products_by_store(store_id: int, department: str | None = None) -> str:
    """
    Retrieve products for a specific store.

    Arguments:
    store_id: ID of the store to search in.
    department: Department within the store to search in (optional).
    
    IMPORTANT: Use this tool when a user wants to see all products in a specific store.
    """
    try:
        _, store_id, department = sanitize_search_inputs(store_id=store_id, department=department)
    except GuardrailViolation as exc:
        logger.warning("Rejected MCP store request: %s", exc)
        return json.dumps({"error": str(exc)})
    sp = StoreProducts()
    product_info = sp.get_store_products(store_id=store_id, department=department)
    return json.dumps({"product_info": product_info})

def main():
    # Only run test if not in MCP mode
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test()
    else:
        # Start MCP server without any print statements
        # mcp.run(transport="stdio")
        # mcp.run(transport="sse")

        import uvicorn
        from starlette.middleware.cors import CORSMiddleware

        app = mcp.streamable_http_app()
        app.add_middleware(CORSMiddleware, 
                           allow_origins=["*"], 
                           allow_methods=["*"], 
                           allow_headers=["*"], 
                           allow_credentials=True)
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")


def test():
    logger.info("Testing get_store_product_info tool...")
    logger.info(get_store_product_info("milk"))
    logger.info("Testing get_products_by_store tool...")
    logger.info(get_products_by_store(21))

if __name__ == "__main__":
    main()    
    