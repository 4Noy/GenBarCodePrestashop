#!/usr/bin/env python3
# -*- coding: utf-8 -*-


__author__ = "Noy."
__version__ = "0.1"

"""
NEEDS :
Python 3 - to install : go on the website https://www.python.org/
pyodbc python package - to install : pip install pyodbc
reportlab python package - to install : pip install reportlab
flask python package - to install : pip install Flask
python-barcode python package - to install : pip install python-barcode
PIL python package - to install : pip install Pillow
"""

from flask import Flask, redirect, request, send_file, url_for
from barcode import EAN13
from barcode.writer import ImageWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image
import pyodbc, os, json, math

# Verify if the ini.json file exists
if not os.path.exists("ini.json"):
    print("The ini.json file doesn't exists.")
    #Create a ini.json file with the default values
    ini = {
        "server": "localhost",
        "database": "prestashop",
        "username": "root",
        "password": "",
        "driver": "ODBC Driver 18 for SQL Server"
    }
    with open("ini.json", "w") as f:
        json.dump(ini, f, indent=4)
    print("The ini.json file has been created with the default values.")
    exit()

# Get logins info on ini.json
with open("ini.json", "r") as f:
    ini = json.load(f)
server = ini["server"]
database = ini["database"]
username = ini["username"]
password = ini["password"]
driver = ini["driver"]



original_path = os.getcwd()

app = Flask(__name__)

def get_text_height(text, font_name, font_size):
    return stringWidth(text, font_name, font_size)


def wrap_text(text, max_width, font, font_size):
    lines = simpleSplit(text, font, font_size, max_width)
    return "\n".join(lines)

def GetPolicySizeAndWrapText(text, max_width, max_height, font_name, max_font_size, min_font_size=3):
    #split the text
    lines = text.split("\n")
    #try to find the good font size wraping the text
    font_size = max_font_size
    while font_size > min_font_size:
        # try to wrap the text with the current font size
        lines = wrap_text(text, max_width, font_name, font_size).split("\n")
        # calculate the height of the text
        height = len(lines) * get_text_height("A", font_name, font_size)*mm

        # if the height is good, return the lines and the font size
        if height <= max_height:
            return (lines, font_size)
        # else, try with a smaller font size
        font_size -= 0.5
    #if font size is too small, set to min font size and cut the text while it's too big
    if font_size < min_font_size:
        font_size = min_font_size
        while font_size < max_font_size:
            # try to wrap the text with the current font size
            lines = wrap_text(text, max_width, font_name, font_size).split("\n")
            # calculate the height of the text
            height = len(lines) * get_text_height("A", font_name, font_size)
            # if the height is good, return the lines and the font size
            if height <= max_height:
                return (lines, font_size)
            # else, remove the last line and try again
            lines.pop()
    return (lines, font_size)

