import json
import sys
from mcp.server.fastmcp import FastMCP
from utilities import StoreProducts

mcp=FastMCP("retail-chain-mcp")

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

def main():
    # Only run test if not in MCP mode
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test()
    else:
        # Start MCP server without any print statements
        mcp.run(transport='stdio')

def test():
    print("Testing get_store_product_info tool...")
    print (get_store_product_info("milk"))

if __name__ == "__main__":
    main()    
    