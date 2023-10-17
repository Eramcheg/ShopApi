from django.shortcuts import render
import requests
from django.http import JsonResponse
import firebase_admin
from firebase_admin import credentials, firestore


cred = credentials.Certificate("key4_Terminal.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
def get_product_info(request, key):
    product_info = {}
    try:
        # Get a reference to the "Orders" collection
        collection_ref = db.collection("Orders")

        # Create a query to find documents where the "orderId" field matches the given key
        query = collection_ref.where("orderId", "==", key).limit(1)

        # Get the documents that match the query (at most one document should match)
        documents = query.stream()

        # Initialize product_info
        product_info = {}

        for doc in documents:
            # You can access the document reference using doc.reference
            document_ref = doc.reference

            # Retrieve data from the document
            doc_data = doc.to_dict()

            # Create the product_info dictionary
            product_info = {
                'name': doc_data.get('name', ''),
                'description': doc_data.get('description', ''),
                'price': doc_data.get('price', ''),
            }

            # You found a matching document, break the loop
            break

    except Exception as e:
        # Handle any errors that may occur during Firebase interaction
        print("Error: ", e)
        product_info = {}

    return render(request, 'index.html', {'product_info': product_info})