def GetProductsInfos(idCartSupplier):
    # Get all the products infos from the database
    # Return a list of productsinfos : (ean, name, price, quantity to print, ref supplier, quantity in stock, quantity ordered)
    # connect to the database
    
    #how to find my odbc driver : 
    conn = pyodbc.connect('DRIVER={'+driver+'};SERVER='+server+';DATABASE='+database+';ENCRYPT=yes;UID='+username+';PWD='+ password)
    # create a cursor
    cursor = conn.cursor()
    # first, take the id_cart from the table mi_wkdelivery_orders then take the quantity from mi_wkdelivery_cart_product with the id_cart
    # execute the query
    cursor.execute("SELECT id_cart FROM mi_wkdelivery_orders WHERE id_wkdelivery_orders = "+str(idCartSupplier))
    # verify if the cart exists
    fet = cursor.fetchone()
    if fet == None:
        print("The cart with id : "+str(idCartSupplier)+" doesn't exists.")
        return []
    # get the result
    id_cart = fet[0]
    # then foreach product in the cart, take the quantity in mi_wkdelivery_cart_product and the id_product in mi_wkdelivery_cart_product, then go to mi_product_lang to take the name
    # then to mi_product to take the ean13, the ref supplier and the price. Then, take in mi_product the id_tax_rules_group and go to mi_tax_rule then take id_tax and go to mi_tax then take the rate
    # execute the query
    cursor.execute("SELECT id_product, quantity FROM mi_wkdelivery_cart_product WHERE id_cart = "+str(id_cart))
    # get the result
    products = cursor.fetchall()
    # all infos of the products must be like this (ean, name, price, quantity, ref supplier)
    productsInfos = []
    for product in products:
        cursor.execute("SELECT name FROM mi_product_lang WHERE id_product = "+str(product[0]))
        name = cursor.fetchone()[0]
        cursor.execute("SELECT ean13, price, id_tax_rules_group FROM mi_product WHERE id_product = "+str(product[0]))
        productInfos = cursor.fetchone()
        # I have to get the supplier reference from the table mi_product_supplier with the id_product (name of property : product_supplier_reference)
        cursor.execute("SELECT product_supplier_reference FROM mi_product_supplier WHERE id_product = "+str(product[0]))
        refSupplier = cursor.fetchone()
        refSupplier = str(refSupplier).replace("(", "").replace(")", "").replace("'", "").replace(",", "").replace(" ", "")
        # first i need to take the id_tax in mi_tax_rule with id_tax_rules_group
        cursor.execute("SELECT id_tax FROM mi_tax_rule WHERE id_tax_rules_group = "+str(productInfos[2]))
        id_tax = cursor.fetchone()[0]
        # then i need to take the rate in mi_tax with id_tax
        cursor.execute("SELECT rate FROM mi_tax WHERE id_tax = "+str(id_tax))
        taxRate = cursor.fetchone()[0]
        # calculate the price with the tax rate
        ean13 = productInfos[0]
        name = name.replace("\n", " ")
        price = round(productInfos[1]*(1+taxRate/100), 2)
        quantity = product[1]

        # get the quantity in stock
        cursor.execute("SELECT quantity FROM mi_stock_available WHERE id_product = "+str(product[0]))
        quantityInStock = cursor.fetchone()[0]
        productInfos = (ean13, name, price, quantity, refSupplier, quantityInStock, quantity)
        productsInfos.append(productInfos)
    # close the connection
    conn.close()
    return productsInfos
   


def GeneratePDF(productsInfos, whereToStart=0):
    # Générer un PDF avec les informations des produits, format A4 en portrait
    # Retourner le chemin du PDF

    # Créer le PDF en format A4 en portrait
    pdf = canvas.Canvas("cart.pdf", pagesize=A4)

    # Position initiale du code-barre
    border = 11 * mm
    space_cell_y = 21.2 * mm
    space_cell_x = 38.1 * mm
    x = border
    y = 270 * mm
    nb_line = 0

    for i in range(int(whereToStart)):
        x += space_cell_x
        if x >= (A4[0] - border - 30):
            x = border
            y -= space_cell_y
            nb_line += 1
            if nb_line >= 13:
                #add a new page
                pdf.showPage()
                x = border
                y = 270 * mm
                nb_line = 0 

    for productInfos in productsInfos:
        # get quantity
        # generate the barcode
        quantity = productInfos[3]
        code_filename = f'barcode_{productInfos[0]}'
        try:
            if productInfos[0].isdigit():
                ean = productInfos[0]
                while len(ean) < 13:
                    ean = "0"+ean
                EAN13(ean, writer=ImageWriter()).save(code_filename)
            else: #generate a error
                raise Exception()
        except:
            print("EAN13 : "+str(productInfos[0])+" is not valid of the product : " + productInfos[1] + ".")
            continue
    
        #Remove all white space around the barcode
        # Open the barcode image with PIL
        img = Image.open(code_filename+".png")
        
        # removethe first and last 1/7.5 of the width of the image and the 1/8 of the bottom
        img = img.crop((img.size[0]/7.5, 0, img.size[0]-img.size[0]/7.5, img.size[1]-img.size[1]/8))
        img.save(code_filename+".png")

        for i in range(quantity):

            # add the barcode
            pdf.drawImage(code_filename+".png", x, y, width=36 * mm, height=15 * mm)

            # Add the name of the product
            font_name = "Helvetica"  # Replace with the desired font name
            max_font_size = 10  # Set the initial font size
            max_width = 35 * mm  # Set the maximum width for the text
            max_height = 4 * mm  # Set the maximum height for the text

            (lines, font_size) = GetPolicySizeAndWrapText(productInfos[1], max_width, max_height, font_name, max_font_size)
            pdf.setFont(font_name, font_size)  # Set the font name and size
            y_product_name = y+15*mm + (len(lines)-1)*get_text_height("A", font_name, font_size)*1.3   # Starting Y position for the product name
            for line in lines:
                pdf.drawString(x, y_product_name, line)
                y_product_name -= get_text_height("A", font_name, font_size)+0.8*mm  # Calculate the height of the current line

            
            # add the price in bold and bigger and in dark blue
            pdf.setFont("Helvetica-Bold", 9)
            pdf.setFillColorRGB(0, 0, 0.65)
            # All prices must be like X.XX€ ending with 0
            price = str(productInfos[2])
            if len(price.split(".")) == 1:
                price += ".00"
            elif len(price.split(".")[1]) == 1:
                price += "0"

            # calculate the width of the price
            width_price = stringWidth(price + "€", "Helvetica-Bold", 9)
            pdf.drawString(x+35*mm-width_price, y - 2.8 * mm, price + "€")
            pdf.setFillColorRGB(0, 0, 0)

            ### !!!! INVERT THE REF SUPPLIER AND PRICE !!!! ###

            # add the ref supplier
            pdf.setFont("Helvetica", 6)
            pdf.drawString(x, y - 2.8 * mm, productInfos[4])
            

            x += space_cell_x
            if x >= (A4[0] - border - 30):
                x = border
                y -= space_cell_y
                nb_line += 1
                if nb_line >= 13:
                    #add a new page
                    pdf.showPage()
                    x = border
                    y = 270 * mm
                    nb_line = 0
        # now remove the barcode file
        try:
            os.remove(code_filename+".png")
        except:
            print("Can't remove the file : "+code_filename+".png")

    # save pdf
    pdf.save()

    return "cart.pdf"


