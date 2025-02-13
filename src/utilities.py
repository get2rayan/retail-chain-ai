import os
import pandas as pd

# csv file that has the store and products info such as
# the storeid, product name, price and promotion details
products_file = os.getenv('STORE_PRODUCTS_FILE')

class StoreProducts:
    """
    Deal with operations for reading the store and product info from the products file
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
                ## path for notebook file - .pynb
                # directory of current notebook        
                current_dir = os.path.abspath('')
                # full file path
                file_path = os.path.join(current_dir, 'data', products_file)
                self.df = pd.read_csv(file_path, header=0)                    
            return self.df
        except Exception as e:
            print(e)
            pass

if __name__ == "__main__":
    sp = StoreProducts()
    print(sp.available_products.head(5))

