from django.utils import timezone
from django.db import transaction
from django.db.models import F
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.shortcuts import render
from django.core.paginator import Paginator
from rest_framework import generics, permissions, status, response
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from knox.auth import TokenAuthentication
from knox.models import AuthToken
from knox.views import LoginView as KnoxLoginView
from decimal import Decimal, InvalidOperation
from math import radians, sin, cos, sqrt, atan2
import math
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .serializers import (
    AppUserSerializer,
    RegisterSerializer,
    EmailAuthTokenSerializer,
    FooditemSerial,
    Orderserializer,
    RestaurantSerial,
    CartSerializer,
    PlaceOrderSerializer,
    Restaurantlistserial,
    CartReadSerializer,
    RestaurantDetailSerializer,
    DeliverymanSerializer
)
from merchant.models import FoodItem, Restaurant, Order, Cart, OrderItem, DeliverymanStatus, Deliveryman, OrderItemHistory, OrderHistory

from django.db.models import Prefetch
from .serializers import OrderWithItemsSerializer
from django.contrib.sessions.models import Session
from django.apps import apps

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404


def api_overview(request):
    api_urls = {
        'API': {
            'API overview': "/api/",
            'API token': "/api/token/",
            'API token refresh': "/api/token/refresh",
        },
        'User Authentication': {
            'Register App User': "/api/register-user/",
            'Login App User': "/api/login-user/",
            'Logout App User': "/api/logout-user/",
            'Logout All Sessions': "/api/logout-all/",
        },
        'Cart Management': {
            'View Cart': "/api/viewcart/",
            'Add to Cart': "/api/addtocart/",
            'Delete Cart Item': "/api/deletecartitem/",
            'Update Cart': "/api/updatecart/",
            'Purchase Cart': "/api/purchasecart/",
        },
        'Orders': {
            'Show User Orders': "/api/showuserorders/",
            'Place Order': "/api/place-order",
            'Order Details': "/api/order-details",
            'Update Order Status': "/api/update-order-status/"
        },
        'Products': {
            'List Products': "/api/products/",
            'Get Product by ID': "/api/products/<int:pk>",
        },
        'Restaurants': {
            'Get Restaurant by ID': "/api/restaurants/<int:id>/",
            'Nearby Restaurants': "/api/nearby-restaurants/",
            'Restaurant Locations': "/api/restaurant-locations/",
        },
        'Deliveryman': {'Set Waiting For Delivery': "/api/set-waiting-for-delivery/",
                        "Deliveryman Accept Order": "/api/deliveryman-accept-order/"}
    }
    return render(request, 'api/api_overview.html', {'api_urls': api_urls})


class register_user(generics.GenericAPIView):
    serializer_class = RegisterSerializer
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # find phone from possible profile places
        phone = None
        # merchant_profile.phone_number
        try:
            phone = getattr(user, "merchant_profile", None) and getattr(
                user.merchant_profile, "phone_number", None)
        except Exception:
            phone = None
        # fallback to customer profile phone or phone_number
        if not phone:
            try:
                profile = getattr(user, "user_profile", None)
                if profile:
                    phone = getattr(profile, "phone", None) or getattr(
                        profile, "phone_number", None)
            except Exception:
                phone = None

        return Response({
            'user': AppUserSerializer(user, context=self.get_serializer_context()).data,
            'phone': phone or ''
        })


class login_user(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = EmailAuthTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user)

        refresh = RefreshToken.for_user(user)

        response = Response({
            'access': str(refresh.access_token),
            'email': user.email,
            'full_name': user.first_name
        })

        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            httponly=True,
            secure=False,
            samesite='Lax'
        )

        return response


# -----------------------------
# ✅ NEW APPENDED VIEWS BELOW
# -----------------------------

class login_user_knox(KnoxLoginView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = [TokenAuthentication]

    def post(self, request, format=None):
        serializer = EmailAuthTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user)

        response = super(login_user_knox, self).post(request, format=None)
        token_data = response.data

        token_data['email'] = user.email
        token_data['full_name'] = user.first_name

        return Response(token_data)


class ShopPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'per_page'


@api_view(['GET'])
@permission_classes([AllowAny])
def get_restaurant_list(request):
    query = Restaurant.objects.filter(approved=True)

    page_number = request.query_params.get('page', 1)
    per_page = request.query_params.get('per_page', 18)

    try:
        page_number = int(page_number)
        per_page = int(per_page)
    except ValueError:
        return Response({'error': 'Invalid pagination parameters'}, status=400)

    pag = Paginator(query, per_page)
    pagobj = pag.get_page(page_number)

    serializer = Restaurantlistserial(pagobj, many=True)
    response = Response(serializer.data)
    response['X-Total-Count'] = pag.count
    return response


class ShopPagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = 'per_page'


@api_view(['GET'])
@permission_classes([AllowAny])
def product_list_view(request):
    queryset = FoodItem.objects.all()

    # Get query parameters
    category = request.query_params.get('category')
    res_type = request.query_params.get('res_category')
    min_price = request.query_params.get('min_price')
    max_price = request.query_params.get('max_price')

    if category and category.lower() != "all":
        queryset = queryset.filter(veg_nonveg__iexact=category)

    if res_type and res_type.lower() != "all":
        queryset = queryset.filter(
            restaurant__restaurant_type__iexact=res_type)

    if min_price:
        try:
            queryset = queryset.filter(price__gte=float(min_price))
        except ValueError:
            return Response({'error': 'min_price must be a number'}, status=status.HTTP_400_BAD_REQUEST)

    if max_price:
        try:
            queryset = queryset.filter(price__lte=float(max_price))
        except ValueError:
            return Response({'error': 'max_price must be a number'}, status=status.HTTP_400_BAD_REQUEST)

    page_number = request.query_params.get('_page', 1)
    per_page = request.query_params.get('_per_page', 6)
    try:
        page_number = int(page_number)
        per_page = int(per_page)
    except ValueError:
        return Response({'error': 'Pagination parameters must be integers'}, status=status.HTTP_400_BAD_REQUEST)
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page_number)
    serializer = FooditemSerial(page_obj, many=True)
    response = Response(serializer.data)
    response['X-Total-Count'] = paginator.count
    return response


class ShopPagination(PageNumberPagination):
    page_size = 5  # Changed from 6 to 5
    page_size_query_param = 'per_page'


class ShopPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'per_page'