def GetSupplierInfos():
    # Get the infos of the supplier
    conn = pyodbc.connect('DRIVER={'+driver+'};SERVER='+server+';DATABASE='+database+';ENCRYPT=yes;UID='+username+';PWD='+ password)
    # create a cursor
    cursor = conn.cursor()
    # Get all reference of mi_wkdelivery_orders and 
    cursor.execute("SELECT id_wkdelivery_orders, reference FROM mi_wkdelivery_orders")
    # get the result
    suppliersInfos = cursor.fetchall()
    # close the connection
    conn.close()
    # the format of the result is : (id_wkdelivery_orders, reference)
    # return the result sorted by id_wkdelivery_orders reversed
    return sorted(suppliersInfos, key=lambda x: x[0], reverse=True)

def GetProductInfos(ean13):
    # Connect to the database and get the infos of the product
    # Return a list of productsinfos : (ean, name, price, quantity, ref supplier, quantity in stock, quantity ordered=0)
    # connect to the database
    conn = pyodbc.connect('DRIVER={'+driver+'};SERVER='+server+';DATABASE='+database+';ENCRYPT=yes;UID='+username+';PWD='+ password)
    # create a cursor
    cursor = conn.cursor()
    # first, take the id_product from the table mi_product then take the name from mi_product_lang with the id_product
    # execute the query
    cursor.execute("SELECT id_product FROM mi_product WHERE ean13 = "+str(ean13))
    # verify if the product exists
    fet = cursor.fetchone()
    if fet == None:
        print("The product with ean13 : "+str(ean13)+" doesn't exists.")
        return []
    # get the result
    id_product = fet[0]
    # then take the name from mi_product_lang with the id_product
    # execute the query
    cursor.execute("SELECT name FROM mi_product_lang WHERE id_product = "+str(id_product))
    # get the result
    name = cursor.fetchone()[0]
    # then take the price from mi_product with the id_product
    # execute the query
    cursor.execute("SELECT price FROM mi_product WHERE id_product = "+str(id_product))
    # get the result
    price = cursor.fetchone()[0]
    # first i need to take the id_tax in mi_tax_rule with id_tax_rules_group
    # execute the query
    cursor.execute("SELECT id_tax_rules_group FROM mi_product WHERE id_product = "+str(id_product))
    # get the result
    id_tax_rules_group = cursor.fetchone()[0]
    # then i need to take the id_tax in mi_tax_rule with id_tax_rules_group
    # execute the query
    cursor.execute("SELECT id_tax FROM mi_tax_rule WHERE id_tax_rules_group = "+str(id_tax_rules_group))
    # get the result
    id_tax = cursor.fetchone()[0]
    # then i need to take the rate in mi_tax with id_tax
    # execute the query
    cursor.execute("SELECT rate FROM mi_tax WHERE id_tax = "+str(id_tax))
    # get the result
    taxRate = cursor.fetchone()[0]
    # calculate the price with the tax rate
    price = round(price*(1+taxRate/100), 2)
    # then take the ref supplier from mi_product_supplier with the id_product
    # execute the query
    cursor.execute("SELECT product_supplier_reference FROM mi_product_supplier WHERE id_product = "+str(id_product))
    # get the result
    refSupplier = cursor.fetchone()[0]
    refSupplier = str(refSupplier).replace("(", "").replace(")", "").replace("'", "").replace(",", "").replace(" ", "")
    # then take the quantity in stock from mi_stock_available with the id_product
    # execute the query
    cursor.execute("SELECT quantity FROM mi_stock_available WHERE id_product = "+str(id_product))
    # get the result
    quantityInStock = cursor.fetchone()[0]
    # close the connection
    conn.close()
    # the format of the result is : (ean, name, price, quantity, ref supplier, quantity in stock, quantity ordered=0)
    # return the result
    return [(ean13, name, price, 1, refSupplier, quantityInStock, 0)]
    


