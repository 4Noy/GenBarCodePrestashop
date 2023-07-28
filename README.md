```
    _____     _____      __      _   ______      ____     ______       ____     ____     ______      _____  
   / ___ \   / ___/     /  \    / ) (_   _ \    (    )   (   __ \     / ___)   / __ \   (_  __ \    / ___/  
  / /   \_) ( (__      / /\ \  / /    ) (_) )   / /\ \    ) (__) )   / /      / /  \ \    ) ) \ \  ( (__    
 ( (  ____   ) __)     ) ) ) ) ) )    \   _/   ( (__) )  (    __/   ( (      ( ()  () )  ( (   ) )  ) __)   
 ( ( (__  ) ( (       ( ( ( ( ( (     /  _ \    )    (    ) \ \  _  ( (      ( ()  () )   ) )  ) ) ( (      
  \ \__/ /   \ \___   / /  \ \/ /    _) (_) )  /  /\  \  ( ( \ \_))  \ \___   \ \__/ /   / /__/ /   \ \___  
   \____/     \____\ (_/    \__/    (______/  /__(  )__\  )_) \__/    \____)   \____/   (______/     \____\ 
By Noy.
```


This tool generate you Barcodes from a given supplier cart with Prestashop.

# Cart Management Application

This is a Python script for a Cart Management Application that allows users to manage product information in a cart. The application utilizes the Flask framework for web development and includes functionalities such as sorting, adding, modifying, and removing products from the cart.

## Prerequisites

Before running the application, ensure you have the following installed:

1. Python 3 - You can download and install Python from the official website: [https://www.python.org/](https://www.python.org/)

2. Python packages:
   - pyodbc: `pip install pyodbc`
   - reportlab: `pip install reportlab`
   - Flask: `pip install Flask`
   - python-barcode: `pip install python-barcode`
   - Pillow (PIL): `pip install Pillow`

## Getting Started

1. Clone the repository to your local machine.

2. Verify if the `ini.json` file exists in the project directory. This file contains login information required to connect to the database.

3. Modify the `ini.json` file with your database server, username, password, database name, and driver information.

## ini.json

The Cart Management Application uses a database to store product information and cart details. To configure the database, open the `ini.json` file and modify the following parameters:

- `server`: The address of the database server.
- `database`: The name of the database to use.
- `username`: The username to authenticate with the database server.
- `password`: The password for the database user.
- `driver`: The ODBC driver to use for database connections.

Make sure to provide accurate and secure login information to ensure proper database connectivity.

## How to Run

1. Open a terminal or command prompt and navigate to the project directory.

2. Run the Flask application by executing the following command:

```
python3 cart_management_app.py
```

3. Once the application is running, access it by visiting `http://localhost:5001` in your web browser.

## Features

The Cart Management Application provides the following functionalities:

- **Sorting**: Allows users to sort products in the cart based on different columns and in ascending or descending order.

- **Adding Products**: Users can add new products to the cart by providing the EAN13 code of the product. The application verifies if the product exists in the database before adding it to the cart.

- **Modifying Quantity**: Users can modify the quantity of a product already present in the cart.

- **Removing Products**: Products can be removed from the cart.

- **Merging Carts**: Users can merge the current cart with another cart identified by the supplier's name or ID.

## Author

- [Noy](https://github.com/4Noy/).

## Version

- 0.1

## Acknowledgments

- [Flask](https://flask.palletsprojects.com/) - The web framework used
- [pyodbc](https://github.com/mkleehammer/pyodbc) - Python ODBC Database API
- [reportlab](https://www.reportlab.com/) - Library for creating PDFs and charts
- [python-barcode](https://github.com/WhyNotHugo/python-barcode) - Library for creating barcodes
- [Pillow (PIL)](https://python-pillow.org/) - Python Imaging Library

Please note that this README provides a general overview of the application. For a more detailed understanding of the code and functionalities, refer to the source code and comments within the Python script.

For safe usage, just modify ini.json.