@api_view(['GET'])
def get_most_ordered_food(request):
    # Get only food items that have been ordered, annotate them with order count
    most_ordered_foods = FoodItem.objects.filter(
        order_countno_of_ordersgt=0
    ).annotate(
        no_of_orders=F('order_count__no_of_orders')
    ).order_by('-no_of_orders')

    # Apply pagination (optional: comment out if not needed)
    paginator = ShopPagination()
    paginated_data = paginator.paginate_queryset(most_ordered_foods, request)

    # Serialize and return only the results array
    serializer = FooditemSerial(paginated_data, many=True)
    return Response(serializer.data, status=200)


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def addtocart(request):
#     user = request.user
#     food_id = request.data.get('food_id')
#     restaurant_id = request.data.get('restaurant_id')
#     quantity = request.data.get('quantity')

#     if not all([food_id, restaurant_id, quantity]):
#         return Response(
#             {"message": "food_id, restaurant_id, and quantity are required."},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     try:
#         quantity = int(quantity)
#     except ValueError:
#         return Response({"message": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

#     try:
#         food = FoodItem.objects.get(id=food_id)
#         restaurant = Restaurant.objects.get(id=restaurant_id)
#     except (FoodItem.DoesNotExist, Restaurant.DoesNotExist):
#         return Response({"message": "Invalid food or restaurant ID."}, status=status.HTTP_404_NOT_FOUND)

#     total_price = food.price * quantity
#     if total_price < 300:
#         return Response({"message": "Minimum order amount is 300."}, status=status.HTTP_400_BAD_REQUEST)

#     order_data = {
#         "user": user.id,
#         "food_item": food.id,
#         "restaurant": restaurant.id,
#         "quantity": quantity,
#         "total_price": total_price
#     }