def ImpressPDF(pathPDF):
    # Print the PDF
    pass

def LaunchGenerationProcess(productsInfos, whereToStart=0):
    # Launch the generation of the PDF
    GeneratePDF(productsInfos, whereToStart)
    # Print the PDF
    ImpressPDF("cart.pdf")
    

@app.route('/')
def index():
    if not os.path.exists("data"):
        os.mkdir("data")
    # Create a html page with a form to enter the id of the cart supplier
    # and a search bar to search a supplier by his reference
    suppliersInfos = GetSupplierInfos()
    html = """ 
    <html>
        <head>
            <title>Cart</title>
        </head>
        <body>
            <center>
                <h1>Generateur de Code Barre</h1>
            
            <form action="/gotID" method="post">
                <label for="idCartSupplier">ID</label>
                <input type="text" id="idCartSupplier" name="idCartSupplier" list="idsuppliers">
                <datalist id="idsuppliers">"""
    # add the datalist with all the suppliers id
    for supplierInfos in suppliersInfos:
        html += "<option value='"+str(supplierInfos[0])+"'>"
    html += """
                </datalist>
                <input type="submit" value="Lancer">    
            </form>
    """
    
    # add search bar so when the user search a supplier by his reference and auto complete the reference
    html += """
            <form action="/searchSupplier" method="post">
                <label for="searchSupplier">Name</label>
                <input type="text" id="searchSupplier" name="searchSupplier" list="suppliers">
                <datalist id="suppliers">
    """
    for supplierInfos in suppliersInfos:
        html += "<option value='"+supplierInfos[1]+"'>"
    
    html += """
                </datalist>
                <input type="submit" value="Lancer">
            </form>
            <form action="/addProduct" method="post">
                <input type="hidden" id="idCartSupplier" name="idCartSupplier" value=''>
                <input type="text" id="ean13" name="ean13" placeholder="EAN13">
                <input type="submit" value="Ajouter Produit">
            </form>
            <form action="/EditBuffer">
                <input type="submit" value="Charger Codes Barres Enregistrés">
            </form>
            <form action="/DeleteSavedFiles">
                <input type="submit" value="Supprimer les fichiers enregistrés">
            </form>
    """

    
    html += """
        </center>
        </body>
    </html>
    """

    return html

@app.route('/generatePDF', methods=['POST'])
def generatePDF():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    # Get the where to start from the form
    whereToStart = request.form['whereToStart']
    # Get all the products infos from the database
    productsInfos = json.load(open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "r"))
    # Launch the generation of the PDF
    LaunchGenerationProcess(productsInfos, whereToStart)
    # show the PDF
    return send_file("cart.pdf", as_attachment=True)

