import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

# csv file that has the store and products info such as
# the storeid, product name, price and promotion details
products_file = os.getenv('STORE_PRODUCTS_FILE')

class StoreProducts:
    """
    methods for reading the store and product info from the products file
    """
    def __init__(self):
        self.df = None
           
    @property
    def available_products(self):
        if self.df is None:
            self.__load_store_products()
        return self.df
    
    def __load_store_products(self): 
        """
        private method to read the product information file

        Returns:
        df: The items from the file populated into a dataframe
        """
        try:
            if self.df is None:
                # Get the directory where this script is located
                script_dir = os.path.dirname(os.path.abspath(__file__))
                # Go up one level to the parent directory, then into data folder
                parent_dir = os.path.dirname(script_dir)
                # full file path
                file_path = os.path.join(parent_dir, 'data', products_file)
                self.df = pd.read_csv(file_path, header=0)                    
            return self.df
        except Exception as e:
            print(f"Error loading store products: {e}")
            pass

    def get_store_products(self, product_name=None, store_id=None, department=None):
        """
        filter the store and product list for the specific product name
        
        Parameter(s):
        product_name: name of the product to look for in a store (if specified)
        store_id : integer representing a store (if specified)
        department: department in the store (if specified)
        
        Returns:
        product details for the requested product as dictionary
        """
        print (f"\nget_store_products argument received : product {product_name} , store {store_id}, department {department}")
        sp = self.available_products
        # print (f"product is : {product_name} storeid is {storeid}")
        try:
            if not sp.empty:
                try:
                    if store_id is not None and int(store_id)>0:
                        sp = sp.query(f'store=={store_id}')
                except ValueError:
                    pass
                if product_name:
                    sp = sp.query(f'product.str.contains("{product_name}", case=False)', engine='python')
                if department:
                    sp = sp.query(f'department.str.contains("{department}", case=False)', engine='python')
                return sp.to_dict('records')
            else:
                return None
        except Exception as e:
            print(f"Error getting store products: {e}")
            pass

    
#####
# local Validation
if __name__ == "__main__":
    sp = StoreProducts()
    print(sp.get_store_products("", 21, "Meat"))
#####