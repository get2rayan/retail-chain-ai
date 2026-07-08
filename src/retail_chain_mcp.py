import json
import sys
from fastmcp import FastMCP
from utilities import StoreProducts

mcp=FastMCP("retail-chain-mcp", description="A retail chain management tool that provides information about stores and products.")

@mcp.tool()
def get_store_product_info(product_name:str=None, store_id:int=None, department:str=None) -> str:
    """
    Retrieve store and product information for a given product and/or store, and/or department.

    Arguments:
    product_name: Name of the product to search for (optional).
    store_id: ID of the store to search in (optional).
    department: Department within the store to search in (optional).
    """
    sp = StoreProducts()
    product_info = sp.get_store_products(product_name, store_id, department)
    return json.dumps({"product_info": product_info})

@mcp.tool()
def get_products_by_store(store_id:int, department:str=None) -> str:
    """
    Retrieve products for a specific store.

    Arguments:
    store_id: ID of the store to search in.
    department: Department within the store to search in (optional).
    
    IMPORTANT: Use this tool when a user wants to see all products in a specific store.
    """
    sp = StoreProducts()
    product_info = sp.get_store_products(store_id=store_id, department=department)
    return json.dumps({"product_info": product_info})

def main():
    # Only run test if not in MCP mode
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test()
    else:
        # Start MCP server without any print statements
        mcp.run(transport="stdio")

def test():
    print("Testing get_store_product_info tool...", file=sys.stderr)
    print (get_store_product_info("milk"), file=sys.stderr)
    print("Testing get_products_by_store tool...", file=sys.stderr)
    print (get_products_by_store(21), file=sys.stderr)

if __name__ == "__main__":
    main()    
    