@app.route('/EditInfos/<idCartSupplier>/<int:isFirstTime>/<int:sort_column>/<sort_order>')
def EditInfos(idCartSupplier, isFirstTime, sort_column,sort_order=0):
    html = """
    <html>
        <head>
            <title>Cart</title>
            <script>

            function sortTable(column) {
                // Create a form element
                var form = document.createElement("form");
                form.method = "post";
                form.action = "/sort";

                // Add idCartSupplier as a hidden input field
                var idCartSupplierInput = document.createElement("input");
                idCartSupplierInput.type = "hidden";
                idCartSupplierInput.name = "idCartSupplier";
                idCartSupplierInput.value = \""""+ str(idCartSupplier) +"""\"; // Remplacez cette valeur par l'idCartSupplier approprié

                // Add sort_order as a hidden input field
                var sort_orderInput = document.createElement("input");
                sort_orderInput.type = "hidden";
                sort_orderInput.name = "sort_order";
                sort_orderInput.value = column + \"_"""+str(sort_order)+"_"+str(sort_column) +"""\";
                // Add the inputs to the form
                form.appendChild(idCartSupplierInput);
                form.appendChild(sort_orderInput);

                // Add the form to the document and submit it
                document.body.appendChild(form);
                form.submit();
            }
            </script>


            <style>
                table, th, td {
                    border: 1px solid black;
                    border-collapse: collapse;
                    padding: 5px;
                    text-align: center;
                    font-family: Arial, Helvetica, sans-serif;
                    font-size: 14px;
                    //space beetwen the column to not be to close
                    border-spacing: 5px;

                }
                .quantity-container {
                    display: inline-flex;
                    align-items: center;
                }

                .product-quantity {
                    margin-right: 10px;
                }
                //reduce the size of the input
                .quantity-form input {
                    width: 25px;
                }
                // Put the buttons on the same line
                #buttons {
                    display: inline-flex;
                }

                .sort-icon {
                    display: inline-block;
                    width: 0;
                    height: 0;
                    margin-left: 5px;
                    vertical-align: middle;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                }

                .sorted-asc .sort-icon {
                    border-bottom: 4px solid #000; /* Replace #000 with the color of your choice */
                }

                .sorted-desc .sort-icon {
                    border-top: 4px solid #000; /* Replace #000 with the color of your choice */
                }
            </style>
        </head>
        <body>
        <span id="buttons">
            <form action="/chosePlaceToStart" method="post">
                <input type="hidden" id="idCartSupplier" name="idCartSupplier" value='"""+str(idCartSupplier)+"""'>
                <input type="submit" value="Suivant">
            </form>
            <form action="/addProduct" method="post">
                <input type="hidden" id="idCartSupplier" name="idCartSupplier" value='"""+str(idCartSupplier)+"""'>
                <input type="text" id="ean13" name="ean13" placeholder="EAN13">
                <input type="submit" value="Ajouter Produit">
            </form>
            <form action="/mergeCarts" method="post">
                <input type="hidden" id="idCartSupplier" name="idCartSupplier" value='"""+str(idCartSupplier)+"""'>"""
    
    # Like in the index function, add a search bar to search a supplier by his reference
    suppliersInfos = GetSupplierInfos()
    html += """
                <input type="text" id="nameMergeCart" name="nameMergeCart" list="suppliers" placeholder="Name">
                <datalist id="suppliers">
    """
    for supplierInfos in suppliersInfos:
        html += "<option value='"+supplierInfos[1]+"'>"


    html+="""
                </datalist>   
                """
    # the same but with idCartSupplier
    html += """
                <input type="text" id="idMergeCart" name="idMergeCart" list="carts" placeholder="ID">
                <datalist id="carts">
    """
    for supplierInfos in suppliersInfos:
        html += "<option value='"+str(supplierInfos[0])+"'>"
    html += """
                </datalist>
                <input type="submit" value="Ajouter une Commande">
            </form>
            <form action="/">
                <input type="submit" value="Enregistrer et Retour">
            </form>
        </span>
            <table id="myTable">
                <tr>
                    <th><button onclick="sortTable(0)">Quantité commandée<span class="sort-icon"></span></button></th>
                    <th><button onclick="sortTable(1)">Quantité<span class="sort-icon"></span></button></th>
                    <th><button onclick="sortTable(2)">Stock<span class="sort-icon"></span></button></th>
                    <th><button onclick="sortTable(3)">Nom<span class="sort-icon"></span></button></th>
                    <th><button onclick="sortTable(4)">Prix<span class="sort-icon"></span></button></th>
                    <th><button onclick="sortTable(5)">EAN<span class="sort-icon"></span></button></th>
                    <th><button onclick="sortTable(6)">Ref Fournisseur<span class="sort-icon"></span></button></th>
                    <th>Actions</th>

                </tr>
    """
    # isFirstime is a int, so doing ifFirstTime == 1 is the same as doing isFirstTime
    if isFirstTime:
        productsInfos = GetProductsInfos(idCartSupplier)
        # store the products infos in json file
        with open(original_path + "/data/productsInfos_"+str(idCartSupplier)+".json", "w") as f:
            json.dump(productsInfos, f, default=str)
    else:
        productsInfos = json.load(open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "r"))
    # add the products infos in the table
    for productInfos in productsInfos:
        # the quantity and the input must be in the same line
        html += """
                <tr>
                    <td>"""+str(productInfos[6])+"""</td>
                    
                    <td>
                        <div class="quantity-container">
                            <span class="product-quantity">""" + str(productInfos[3]) + """</span>
                            <form class="quantity-form" action="/modifyQuantity" method="post">
                                <input type="hidden" id="idCartSupplier" name="idCartSupplier" value='""" + str(idCartSupplier) + """'>
                                <input type="hidden" id="ean13" name="ean13" value='""" + str(productInfos[0]) + """'>
                                <input type="number" id="quantity" name="quantity" value='""" + str(productInfos[3]) + """'>
                            </form>
                        </div>
                    </td>

                    <td>"""+str(productInfos[5])+"""</td>

                    <td>"""+str(productInfos[1])+"""</td>
                    <td>"""+str(productInfos[2])+"""€</td>
                    <td>"""+str(productInfos[0])+"""</td>
                    <td>"""+str(productInfos[4])+"""</td>
                    <td>
                        <form action="/removeProduct" method="post">
                            <input type="hidden" id="idCartSupplier" name="idCartSupplier" value='"""+str(idCartSupplier)+"""'>
                            <input type="hidden" id="ean13" name="ean13" value='"""+str(productInfos[0])+"""'>
                            <input type="submit" value="Supprimer">
                        </form>
                    </td>
                </tr>
        """


    html += """
            </table>
        </body>
    </html>
    """

    return html