#     serializer = Orderserializer(data=order_data)
#     if serializer.is_valid():
#         serializer.save()
#         return Response(
#             {'message': 'Order placed successfully.', 'order': serializer.data},
#             status=status.HTTP_201_CREATED
#         )
#     else:
#         return Response(
#             {'message': 'Error, invalid data.', 'errors': serializer.errors},
#             status=status.HTTP_400_BAD_REQUEST
#         )
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def addtocart(request):
    user = request.user
    food_id = request.data.get('food_id')
    restaurant_id = request.data.get('restaurant_id')
    quantity = request.data.get('quantity')

    if not all([food_id, restaurant_id, quantity]):
        return Response(
            {"message": "food_id, restaurant_id, and quantity are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        quantity = int(quantity)
    except ValueError:
        return Response({"message": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        food = FoodItem.objects.get(id=food_id)
        restaurant = Restaurant.objects.get(id=restaurant_id)
    except (FoodItem.DoesNotExist, Restaurant.DoesNotExist):
        return Response({"message": "Invalid food or restaurant ID."}, status=status.HTTP_404_NOT_FOUND)

    total_price = food.price * quantity

    cart_data = {
        "user": user.id,
        "food_item": food.id,
        "restaurant": restaurant.id,
        "quantity": quantity,
        "total_price": total_price
    }

    serializer = CartSerializer(data=cart_data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {'message': 'Item added to cart successfully.', 'cart': serializer.data},
            status=status.HTTP_201_CREATED
        )
    else:
        return Response(
            {'message': 'Error, invalid data.', 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_cart(request):
    user = request.user
    cart_items = Cart.objects.filter(user=user)
    serializer = CartReadSerializer(cart_items, many=True)

    return Response({
        "cart": serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_cart(request):
    user = request.user
    cart_items = Order.objects.filter(user=user, is_transited=False)

    if not cart_items.exists():
        return Response({"message": "Your cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

    cart_items.update(is_transited=True)

    serializer = Orderserializer(cart_items, many=True)
    return Response({
        "message": "Purchase successful.",
        "purchased_items": serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def show_user_order_history(request):
    user = request.user
    orders = Order.objects.filter(user=user, is_transited=True)

    if not orders.exists():
        return Response({'message': 'No orders found for this user.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = Orderserializer(orders, many=True)

    return Response({
        "order_history": serializer.data,
    }, status=status.HTTP_200_OK)


# @api_view(['DELETE'])
# @permission_classes([IsAuthenticated])
# def delete_cart(request):
#     user = request.user
#     order_id = request.data.get('order_id')
#     try:
#         order = Order.objects.get(id=order_id, user=user, is_transited=False)
#     except Order.DoesNotExist:
#         return Response({'message': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

#     order.delete()
#     return Response({'message': 'Order deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_cart(request):
    """Delete a cart item using cart_id from request body"""
    user = request.user
    cart_id = request.data.get('cart_id')

    if not cart_id:
        return Response(
            {'message': 'cart_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        cart_item = Cart.objects.get(cart_id=cart_id, user=user)
    except Cart.DoesNotExist:
        return Response(
            {'message': 'Cart item not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    cart_item.delete()
    return Response(
        {'message': 'Cart item deleted successfully.'},
        status=status.HTTP_204_NO_CONTENT
    )


# @api_view(['PUT'])
# @permission_classes([IsAuthenticated])
# def update_cart(request):
#     user = request.user
#     food_id = request.data.get('food_id')
#     restaurant_id = request.data.get('restaurant_id')
#     quantity = request.data.get('quantity')

#     if not all([food_id, restaurant_id, quantity]):
#         return Response(
#             {"message": "food_id, restaurant_id, and quantity are required."},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     try:
#         quantity = int(quantity)
#     except ValueError:
#         return Response({"message": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

#     try:
#         food = FoodItem.objects.get(id=food_id)
#         restaurant = Restaurant.objects.get(id=restaurant_id)
#     except (FoodItem.DoesNotExist, Restaurant.DoesNotExist):
#         return Response({"message": "Invalid food or restaurant ID."}, status=status.HTTP_404_NOT_FOUND)

#     # Delete the previous order if it exists
#     Order.objects.filter(user=user, food_item=food,
#                          restaurant=restaurant).delete()

#     # Recalculate total price
#     total_price = food.price * quantity
#     if total_price < 300:
#         return Response({"message": "Minimum order amount is 300."}, status=status.HTTP_400_BAD_REQUEST)

#     order_data = {
#         "user": user.id,
#         "food_item": food.id,
#         "restaurant": restaurant.id,
#         "quantity": quantity,
#         "total_price": total_price
#     }

#     serializer = Orderserializer(data=order_data)
#     if serializer.is_valid():
#         serializer.save()
#         return Response(
#             {'message': 'Order updated successfully.', 'order': serializer.data},
#             status=status.HTTP_200_OK
#         )
#     else:
#         return Response(
#             {'message': 'Error, invalid data.', 'errors': serializer.errors},
#             status=status.HTTP_400_BAD_REQUEST
#         )

# @api_view(['PUT'])
# @permission_classes([IsAuthenticated])
# def update_cart(request):
#     user = request.user
#     order_id = request.data.get('order_id')
#     quantity = request.data.get('quantity')

#     if not all([order_id, quantity]):
#         return Response(
#             {"message": "order_id and quantity are required."},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     try:
#         quantity = int(quantity)
#         if quantity < 1:
#             raise ValueError
#     except ValueError:
#         return Response({"message": "Quantity must be a positive integer."},
#                         status=status.HTTP_400_BAD_REQUEST)

#     try:
#         order = Order.objects.get(id=order_id, user=user, is_transited=False)
#     except Order.DoesNotExist:
#         return Response({"message": "Cart item not found."},
#                         status=status.HTTP_404_NOT_FOUND)

#     order.quantity = quantity
#     order.total_price = order.food_item.price * quantity

#     if order.total_price < 300:
#         return Response({"message": "Minimum order amount is 300."},
#                         status=status.HTTP_400_BAD_REQUEST)

#     order.save()
#     serializer = Orderserializer(order)
#     return Response({'message': 'Cart updated successfully.', 'order': serializer.data},
#                     status=status.HTTP_200_OK)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_cart(request):
    user = request.user
    cart_id = request.data.get('cart_id')  # renamed for clarity
    quantity = request.data.get('quantity')

    if not all([cart_id, quantity]):
        return Response(
            {"message": "cart_id and quantity are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        quantity = int(quantity)
        if quantity < 1:
            raise ValueError
    except ValueError:
        return Response({"message": "Quantity must be a positive integer."},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        cart_item = Cart.objects.get(cart_id=cart_id, user=user)
    except Cart.DoesNotExist:
        return Response({"message": "Cart item not found."},
                        status=status.HTTP_404_NOT_FOUND)

    cart_item.quantity = quantity
    cart_item.save()
    serializer = CartSerializer(cart_item)
    return Response({'message': 'Cart updated successfully.', 'cart': serializer.data},
                    status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_cart_status(request):
    user = request.user
    cart_id = request.data.get('cart_id')     # example: 10
    checked = request.data.get('checked')     # example: true / false

    # Validate inputs
    if cart_id is None or checked is None:
        return Response(
            {"message": "cart_id and checked are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Ensure 'checked' is boolean
    if isinstance(checked, str):
        if checked.lower() == 'true':
            checked = True
        elif checked.lower() == 'false':
            checked = False
        else:
            return Response(
                {"message": "checked must be true or false."},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Get the cart item for this user
    try:
        cart_item = Cart.objects.get(cart_id=cart_id, user=user)
    except Cart.DoesNotExist:
        return Response(
            {"message": "Cart not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    # ✅ Set checked field exactly as frontend sends
    cart_item.checked = checked
    cart_item.save()

    serializer = CartSerializer(cart_item)

    return Response(
        {
            'message': f'Cart status updated to {checked}.',
            'order': serializer.data
        },
        status=status.HTTP_200_OK
    )
    # user = request.user
    # cart_id = request.data.get('cart_id')
    # checked = request.data.get('checked')  # expecting True/False from frontend

    # if not all([cart_id, checked is not None]):
    #     return Response(
    #         {"message": "cart_id and status are required."},
    #         status=status.HTTP_400_BAD_REQUEST
    #     )

    # # Validate status value (must be boolean-like)
    # if str(checked).lower() not in ['true', 'false']:
    #     return Response(
    #         {"message": "Status must be true or false."},
    #         status=status.HTTP_400_BAD_REQUEST
    #     )

    # try:
    #     cart_item = Cart.objects.get(cart_id=cart_id, user=user)
    # except Cart.DoesNotExist:
    #     return Response({"message": "cart not found."},
    #                     status=status.HTTP_404_NOT_FOUND)

    # cart_item.checked = checked
    # cart_item.save()

    # serializer = CartSerializer(cart_item)

    # return Response(
    #     {'message': 'Cart status updated successfully.', 'order': serializer.data},
    #     status=status.HTTP_200_OK
    # )

    # user = request.user
    # cart_id = request.data.get('cart_id')  # expect a list like [1, 2, 3]
    # checked = request.data.get('checked')    # true/false from frontend
    # print(cart_id, checked)
    # if not cart_id or checked is None:
    #     return Response(
    #         {"message": "cart_id (list) and checked are required."},
    #         status=status.HTTP_400_BAD_REQUEST
    #     )

    # # Validate input
    # if not isinstance(cart_id, list):
    #     return Response(
    #         {"message": "cart_ids must be a list."},
    #         status=status.HTTP_400_BAD_REQUEST
    #     )

    # if str(checked).lower() not in ['true', 'false']:
    #     return Response(
    #         {"message": "checked must be true or false."},
    #         status=status.HTTP_400_BAD_REQUEST
    #     )

    # # Get all matching cart items
    # cart_items = Cart.objects.filter(cart_id__in=cart_id, user=user)
    # if not cart_items.exists():
    #     return Response(
    #         {"message": "No matching cart items found."},
    #         status=status.HTTP_404_NOT_FOUND
    #     )

    # # Update all statuses
    # new_status = str(checked).lower() == 'true'
    # cart_items.update(checked=new_status)

    # serializer = CartSerializer(cart_items, many=True)

    # return Response(
    #     {
    #         'message': f'Status updated for {cart_items.count()} cart item(s).',
    #         'cart': serializer.data
    #     },
    #     status=status.HTTP_200_OK
    # )


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_all_status(request):
    user = request.user
    cart_ids = request.data.get('cart_ids')  # list of IDs
    checked = request.data.get('checked')    # true/false

    if not cart_ids or checked is None:
        return Response({"message": "cart_ids and checked are required."}, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(checked, str):
        checked = checked.lower() == 'true'

    cart_items = Cart.objects.filter(cart_id__in=cart_ids, user=user)
    if not cart_items.exists():
        return Response({"message": "No cart items found."}, status=status.HTTP_404_NOT_FOUND)

    cart_items.update(checked=checked)
    serializer = CartSerializer(cart_items, many=True)

    return Response({
        "message": f"Checked status updated for {cart_items.count()} items.",
        "cart": serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_restaurant_by_id(request, id):
    try:
        restaurant = Restaurant.objects.get(id=id)
        serializer = RestaurantSerial(restaurant)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Restaurant.DoesNotExist:
        return Response(
            {"error": "Restaurant not found"},
            status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order_api(request):
    try:
        user = request.user
    except Exception:
        return Response({"detail": "Authenticated user not found."}, status=status.HTTP_400_BAD_REQUEST)

    cart_ids = request.data.get('cart_ids')
    payment_method = request.data.get('payment_method')
    latitude = request.data.get('latitude')
    longitude = request.data.get('longitude')
    delivery_charge = request.data.get('delivery_charge', 0)
    customer_location = request.data.get('customer_location')  # <--- NEW FIELD
    restaurant_id = None
    if not cart_ids or not isinstance(cart_ids, list):
        return Response({"detail": "cart_ids must be provided as a list."}, status=status.HTTP_400_BAD_REQUEST)

    if payment_method is None or latitude is None or longitude is None or not customer_location:
        return Response({"detail": "payment_method, latitude, longitude, and customer_location are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        lat_dec = Decimal(str(latitude))
        lon_dec = Decimal(str(longitude))
    except (InvalidOperation, TypeError, ValueError):
        return Response({"detail": "latitude and longitude must be numeric."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        del_charge_dec = Decimal(
            str(delivery_charge)) if delivery_charge is not None else Decimal('0.00')
    except (InvalidOperation, TypeError, ValueError):
        return Response({"detail": "delivery_charge must be numeric."}, status=status.HTTP_400_BAD_REQUEST)

    cart_items = Cart.objects.filter(
        cart_id__in=cart_ids, user=user).select_related('food_item', 'restaurant')

    if not cart_items.exists():
        return Response({"detail": "No valid cart items found."}, status=status.HTTP_400_BAD_REQUEST)

    created_orders = []
    restaurant_orders = {}
    errors = []

    for cart in cart_items:
        try:
            restaurant = cart.restaurant
            restaurant_id = restaurant.id
            if restaurant.id not in restaurant_orders:
                order = Order.objects.create(
                    user=user,
                    restaurant=restaurant,
                    order_date=timezone.now(),
                    payment_method=payment_method,
                    latitude=lat_dec,
                    longitude=lon_dec,
                    delivery_charge=del_charge_dec,
                    customer_location=customer_location  # <--- SAVE THE FIELD
                )
                restaurant_orders[restaurant.id] = order
                created_orders.append(order)
            else:
                order = restaurant_orders[restaurant.id]

            OrderItem.objects.create(
                order=order,
                food_item=cart.food_item,
                quantity=cart.quantity,
                price_at_order=cart.food_item.price or Decimal('0.00')
            )
            order.update_total_price()
            order.total_price = (order.total_price or Decimal(
                '0.00')) + (order.delivery_charge or Decimal('0.00'))
            order.save(update_fields=['total_price'])

        except Exception as exc:
            errors.append({"cart_id": cart.cart_id, "error": str(exc)})

    cart_items.delete()

    if not created_orders:
        return Response({"detail": "No orders could be placed.", "errors": errors}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    serializer = PlaceOrderSerializer(
        created_orders, many=True, context={'request': request})
    serialized = serializer.data
    order_id = None
    for item in serialized:
        order_id = item["id"]
    for idx, order in enumerate(created_orders):
        try:
            if isinstance(serialized[idx], dict):
                serialized[idx]['delivery_charge'] = str(
                    order.delivery_charge if order.delivery_charge is not None else "0.00")
                serialized[idx]['total_price'] = str(
                    order.total_price if order.total_price is not None else "0.00")
                # <--- INCLUDE IN RESPONSE
                serialized[idx]['customer_location'] = order.customer_location
        except Exception:
            pass

    db_saved = [
        {
            "order_pk": order.pk,
            "restaurant": getattr(order.restaurant, "id", None),
            "total_price": str(order.total_price if order.total_price is not None else "0.00"),
            "delivery_charge": str(order.delivery_charge if order.delivery_charge is not None else "0.00"),
            "status": order.status,
            "payment_method": getattr(order, "payment_method", None),
            "latitude": str(getattr(order, "latitude", None)),
            "longitude": str(getattr(order, "longitude", None)),
            "customer_location": order.customer_location,  # <--- SAVE TO DB LOG
        }
        for order in created_orders
    ]

    try:
        channel_layer = get_channel_layer()
        payload = {"type": "join_order_group", "order_id": order_id,
                   "order": serialized, "db_saved": db_saved, "errors": errors}
        async_to_sync(channel_layer.group_send)(
            f"restaurant_{restaurant_id}", payload)
    except Exception as exc:
        errors.append({"channel_error": str(exc)})

    return Response(
        {
            "message": "Order(s) placed successfully." if created_orders else "Order placement failed.",
            "orders": serialized,
            "errors": errors
        },
        status=status.HTTP_201_CREATED if created_orders else status.HTTP_500_INTERNAL_SERVER_ERROR
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_order_status_api(request):
    user = request.user

    order_id = request.data.get('order_id')
    new_status = request.data.get('status')

    if not order_id or not new_status:
        return Response(
            {"detail": "Both 'order_id' and 'status' are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return Response(
            {"detail": f"Order with id {order_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND
        )

    if new_status not in dict(Order.STATUS_CHOICES):
        return Response(
            {"detail": f"Invalid status '{new_status}'. Must be one of: {[s[0] for s in Order.STATUS_CHOICES]}."},
            status=status.HTTP_400_BAD_REQUEST
        )

    order.status = new_status
    order.save(update_fields=['status'])

    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            f"order_{order_id}",
            {
                "type": "order_status_change",
                "payload": {
                    "order_id": order_id,
                    "new_status": new_status
                }
            })
    except:
        pass

    return Response(
        {"detail": f"Order #{order_id} status updated to '{new_status}'."},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_product_by_id(request, pk):
    try:
        product = FoodItem.objects.get(pk=pk)
        serializer = FooditemSerial(product)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except FoodItem.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * \
        math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


@api_view(['GET'])
@permission_classes([AllowAny])
def get_nearby_restaurants(request):
    try:
        user_lat = float(request.GET.get('latitude'))
        user_lon = float(request.GET.get('longitude'))
    except (TypeError, ValueError):
        return Response({"error": "Please provide valid 'latitude' and 'longitude' as query params."}, status=400)

    restaurants = Restaurant.objects.all()

    distances = []
    for restaurant in restaurants:
        distance = haversine_distance(
            user_lat, user_lon, restaurant.latitude, restaurant.longitude)
        distances.append((distance, restaurant))

    # Sort and select top 4 nearby
    distances.sort(key=lambda x: x[0])
    nearest_restaurants = [r for _, r in distances[:4]]

    serializer = RestaurantSerial(nearest_restaurants, many=True)
    return Response(serializer.data)


def calculate_distance(lat1, lon1, lat2, lon2):
    # Radius of Earth in kilometers (use 3956 for miles)
    R = 6371.0

    # Convert degrees to radians
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)

    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c  # in kilometers
    return distance


@api_view(['GET'])
@permission_classes([AllowAny])
def restaurant_locations(request):
    restaurant_id = request.query_params.get('id')
    user_longitude = request.query_params.get('user_longitude')
    user_latitude = request.query_params.get('user_latitude')

    if not restaurant_id:
        return Response({'error': 'restaurant ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    if not user_latitude or not user_longitude:
        return Response({'error': 'User latitude and longitude are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Parse user lat/lon safely
        user_lat = float(user_latitude)
        user_lon = float(user_longitude)

        restaurant = Restaurant.objects.get(id=restaurant_id)
        distance = calculate_distance(
            user_lat, user_lon, restaurant.latitude, restaurant.longitude)

        return Response({
            'id': restaurant.id,
            'restaurant_name': restaurant.restaurant_name,
            'latitude': restaurant.latitude,
            'longitude': restaurant.longitude,
            'user_latitude': user_lat,
            'user_longitude': user_lon,
            'distance': round(distance, 2),
        }, status=status.HTTP_200_OK)

    except ValueError:
        return Response({'error': 'Latitude and longitude must be valid numbers'}, status=status.HTTP_400_BAD_REQUEST)

    except Restaurant.DoesNotExist:
        return Response({'error': 'Restaurant not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


EXCLUDED_STATUSES = ['DELIVERED', 'CANCELLED']


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_details_api(request):
    user = request.user
    view = request.query_params.get('view', None)

    if view == "history":
        queryset = (
            OrderHistory.objects
            .filter(user=user)
            .select_related('restaurant', 'deliveryman')
            .prefetch_related(
                Prefetch('order_items_history',
                         queryset=OrderItemHistory.objects.select_related('food_item'))
            )
            .order_by('-order_date')
        )
        data = []
        for oh in queryset:
            order_items_data = []
            for item in oh.order_items_history.all():
                fi = getattr(item, 'food_item', None)
                image_url = None
                if fi:
                    if getattr(fi, 'profile_picture', None):
                        image_url = fi.profile_picture.url if getattr(
                            fi.profile_picture, 'url', None) else None
                    elif getattr(fi, 'external_image_url', None):
                        image_url = fi.external_image_url
                order_items_data.append({
                    "id": getattr(item, 'id', None),
                    "name": getattr(fi, 'name', 'N/A') if fi else 'N/A',
                    "quantity": getattr(item, 'quantity', 0),
                    "price_at_order": str(getattr(item, 'price_at_order', Decimal('0.00'))),
                    "image": image_url,
                })

            order_data = {
                "order_id": getattr(oh, 'original_order', oh.id),
                "status": getattr(oh, 'status', ''),
                "total_price": str(getattr(oh, 'total_price', Decimal('0.00'))),
                "delivery_charge": str(getattr(oh, 'delivery_charge', Decimal('0.00'))),
                "payment_method": getattr(oh, 'payment_method', None),
                "order_date": getattr(oh, 'order_date', None).isoformat() if getattr(oh, 'order_date', None) else None,
                "delivery_location": getattr(oh, 'customer_location', None),
                "restaurant": RestaurantDetailSerializer(getattr(oh, 'restaurant', None), context={'request': request}).data if getattr(oh, 'restaurant', None) else None,
                "deliveryman": DeliverymanSerializer(getattr(oh, 'deliveryman', None), context={'request': request}).data if getattr(oh, 'deliveryman', None) else None,
                "order_items": order_items_data,
                "latitude": getattr(oh, 'latitude', None),
                "longitude": getattr(oh, 'longitude', None),
                "delivered_time": getattr(oh, 'created_at', None).isoformat() if getattr(oh, 'created_at', None) else None
            }
            data.append(order_data)

        return Response({"orders": data}, status=status.HTTP_200_OK)

    queryset = (
        Order.objects
        .filter(user=user)
        .exclude(status__in=EXCLUDED_STATUSES)
        .select_related('restaurant', 'deliveryman')
        .prefetch_related(Prefetch('order_items', queryset=OrderItem.objects.select_related('food_item')))
        .order_by('-order_date')
    )

    if view and view.upper() in ["PENDING", "PROCESSING", "WAITING_FOR_DELIVERY", "OUT_FOR_DELIVERY"]:
        queryset = queryset.filter(status=view.upper())

    serializer = OrderWithItemsSerializer(
        queryset, many=True, context={'request': request})
    return Response({"orders": serializer.data}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_order_waiting_for_delivery_api(request):
    Order = apps.get_model("merchant", "Order")
    Deliveryman = apps.get_model("merchant", "Deliveryman")
    DeliverymanStatus = apps.get_model("merchant", "DeliverymanStatus")
    OrderItem = apps.get_model("merchant", "OrderItem")

    order_id = request.data.get("order_id")
    if not order_id:
        return Response({"detail": "order_id is required."}, status=400)

    try:
        order_id = int(order_id)
    except:
        return Response({"detail": "order_id must be numeric."}, status=400)

    try:
        order = Order.objects.select_related(
            "restaurant", "user").get(pk=order_id)
    except Order.DoesNotExist:
        return Response({"detail": f"Order with id {order_id} does not exist."}, status=404)

    if order.status == "WAITING_FOR_DELIVERY":
        return Response({"detail": "Order is already WAITING_FOR_DELIVERY."}, status=400)

    restaurant = order.restaurant

    try:
        order.status = "WAITING_FOR_DELIVERY"
        order.save(update_fields=["status"])
    except Exception:
        return Response({"detail": "Failed to update order status."}, status=500)

    # Check if a deliveryman is already assigned to this restaurant
    assigned_deliveryman = None
    try:
        existing_order = (
            Order.objects
            .select_related("deliveryman")
            .filter(
                restaurant=restaurant,
                assigned=True,
                deliveryman__isnull=False
            )
            .first()
        )
        if existing_order:
            assigned_deliveryman = existing_order.deliveryman
    except Exception:
        assigned_deliveryman = None

    # Build detailed payload
    def build_payload(order, assigned_deliveryman=None):
        restaurant_obj = order.restaurant
        user_obj = order.user
        dm_status = None
        if assigned_deliveryman:
            dm_status = DeliverymanStatus.objects.filter(
                deliveryman=assigned_deliveryman).first()

        # Build order items
        # order_items_list = []
        # for oi in order.order_items.select_related("food_item").all():
        #     fi = getattr(oi, "food_item", None)
        #     order_items_list.append({
        #         "id": oi.pk,
        #         "food_item": getattr(fi, "pk", None),
        #         "food_item_name": getattr(fi, "name", "") if fi else "",
        #         "restaurant_name": getattr(restaurant_obj, "restaurant_name", ""),
        #         "food_item_image": getattr(fi, "image", None) if fi else None,
        #         "quantity": oi.quantity,
        #         "price_at_order": str(oi.price_at_order) if oi.price_at_order is not None else None,
        #         "total_price": str(order.total_price) if order.total_price is not None else None,
        #     })

        order_items_list = []
        for oi in order.order_items.select_related("food_item").all():
            fi = getattr(oi, "food_item", None)
            price_at_order = str(
                oi.price_at_order) if oi.price_at_order is not None else "0.00"
            total_price = str((oi.price_at_order or 0) * oi.quantity)

            order_items_list.append({
                "id": oi.pk,
                "food_item": getattr(fi, "pk", None),
                "food_item_name": getattr(fi, "name", "") if fi else "",
                "restaurant_name": getattr(restaurant_obj, "restaurant_name", ""),
                "food_item_image": getattr(fi, "image", None) if fi else None,
                "quantity": oi.quantity,
                "price_at_order": price_at_order,
                "total_price": total_price,
            })

        return {
            "assigned_to_me": bool(assigned_deliveryman),
            "assigned_restaurant": getattr(restaurant_obj, "restaurant_name", ""),
            "orders": [
                {
                    "order_assigned": bool(assigned_deliveryman),
                    "order_id": order.pk,
                    "user": {
                        "id": getattr(user_obj, "pk", None),
                        "username": getattr(user_obj, "username", ""),
                        "first_name": getattr(user_obj, "first_name", ""),
                        "email": getattr(user_obj, "email", ""),
                    },
                    "restaurant_id": getattr(restaurant_obj, "pk", None),
                    "restaurant": {
                        "id": getattr(restaurant_obj, "pk", None),
                        "user": {
                            "id": getattr(restaurant_obj.user, "pk", None) if hasattr(restaurant_obj, "user") else None,
                            "username": getattr(restaurant_obj.user, "username", "") if hasattr(restaurant_obj, "user") else "",
                            "first_name": getattr(restaurant_obj.user, "first_name", "") if hasattr(restaurant_obj, "user") else "",
                            "last_name": getattr(restaurant_obj.user, "last_name", "") if hasattr(restaurant_obj, "user") else "",
                            "email": getattr(restaurant_obj.user, "email", "") if hasattr(restaurant_obj, "user") else "",
                        },
                        "restaurant_name": getattr(restaurant_obj, "restaurant_name", ""),
                        "owner_name": getattr(restaurant_obj, "owner_name", ""),
                        "owner_contact": getattr(restaurant_obj, "owner_contact", ""),
                        "restaurant_address": getattr(restaurant_obj, "restaurant_address", ""),
                        "latitude": getattr(restaurant_obj, "latitude", None),
                        "longitude": getattr(restaurant_obj, "longitude", None),
                        "cuisine": getattr(restaurant_obj, "cuisine", ""),
                        "description": getattr(restaurant_obj, "description", ""),
                        "restaurant_type": getattr(restaurant_obj, "restaurant_type", ""),
                        "profile_picture": order.restaurant.profile_picture.url if getattr(order.restaurant, "profile_picture", None) and order.restaurant.profile_picture else None,
                        "cover_photo": order.restaurant.cover_photo.url if getattr(order.restaurant, "cover_photo", None) and order.restaurant.cover_photo else None,
                    },
                    "is_transited": False,
                    "delivery_charge": str(order.delivery_charge) if order.delivery_charge is not None else "0.00",
                    "total_price": str(order.total_price) if order.total_price is not None else "0.00",
                    "order_items": order_items_list,
                    "order_date": getattr(order, "created_at", timezone.now()).isoformat(),
                    "status": order.status,
                    "payment_method": getattr(order, "payment_method", "cashondelivery"),
                    "latitude": getattr(order, "latitude", None),
                    "longitude": getattr(order, "longitude", None),
                    "customer_details": {
                        "email": getattr(user_obj, "email", None),
                        "phone": getattr(user_obj, "phone", None),
                    },
                    "customer_location": getattr(order, "delivery_address", None)
                }
            ],
            "returned_at": timezone.now().isoformat()
        }

    payload = build_payload(order, assigned_deliveryman)

    dm_status = None
    if assigned_deliveryman:
        try:
            dm_status = DeliverymanStatus.objects.filter(
                deliveryman=assigned_deliveryman).first()
        except:
            dm_status = None

    deliveryman_data = None
    if assigned_deliveryman:
        dm_user = getattr(assigned_deliveryman, "user", None)
        dm_phone = None
        if dm_user:
            if hasattr(dm_user, "user_profile"):
                dm_phone = getattr(dm_user.user_profile, "phone_number", None)
            if not dm_phone and hasattr(dm_user, "merchant_profile"):
                dm_phone = getattr(dm_user.merchant_profile,
                                   "phone_number", None)
        status_obj = getattr(assigned_deliveryman, 'status', None)
        deliveryman_data = {
            "id": getattr(assigned_deliveryman, "pk", None),
            "name": f"{getattr(assigned_deliveryman, 'Firstname', '') or ''} {getattr(assigned_deliveryman, 'Lastname', '') or ''}".strip(),
            "email": getattr(dm_user, "email", None) if dm_user else None,
            "phone": dm_phone,
            "vehicle": getattr(assigned_deliveryman, "Vehicle", None),
            "active_flag": getattr(status_obj, 'online', False) if status_obj is not None else False
        }

    channel_layer = get_channel_layer()

    # CASE A = Restaurant already has a deliveryman assigned
    if assigned_deliveryman:
        try:
            dm_status = DeliverymanStatus.objects.filter(
                deliveryman=assigned_deliveryman).first()
        except Exception:
            dm_status = None

        # CASE A1 = Deliveryman idle = Assign the order
        if dm_status and not dm_status.on_delivery:
            try:
                order.deliveryman = assigned_deliveryman
                order.assigned = True
                order.save(update_fields=["deliveryman", "assigned"])
            except:
                return Response({"detail": "Could not assign order."}, status=500)

            try:
                async_to_sync(channel_layer.group_send)(
                    f"deliveryman_{assigned_deliveryman.pk}",
                    {
                        "type": "direct_order_assignment",
                        "payload": payload,
                        "order_id": order_id
                    }
                )
                async_to_sync(channel_layer.group_send)(
                    f"order_{order_id}",
                    {
                        "type": "order_status_change",
                        "payload": {
                            "order_id": order_id,
                            "new_status": "WAITING_FOR_DELIVERY",
                            "deliveryman": deliveryman_data
                        }
                    }
                )
            except:
                pass

            return Response(payload, status=200)

        # CASE A2 = Deliveryman is busy = broadcast
        try:
            async_to_sync(channel_layer.group_send)(
                "deliverymen",
                {
                    "type": "new_order_available",
                    "payload": payload,
                }
            )
            async_to_sync(channel_layer.group_send)(
                f"order_{order_id}",
                {
                    "type": "order_status_change",
                    "payload": {
                            "order_id": order_id,
                            "new_status": "WAITING_FOR_DELIVERY",
                    }
                }
            )
        except:
            pass

        return Response(payload, status=200)

    # CASE B → No deliveryman found → broadcast
    try:
        async_to_sync(channel_layer.group_send)(
            "deliverymen",
            {
                "type": "new_order_available",
                "payload": payload,
            }
        )
        async_to_sync(channel_layer.group_send)(
            f"order_{order_id}",
            {
                "type": "order_status_change",
                        "payload": {
                            "order_id": order_id,
                            "new_status": "WAITING_FOR_DELIVERY",
                        }
            }
        )
    except:
        pass

    return Response(payload, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deliveryman_accept_order_api(request):
    Deliveryman = apps.get_model("merchant", "Deliveryman")
    Order = apps.get_model("merchant", "Order")
    deliveryman = getattr(request.user, 'deliveryman_profile', None)
    if not deliveryman:
        return Response({"detail": "User is not a deliveryman."}, status=400)

    order_id = request.data.get("order_id")
    if not order_id:
        return Response({"detail": "order_id is required."}, status=400)

    dm_status = getattr(deliveryman, "status", None)
    if dm_status and dm_status.on_delivery:
        return Response({"detail": "You are already on a delivery."}, status=400)

    try:
        order_id = int(order_id)
    except:
        return Response({"detail": "order_id must be an integer."}, status=400)

    try:
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update()
                .select_related("deliveryman")
                .get(pk=order_id)
            )

            assigned_dm = getattr(order, "deliveryman", None)
            if assigned_dm and assigned_dm.pk != deliveryman.pk:
                return Response({"detail": "Order already assigned to another deliveryman."}, status=400)

            order.deliveryman = deliveryman
            order.assigned = True
            order.save(update_fields=["deliveryman", "assigned"])

            # DeliverymanStatus = apps.get_model("merchant", "DeliverymanStatus")
            # dm_status, _ = DeliverymanStatus.objects.get_or_create(
            #     deliveryman=deliveryman)
            # dm_status.on_delivery = True
            # dm_status.save(update_fields=["on_delivery"])

        # additionally assign other waiting orders from same restaurant
        additionally_assigned_ids = []
        with transaction.atomic():
            candidate_qs = Order.objects.select_for_update().filter(
                restaurant=order.restaurant,
                status='WAITING_FOR_DELIVERY',
                assigned=False,
                deliveryman__isnull=True
            ).exclude(pk=order.pk).order_by('order_date')

            for candidate in candidate_qs:
                if not candidate.assigned and candidate.deliveryman is None:
                    candidate.deliveryman = deliveryman
                    candidate.assigned = True
                    candidate.save(update_fields=['deliveryman', 'assigned'])
                    additionally_assigned_ids.append(candidate.pk)

    except Order.DoesNotExist:
        return Response({"detail": "Order not found."}, status=404)
    except Exception:
        return Response({"detail": "Server error while accepting order."}, status=500)

    # Channel layer send
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"deliveryman_{deliveryman.pk}",
            {"type": "current_delivery_update", "order_id": order.pk}
        )
    except:
        pass

    payload = {
        "type": "delivery_assignment",
        "order": {"order_id": order.pk},
        "deliveryman": {
            "id": deliveryman.pk,
            "firstname": deliveryman.Firstname,
            "lastname": deliveryman.Lastname,
        },
        "assigned_at": timezone.now().isoformat(),
    }

    status_obj = getattr(deliveryman, 'status', None)
    dm_user = getattr(deliveryman, 'user', None)
    dm_phone = None
    if dm_user:
        if hasattr(dm_user, 'user_profile'):
            dm_phone = getattr(dm_user.user_profile, 'phone_number', None)
        if not dm_phone and hasattr(dm_user, 'merchant_profile'):
            dm_phone = getattr(dm_user.merchant_profile, 'phone_number', None)

    deliveryman_data = {
        "id": getattr(deliveryman, "pk", None),
        "full_name": f"{getattr(deliveryman, 'Firstname', '') or ''} {getattr(deliveryman, 'Lastname', '') or ''}".strip(),
        "email": getattr(dm_user, "email", None) if dm_user else None,
        "phone": dm_phone,
        "vehicle": getattr(deliveryman, "Vehicle", None),
        "active_flag": getattr(status_obj, 'online', False) if status_obj is not None else False
    }

    order_ids = [order.pk] + additionally_assigned_ids
    order_ids .sort()

    channel_layer = get_channel_layer()
    try:
        for oid in order_ids:
            async_to_sync(channel_layer.group_send)(
                f"order_{oid}",
                {
                    "type": "deliveryman_accepted",
                    "payload": {
                        "order_id": oid,
                        "deliveryman": deliveryman_data
                    }
                }
            )

        async_to_sync(channel_layer.group_send)(
            f"deliveryman_{deliveryman.pk}",
            {
                "type": "join_multiple_order_groups",
                "order_ids": order_ids
            }
        )
    except:
        pass

    return Response({
        "success": True,
        "data": {
            "order_ids": order_ids,
            "deliveryman_data": deliveryman_data,
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_order_details_api(request, id):
    user = request.user

    def _get_item_image(food_item):
        if not food_item:
            return None
        if getattr(food_item, 'profile_picture', None):
            try:
                return food_item.profile_picture.url
            except Exception:
                pass
        return getattr(food_item, 'external_image_url', None)

    order = Order.objects.select_related('restaurant', 'deliveryman') \
        .prefetch_related(
            Prefetch('order_items',
                     queryset=OrderItem.objects.select_related('food_item'))
    ).filter(id=id, user=user).first()

    source_is_history = False
    order_items_qs = None
    source_obj = None

    if order:
        source_obj = order
        order_items_qs = order.order_items.all()
    else:
        oh = OrderHistory.objects.select_related('restaurant', 'deliveryman') \
            .prefetch_related(
                Prefetch('order_items_history',
                         queryset=OrderItemHistory.objects.select_related('food_item'))
        ).filter(original_order=str(id), user=user).first()
        if oh:
            source_is_history = True
            source_obj = oh
            order_items_qs = oh.order_items_history.all()
        else:
            return Response({"success": False, "detail": "No order found with that id for the authenticated user."},
                            status=status.HTTP_404_NOT_FOUND)

    is_assigned = bool(getattr(source_obj, 'assigned', False)
                       ) if not source_is_history else False

    customer_info = {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name(),
        "email": user.email,
        "phone": getattr(user.user_profile, 'phone_number', None) if hasattr(user, 'user_profile') else None,
    }

    restaurant_obj = getattr(source_obj, 'restaurant', None)
    restaurant_info = None
    if restaurant_obj:
        restaurant_info = {
            "id": getattr(restaurant_obj, 'id', None),
            "name": getattr(restaurant_obj, 'restaurant_name', 'N/A'),
            "owner_name": getattr(restaurant_obj, 'owner_name', 'N/A'),
            "owner_email": getattr(restaurant_obj, 'owner_email', None),
            "owner_contact": getattr(restaurant_obj, 'owner_contact', None),
            "address": getattr(restaurant_obj, 'restaurant_address', 'N/A'),
            "cuisine": getattr(restaurant_obj, 'cuisine', 'N/A'),
            "restaurant_type": getattr(restaurant_obj, 'restaurant_type', 'N/A'),
            "profile_picture": getattr(restaurant_obj.profile_picture, 'url', None) if getattr(restaurant_obj, 'profile_picture', None) else None,
            "latitude": getattr(restaurant_obj, 'latitude', None),
            "longitude": getattr(restaurant_obj, 'longitude', None),
        }

    deliveryman_obj = getattr(source_obj, 'deliveryman', None)
    deliveryman_info = None
    if deliveryman_obj:
        deliveryman_user = getattr(deliveryman_obj, 'user', None)
        phone_number = None
        if deliveryman_user:
            if hasattr(deliveryman_user, 'user_profile'):
                phone_number = getattr(
                    deliveryman_user.user_profile, 'phone_number', None)
            if not phone_number and hasattr(deliveryman_user, 'merchant_profile'):
                phone_number = getattr(
                    deliveryman_user.merchant_profile, 'phone_number', None)

        status_obj = getattr(deliveryman_obj, 'status', None)
        active_flag = bool(getattr(status_obj, 'online', False)
                           ) if status_obj is not None else False

        deliveryman_info = {
            "id": getattr(deliveryman_obj, 'id', None),
            "name": f"{getattr(deliveryman_obj, 'Firstname', '')} {getattr(deliveryman_obj, 'Lastname', '')}".strip(),
            "email": getattr(deliveryman_user, 'email', None) if deliveryman_user else None,
            "phone": phone_number or None,
            "vehicle": getattr(deliveryman_obj, 'Vehicle', None),
            "active_flag": active_flag,
        }

    order_items_data = []
    for item in (order_items_qs or []):
        fi = getattr(item, 'food_item', None)
        order_items_data.append({
            "id": getattr(item, 'id', None),
            "name": getattr(fi, 'name', 'N/A') if fi else 'N/A',
            "quantity": getattr(item, 'quantity', 0),
            "price_at_order": str(getattr(item, 'price_at_order', Decimal('0.00'))),
            "image": _get_item_image(fi),
        })

    if source_is_history:
        order_id_value = getattr(source_obj, 'original_order', None) or getattr(
            source_obj, 'id', None)
    else:
        order_id_value = getattr(source_obj, 'id', None)

    status_value = getattr(source_obj, 'status', '') or ''
    total_price_val = getattr(source_obj, 'total_price', Decimal('0.00'))
    order_date_val = getattr(source_obj, 'order_date', None)
    delivery_charge_val = getattr(
        source_obj, 'delivery_charge', Decimal('0.00'))
    payment_method_val = getattr(source_obj, 'payment_method', None)
    delivery_location_val = getattr(source_obj, 'customer_location', None)
    latitude_val = getattr(source_obj, 'latitude', None)
    longitude_val = getattr(source_obj, 'longitude', None)

    ordered_steps = ["PENDING", "PROCESSING",
                     "WAITING_FOR_DELIVERY", "OUT_FOR_DELIVERY"]
    status_progress = {step: False for step in ordered_steps}
    status_value_up = status_value.upper()
    if status_value_up in ordered_steps:
        current_index = ordered_steps.index(status_value_up)
        for i in range(0, current_index):
            status_progress[ordered_steps[i]] = True

    if status_value_up == "DELIVERED":
        for step in status_progress:
            status_progress[step] = True
    order_data = {
        "order_id": order_id_value,
        "status": status_value,
        "total_price": str(total_price_val if total_price_val is not None else Decimal('0.00')),
        "delivery_charge": str(delivery_charge_val if delivery_charge_val is not None else Decimal('0.00')),
        "payment_method": payment_method_val,
        "delivery_location": delivery_location_val,
        "order_date": order_date_val.isoformat() if order_date_val else None,
        "customer": customer_info,
        "restaurant": restaurant_info,
        "deliveryman": deliveryman_info,
        "order_items": order_items_data,
        "latitude": latitude_val,
        "longitude": longitude_val,
    }
    if source_is_history:
        order_data["delivered_time"] = source_obj.created_at.isoformat(
        ) if getattr(source_obj, 'created_at', None) else None

    return Response(
        {"success": True, "assigned": is_assigned,
            "status_progress": status_progress, "order": order_data},
        status=status.HTTP_200_OK
    )
