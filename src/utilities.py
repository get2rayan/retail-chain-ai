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
                # directory of current notebook        
                current_dir = os.path.abspath('')
                # full file path
                file_path = os.path.join(current_dir, 'data', products_file)
                self.df = pd.read_csv(file_path, header=0)                    
            return self.df
        except Exception as e:
            print(f"Error loading store products: {e}")
            pass


    def get_store_products(self, product_name=None, storeid=None):
        """
        filter the store and product list for the specific product name
        
        Parameter(s):
        product_name: name of the product to look for in a store (if specified)
        storeid : integer representing a store (if specified)
        
        Returns:
        product details for the requested product as dictionary
        """
        print (f"\nget_store_products argument received : {product_name} ,  {storeid}")
        sp = self.available_products
        # print (f"product is : {product_name} storeid is {storeid}")
        try:
            if not sp.empty:
                try:
                    if storeid is not None and int(storeid)>0:
                        sp = sp.query(f'store=={storeid}')
                except ValueError:
                    pass
                if product_name:
                    sp = sp.query(f'product=="{product_name}"')
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
    print(sp.get_store_products("", 21))
#####