@app.route('/sort', methods=['POST'])
def sort():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    # Get the sort order from the form
    sort_order = request.form['sort_order']
    # Get all the products infos from the database
    productsInfos = json.load(open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "r"))
    # sort the products infos
    # sort_order is like this : column_sortDirection
    # column is the number of the column to sort
    # sortDirection is the direction of the sort : asc or desc
    column = int(sort_order.split("_")[0])
    sortDirection = sort_order.split("_")[1]
    pastSortColumn = int(sort_order.split("_")[2])
    if pastSortColumn == column:
        if sortDirection == "asc":
            sortDirection = "desc"
        else:
            sortDirection = "asc"
    else:
        sortDirection = "asc"
    sort_order = str(column)+"_"+sortDirection+"_"+str(column)
    if column == 0:
        productsInfos = sorted(productsInfos, key=lambda x: x[6], reverse=sortDirection=="desc")
    elif column == 1:
        productsInfos = sorted(productsInfos, key=lambda x: x[3], reverse=sortDirection=="desc")
    elif column == 2:
        productsInfos = sorted(productsInfos, key=lambda x: x[5], reverse=sortDirection=="desc")
    elif column == 3:
        productsInfos = sorted(productsInfos, key=lambda x: x[1], reverse=sortDirection=="desc")
    elif column == 4:
        productsInfos = sorted(productsInfos, key=lambda x: x[2], reverse=sortDirection=="desc")
    elif column == 5:
        productsInfos = sorted(productsInfos, key=lambda x: x[0], reverse=sortDirection=="desc")
    elif column == 6:
        productsInfos = sorted(productsInfos, key=lambda x: x[4], reverse=sortDirection=="desc")
    # store the products infos in json file
    with open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "w") as f:
        json.dump(productsInfos, f, default=str)
    # redirect to EditInfos
    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=column, sort_order=sortDirection))

@app.route('/DeleteSavedFiles')
def DeleteSavedFiles():
    # delete all the files in the data folder
    for filename in os.listdir(original_path+"/data"):
        os.remove(original_path+"/data/"+filename)
    # redirect to main page /
    return redirect(url_for('index'))

@app.route('/EditBuffer')
def EditBuffer():
    if os.path.exists(original_path+"/data/productsInfos_Buffer.json"):
        # redirect to EditInfos
        return redirect(url_for('EditInfos', idCartSupplier="Buffer", isFirstTime=0, sort_column=0, sort_order="asc"))
    return redirect(url_for('index'))

