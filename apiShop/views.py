import json
import time

import firebase_admin
import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from firebase_admin import credentials, firestore

# from models import UserPayment

stripe.api_key = settings.STRIPE_SECRET_KEY

cred = credentials.Certificate("static/key4_Terminal.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

keyValue = ""

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
                'name': doc_data.get('Status', ''),
                'description': doc_data.get('orderId', ''),
                'price': doc_data.get('price', ''),
                'orders': []  # Initialize an empty list for orders
            }
            # Retrieve the list of order references
            order_references = doc_data.get('list', [])
            # Iterate through the order references
            for order_ref in order_references:
                order_doc = order_ref.get()  # Get the referenced document
                order_data = order_doc.to_dict()  # Extract data from the referenced document
                order_info = {
                    'name': order_data.get('name', ''),
                    'quantity': order_data.get('quantity', 0)
                }
                product_info['orders'].append(order_info)  # Add order information to the list

            request.session['price'] = doc_data.get('price', '')
            request.session['Id'] = doc_data.get('orderId', '')
            request.session['orderId'] = "Order " + doc_data.get('orderId', '')
            # You found a matching document, break the loop
            break

    except Exception as e:
        # Handle any errors that may occur during Firebase interaction
        print("Error: ", e)
        product_info = {}

    return render(request, 'index.html', {'product_info': product_info})

def payment(request):
    if request.method == 'POST':
        # Get the amount from the form (validate this)
        amount = int(request.session.get('price') * 100)

        # Create a payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
        )

        return render(request, 'payment.html', {'client_secret': intent.client_secret})

    return render(request, 'payment_form.html')
def payment_confirmation(request):
    return render(request, 'payment.html')

@csrf_exempt
def stripe_config(request):
    if request.method == 'GET':
        stripe_config = {'publicKey': settings.STRIPE_PUBLISHABLE_KEY}
        return JsonResponse(stripe_config, safe=False)


@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        domain_url = 'http://localhost:8000/'
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            # Parse the JSON object from the request body
            data = json.loads(request.body)

            # Get the email from the parsed JSON object
            email = data.get('email', None)
            code = data.get('code', None)
            phone = data.get('phone', None)

            print(email)
            print(code + phone)
            metadata = {'Id': request.session.get('Id'), "Email": email, "Phone": code + phone}


            # Create the checkout session with metadata
            checkout_session = stripe.checkout.Session.create(
                success_url=domain_url + 'success?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=domain_url + 'cancelled/',
                payment_method_types=['card'],
                mode='payment',
                line_items=[
                    {
                        'price_data': {
                            'currency': 'eur',
                            'product_data': {
                                'name': request.session.get('orderId'),
                            },
                            'unit_amount': int(request.session.get('price') * 100),
                        },
                        'quantity': 1,
                    }
                ],
                metadata=metadata,  # Include the previously defined metadata
            )
            return JsonResponse({'sessionId': checkout_session['id']})
        except Exception as e:
            return JsonResponse({'error': str(e)})

class SuccessView(TemplateView):

    template_name = 'success.html'

class CancelledView(TemplateView):
    template_name = 'cancelled.html'


@csrf_exempt
def stripe_webhook(request, key):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        # Extract the session ID from the event data
        session_id = event['data']['object']['id']

        # Retrieve the metadata, including 'Id', from the session
        session = stripe.checkout.Session.retrieve(session_id)
        metadata = session.metadata

        # Access 'Id' from metadata and update Firestore
        order_id = metadata.get('Id')
        if order_id:
            collection_ref = db.collection("Orders")
            doc_ref = collection_ref.document(order_id)

            # Update the 'Status' field to 'Paid'
            doc_ref.update({"Status": "Paid"})
            user_email = metadata.get('Email')
            user_phone = metadata.get("Phone")
            if user_email:
                print(user_email)
                doc_ref.update({"Email": user_email})
            if user_phone:
                doc_ref.update({"Phone": user_phone})

            print(f"Order {order_id} has been marked as paid.")

    return HttpResponse(status=200)