@app.route('/addProduct', methods=['POST'])
def addProduct():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    # Get the ean13 of the product from the form
    ean13 = request.form['ean13']
    if os.path.exists(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json"):
        # Get all the products infos from the database
        productsInfos = json.load(open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "r"))
    elif os.path.exists(original_path+"/data/productsInfos_Buffer.json"):
        # Get all the products infos from the database
        idCartSupplier = "Buffer"
        productsInfos = json.load(open(original_path+"/data/productsInfos_Buffer.json", "r"))
    else:
        idCartSupplier = "Buffer"
        with open(original_path+"/data/productsInfos_Buffer.json", "w") as f:
            json.dump([], f, default=str)
        productsInfos = []
    if ean13 == "":
        # redirect to EditInfos
        return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))
    if idCartSupplier != "Buffer":
        for productInfos in productsInfos:
            if productInfos[0] == ean13:
                # the product is already in the cart
                # redirect to EditInfos
                return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))
    else:
        for productInfos in productsInfos:
            if productInfos[0] == ean13:
                productInfos[3] += 1
                with open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "w") as f:
                    json.dump(productsInfos, f, default=str)
                return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))
    # get the infos of the product from the database
    productInfos = GetProductInfos(ean13)
    # if the product doesn't exists, redirect to EditInfos
    if len(productInfos) == 0:
        return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))
    # add the product in the cart
    productsInfos.append(productInfos[0])
    # store the products infos in json file
    with open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "w") as f:
        json.dump(productsInfos, f, default=str)
    if idCartSupplier == "Buffer":
        return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))
    # redirect to EditInfos
    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))

    

@app.route('/modifyQuantity', methods=['POST'])
def modifyQuantity():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    # Get the ean13 of the product from the form
    ean13 = request.form['ean13']
    # Get the quantity of the product from the form
    quantity = request.form['quantity']
    # modify the quantity of the product in json file
    productsInfos = json.load(open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "r"))
    for productInfos in productsInfos:
        if productInfos[0] == ean13:
            productInfos[3] = int(quantity)
            break
    # store the products infos in json file
    with open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "w") as f:
        json.dump(productsInfos, f, default=str)

    # redirect to EditInfos
    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))

@app.route('/removeProduct', methods=['POST'])
def removeProduct():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    # Get the ean13 of the product from the form
    ean13 = request.form['ean13']
    # remove the product from the cart in json file
    productsInfos = json.load(open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "r"))
    for productInfos in productsInfos:
        if productInfos[0] == ean13:
            productsInfos.remove(productInfos)
            break
    # store the products infos in json file
    with open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "w") as f:
        json.dump(productsInfos, f, default=str)

    # redirect to EditInfos
    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))

@app.route('/searchSupplier', methods=['POST'])
def searchSupplier():
    # Get the reference of the supplier from the form
    reference = request.form['searchSupplier']
    # Get the id of the cart supplier from the reference
    idCartSupplier = ""
    suppliersInfos = GetSupplierInfos()
    for supplierInfos in suppliersInfos:
        if supplierInfos[1] == reference:
            idCartSupplier = supplierInfos[0]
            break
    if idCartSupplier == "":
        # redirect to main page /
        return redirect(url_for('index'))
    if os.path.exists(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json"):
        # redirect to EditInfos
        return redirect(url_for('savedCart', idCartSupplier=idCartSupplier))
    # redirect to EditInfos
    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=1, sort_column=0, sort_order="asc"))

@app.route('/mergeCarts', methods=['POST'])
def mergeCarts():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    # Get the name of the cart to merge from the form
    nameMergeCart = request.form['nameMergeCart']
    # Get the id of the cart to merge from the form
    idMergeCart = request.form['idMergeCart']
    # if both are empty, redirect to EditInfos
    if nameMergeCart == "" and idMergeCart == "":
        return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))
    # if nameMergeCart is not empty, get the id of the cart to merge from the name  
    if nameMergeCart != "" and idMergeCart == "":
        suppliersInfos = GetSupplierInfos()
        for supplierInfos in suppliersInfos:
            if supplierInfos[1] == nameMergeCart:
                idMergeCart = supplierInfos[0]
                break
    
    # Get all the products infos from the database
    productsInfos = json.load(open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "r"))
    # create the products infos of the cart to merge
    productsInfosToMerge = GetProductsInfos(idMergeCart)
    # add the products infos of the cart to merge in the cart
    for productInfosToMerge in productsInfosToMerge:
        # first, verify if the product is not already in the cart
        for productInfos in productsInfos:
            if productInfos[0] == productInfosToMerge[0]:
                productInfos[3] += productInfosToMerge[3]
                productInfos[6] += productInfosToMerge[3]
                break
        else:
            # the product is not in the cart
            # add the product in the cart
            productsInfos.append(productInfosToMerge)
    # store the products infos in json file
    with open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "w") as f:
        json.dump(productsInfos, f, default=str)
    # redirect to EditInfos
    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))
    

@app.route('/savedCart/<idCartSupplier>')
def savedCart(idCartSupplier):
    if os.path.exists(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json"):
        html = """
        <html>
            <head>
                <title>Cart</title>
            </head>
            <body>
                <center>
                    <h1>Generateur de Code Barre</h1>
                    <form action="/UseSavedCart" method="post">
                        <input type="hidden" id="idCartSupplier" name="idCartSupplier" value='"""+str(idCartSupplier)+"""'>
                        <input type="submit" value="Utiliser le panier enregistré">
                    </form>
                    <form action="/UseNewCart" method="post">
                        <input type="hidden" id="idCartSupplier" name="idCartSupplier" value='"""+str(idCartSupplier)+"""'>
                        <input type="submit" value="Utiliser un nouveau panier">
                    </form>
                </center>
            </body>
        </html>
        """
        return html

    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=1, sort_column=0, sort_order="asc"))

@app.route('/UseNewCart', methods=['POST'])
def UseNewCart():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    # redirect to EditInfos
    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=1, sort_column=0, sort_order="asc"))

@app.route('/UseSavedCart', methods=['POST'])
def UseSavedCart():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=0, sort_column=0, sort_order="asc"))

@app.route('/gotID', methods=['POST'])
def gotID():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    if os.path.exists(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json"):
        # redirect to EditInfos
        return redirect(url_for('savedCart', idCartSupplier=idCartSupplier))
    # redirect to EditInfos
    return redirect(url_for('EditInfos', idCartSupplier=idCartSupplier, isFirstTime=1, sort_column=0, sort_order="asc"))

@app.route('/chosePlaceToStart', methods=['POST'])
def chosePlaceToStart():
    # Get the id of the cart supplier from the form
    idCartSupplier = request.form['idCartSupplier']
    # Get all the products infos from the database
    # show a clickable table to know where to start
    # my table must be 5 x 13
    html = """
    <html>
        <head>
            <title>Cart</title>
            <style>
                #myTable {
                    width: 210mm;
                    height: 297mm;
                }
                table, th, td {
                    border: 1px solid black;
                    border-collapse: collapse;
                    padding: 5px;
                    text-align: center;
                    font-family: Arial, Helvetica, sans-serif;
                    font-size: 14px;
                    border-spacing: 5px;
                }
                td:hover {
                    background-color: lightgrey;
                    cursor: pointer;
                }
                p {
                    font-family: Arial, Helvetica, sans-serif;
                    font-size: 14px;
                }
            </style>
            <script>
                function handleClick(index) {
                    document.getElementById('whereToStart').value = index;
                    document.getElementById('myForm').submit();
                }
            </script>
        </head>
        <body>"""
    html += """
        <span id="buttons">"""
    html += f"        <form action=\"/EditInfos/{idCartSupplier}/0/0/asc\">"

    html += """            <input type="hidden" id="idCartSupplier" name="idCartSupplier" value=\"""" +str(idCartSupplier) +"""\"> """
    html += """
                <input type="submit" value="Back">
            </form>
            <form action="/">
                <input type="submit" value="Retour à la page principale">
            </form>
            <form id="myForm" action="/generatePDF" method="post">"""
    html += """            <input type="hidden" id="idCartSupplier" name="idCartSupplier" value=\"""" +str(idCartSupplier) +"""\"> """
    html += """
                <input type="hidden" id="whereToStart" name="whereToStart" value="">
            </form>
            </span>
            """
    # Now show the number of etiquettes and the number of pages
    # number of etiquettes = number of products
    # number of etiquettes = quantity of the product foreach product
    with open(original_path+"/data/productsInfos_"+str(idCartSupplier)+".json", "r") as f:
        productsInfos = json.load(f)
    quantity = sum([productInfos[3] for productInfos in productsInfos])

    html += f"""
    <div id="infos">
            <p>Nombre d'étiquettes : {quantity}</p>
            <p>Nombre de pages : {math.ceil(quantity/65)}</p>
            <p>Nombre de produits : {len(productsInfos)}</p>
            <p>Nombre de produits sur la dernière page : {quantity%65}</p>
    </div>
            """
    html +="""
            <table id="myTable">
    """
    # create the table
    for i in range(13):
        html += "<tr>"
        for j in range(5):
            index = i * 5 + j
            html += f"<td onclick='handleClick({index})'>{index+1}</td>"
        html += "</tr>"
    html += """
            </table>
        </body>
    </html>
    """
    return html


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)