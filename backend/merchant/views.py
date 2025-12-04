from .models import Deliveryman, DeliverymanStatus, Order, Restaurant
from django.views.decorators.http import require_GET
from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.shortcuts import render, redirect, get_object_or_404
from .forms import MerchantSignUpForm, RestaurantRegistrationForm, MerchantForgotPasswordForm, DeliverymanForm, FoodItemForm, RestaurantBioUpdateForm, RestaurantProfilePicUpdateForm, RestaurantLocationUpdateForm, DeliverymanBioUpdateForm, DeliverymanProfilePicUpdateForm
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash, get_user_model
from .utils import account_activation_token
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import EmailMessage
from django.contrib.auth.tokens import default_token_generator
from .models import Merchant, Deliveryman, Restaurant, FoodItem, GoToDashClickCheck, Order, OrderHistory, OrderItemHistory, DeliverymanStatus
from django.contrib.auth.forms import SetPasswordForm
from django.http import Http404, JsonResponse
from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch, Q
from decimal import Decimal
from django.apps import apps
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Sum

def profile_none_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        profile = (
            getattr(request.user, 'deliveryman_profile', None)
            or getattr(request.user, 'restaurant_profile', None)
        )
        if profile is None:
            return view_func(request, *args, **kwargs)
        return redirect('application-status')
    return _wrapped_view


def merchant_home_view(request):
    if request.user.is_authenticated:
        try:
            obj = GoToDashClickCheck.objects.get(user=request.user)
            if obj.go_to_dash_clicked:
                return redirect('deliveryman-dashboard')
        except GoToDashClickCheck.DoesNotExist:
            pass

    return render(request, "merchant/m_home.html")


def merchant_signup_view(request):
    if request.method == "POST":
        signup_form = MerchantSignUpForm(request.POST)
        if signup_form.is_valid():
            user = signup_form.save()
            user.is_staff = False
            user.is_superuser = False
            user.save()
            logout(request)
            login(request, user)

            messages.success(
                request, "Account created. You are now logged in.")
            return redirect("home")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        signup_form = MerchantSignUpForm()

    return render(request, "merchant/merchant_signup.html", {"signup_form": signup_form})


@require_http_methods(["GET", "POST"])
def merchant_login_view(request):
    next_url = request.GET.get('next') or request.session.get('next_url')
    if request.user.is_authenticated:
        return redirect(next_url or "home")

    if request.method == "POST":
        next_url = request.POST.get("next") or next_url
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "You have successfully logged in.")
            return redirect(next_url or "home")
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "merchant/merchant_login.html", {"next": next_url})


@login_required
def deliveryman_dashboard(request):
    obj, created = GoToDashClickCheck.objects.get_or_create(user=request.user)
    if not obj.go_to_dash_clicked:
        obj.go_to_dash_clicked = True
        obj.save()

    try:
        profile = Deliveryman.objects.get(user=request.user)
    except Deliveryman.DoesNotExist:
        return redirect('restaurant-dashboard')

    total_completed_deliveries = OrderHistory.objects.filter(
        deliveryman=profile
    ).count()

    total_active_deliveries = 0
    total_active_deliveries = Order.objects.filter(
        deliveryman=profile,
        assigned=True,
        status__in=['WAITING_FOR_DELIVERY', 'OUT_FOR_DELIVERY']
    ).count()

    total_new_deliveries = Order.objects.filter(
        assigned=False,
        deliveryman__isnull=True,
        status="WAITING_FOR_DELIVERY"
    ).count()

    return render(request, "merchant/deliveryman_dashboard.html", {
        'deliveryman': profile,
        'total_new_deliveries':total_new_deliveries,
        'total_active_deliveries': total_active_deliveries,
        'total_completed': total_completed_deliveries,
    })

@login_required
def merchant_logout_view(request):
    user = request.user
    deliveryman = getattr(user, "deliveryman", None)

    if deliveryman:
        try:
            status = deliveryman.status
            status.online = False
            status.on_delivery = False  
            status.save()
        except DeliverymanStatus.DoesNotExist:
            pass  

    logout(request)
    messages.success(request, "You are successfully logged out")
    return redirect('home')



@login_required
@profile_none_required
def merchant_form_register_view(request):
    role = request.POST.get('role') or request.GET.get('role')

    if request.method == "POST":
        if role == "restaurant":
            form = RestaurantRegistrationForm(request.POST, request.FILES)
            if form.is_valid():
                restaurant = form.save(commit=False)
                restaurant.user = request.user
                restaurant.save()
                form.save_m2m()
                messages.success(
                    request, 'Your restaurant has been registered. Welcome aboard.')
                return redirect('home')

        elif role == "deliveryman":
            form = DeliverymanForm(request.POST, request.FILES)
            if form.is_valid():
                deliveryman = form.save(commit=False)
                deliveryman.user = request.user
                deliveryman.save()
                form.save_m2m()
                messages.success(
                    request, "Your registration has been successfully completed. Welcome aboard.")
                return redirect('home')
    else:
        if role == "restaurant":
            form = RestaurantRegistrationForm(
                initial={'Email': request.user.email})
        else:
            form = DeliverymanForm(initial={'Email': request.user.email})

    return render(request, "merchant/merchant_form_register.html", {"form": form})


@login_required
@profile_none_required
def merchant_res_reg_view(request):

    if request.method == 'POST':
        form = RestaurantRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            restaurant = form.save(commit=False)
            restaurant.owner = request.user
            restaurant.save()
            messages.success(
                request, 'Your restaurant has been registered. Welcome aboard.')
            return redirect('application-status')
    else:
        form = RestaurantRegistrationForm()

    return render(request, 'merchant/reg_restaurant.html', {'form': form})

    if request.method == 'POST':
        form = RestaurantRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            restaurant = form.save(commit=False)
            restaurant.user = request.user
            restaurant.save()
            request.session['restaurant_id'] = restaurant.id
            return redirect(request.path)
    else:
        form = RestaurantRegistrationForm()
    return render(request, 'merchant/reg_restaurant.html', {'form': form})


@login_required
def restaurant_bio_json_response(request, id):
    restaurant = get_object_or_404(Restaurant, id=id, user=request.user)
    data = {
        "restaurant_name": restaurant.restaurant_name,
        "restaurant_address": restaurant.restaurant_address,
        "description": restaurant.description,
        "owner_name": restaurant.owner_name,
        "owner_contact": restaurant.owner_contact,
        "owner_email": restaurant.owner_email,
        "restaurant_type": restaurant.restaurant_type,
    }
    return JsonResponse({"success": True, "data": data})


@login_required
def update_restaurant_bio(request):
    if request.method == "POST":
        restaurant_id = request.POST.get("restaurant_id")
        restaurant = get_object_or_404(
            Restaurant, id=restaurant_id, user=request.user)

        form = RestaurantBioUpdateForm(
            request.POST, request.FILES, instance=restaurant)
        if form.is_valid():
            form.save()
            messages.success(request, "Restaurant updated successfully.")
        else:
            messages.error(
                request, "Failed to update restaurant. Please check the form inputs.")

    return redirect("restaurant-settings")


@login_required
def update_restaurant_profile_picture(request):
    if request.method == "POST":
        restaurant_id = request.POST.get("restaurant_id")
        restaurant = get_object_or_404(
            Restaurant, id=restaurant_id, user=request.user)

        form = RestaurantProfilePicUpdateForm(
            request.POST, request.FILES, instance=restaurant)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile picture updated successfully.")
        else:
            messages.error(
                request, "Failed to update profile picture. Please try again.")

    return redirect("restaurant-settings")


@login_required
def deliveryman_bio_json_response(request, id):
    deliveryman = get_object_or_404(Deliveryman, id=id, user=request.user)
    try:
        contact = deliveryman.user.merchant_profile.phone_number
    except (AttributeError, Merchant.DoesNotExist):
        contact = None
    data = {
        "Firstname": deliveryman.Firstname,
        "Lastname": deliveryman.Lastname,
        "Address": deliveryman.Address,
        "DateofBirth": deliveryman.DateofBirth.isoformat() if deliveryman.DateofBirth else None,
        "PanNumber": deliveryman.PanNumber,
        "Email": deliveryman.user.email if deliveryman.user else None,
        "Contact": contact,
        "Vehicle": deliveryman.Vehicle,
        "VehicleNumber": deliveryman.VehicleNumber,
        "Zone": deliveryman.Zone,
        "DutyTime": deliveryman.DutyTime,
        "UserImage": deliveryman.UserImage.url if getattr(deliveryman, 'UserImage') else None,
    }
    return JsonResponse({"success": True, "data": data})


@login_required
def update_deliveryman_bio(request):
    if request.method == "POST":
        deliveryman_id = request.POST.get(
            "deliveryman_id") or request.POST.get("deliveryman")
        deliveryman = get_object_or_404(
            Deliveryman, id=deliveryman_id, user=request.user)
        form = DeliverymanBioUpdateForm(
            request.POST, request.FILES, instance=deliveryman, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
        else:
            messages.error(
                request, "Failed to update profile. Please check the form inputs.")
    return redirect("deliveryman-profile")


@login_required
def update_deliveryman_profile_picture(request):
    if request.method == "POST":
        deliveryman_id = request.POST.get(
            "deliveryman") or request.POST.get("deliveryman_id")
        deliveryman = get_object_or_404(
            Deliveryman, id=deliveryman_id, user=request.user)
        if 'UserImage' in request.FILES:
            form = DeliverymanProfilePicUpdateForm(
                request.POST, request.FILES, instance=deliveryman)
            if form.is_valid():
                form.save()
                messages.success(
                    request, "Profile picture updated successfully.")
            else:
                messages.error(
                    request, "Failed to update profile picture. Please try again.")
        elif 'profile_picture' in request.FILES:
            deliveryman.UserImage = request.FILES['profile_picture']
            try:
                deliveryman.save()
                messages.success(
                    request, "Profile picture updated successfully.")
            except Exception:
                messages.error(
                    request, "Failed to save profile picture. Please try again.")
        else:
            messages.error(request, "No image uploaded.")
    return redirect("deliveryman-profile")


@login_required
def update_restaurant_location(request):
    if request.method == "POST":
        restaurant_id = request.POST.get("restaurant_id")
        restaurant = get_object_or_404(
            Restaurant, id=restaurant_id, user=request.user)

        form = RestaurantLocationUpdateForm(request.POST, instance=restaurant)
        if form.is_valid():
            form.save()
            messages.success(request, "Location updated successfully.")
        else:
            messages.error(
                request, "Failed to update location. Please check the values.")

    return redirect("restaurant-settings")


def safe_url(field):
    try:
        return field.url if field and getattr(field, 'name', '') else None
    except Exception:
        return None


@login_required
def restaurant_orders_json_response(request, id):
    restaurant = get_object_or_404(Restaurant, id=id, user=request.user)
    status = request.GET.get('status', '').strip().upper()
    orders_qs = Order.objects.filter(restaurant=restaurant).select_related(
        'user', 'restaurant', 'deliveryman'
    ).prefetch_related('order_items__food_item')

    # Filter by status
    valid_statuses = {k for k, _ in Order.STATUS_CHOICES}
    if status and status in valid_statuses:
        orders_qs = orders_qs.filter(status=status)

    # Pagination params
    last_limit_id = request.GET.get('last_limit_id')
    try:
        limit = int(request.GET.get('limit', 10))
        if limit <= 0:
            limit = 10
    except (ValueError, TypeError):
        limit = 10

    if last_limit_id:
        try:
            last_limit_id_int = int(last_limit_id)
            orders_qs = orders_qs.filter(
                id__lt=last_limit_id_int)  # descending order
        except ValueError:
            pass

    orders_qs = orders_qs.order_by('-id')  # descending order

    # Fetch limited orders
    orders_list = list(orders_qs[:limit])

    # Determine finished status
    if not orders_list:
        finished = True
    else:
        if len(orders_list) < limit:
            finished = True  # less than limit, no more pages
        else:
            last_id_in_page = orders_list[-1].id
            remaining_orders = orders_qs.filter(
                id__lt=last_id_in_page).exists()
            finished = not remaining_orders  # no more orders after this page

    data = []

    for order in orders_list:
        items = []
        computed_total = Decimal('0.00')
        for oi in order.order_items.all():
            fi = getattr(oi, 'food_item', None)
            price_each = oi.price_at_order or (
                getattr(fi, 'price', Decimal('0.00')) if fi else Decimal('0.00'))
            item_total = price_each * oi.quantity
            computed_total += item_total

            image_url = None
            if fi:
                try:
                    image_url = fi.profile_picture.url if fi.profile_picture else fi.external_image_url
                except Exception:
                    image_url = fi.external_image_url

            items.append({
                "id": oi.pk,
                "food_item": getattr(fi, 'pk', None),
                "food_item_name": getattr(fi, 'name', ''),
                "restaurant_name": getattr(fi.restaurant, 'restaurant_name', getattr(order.restaurant, 'restaurant_name', '')),
                "food_item_image": image_url,
                "quantity": oi.quantity,
                "price_at_order": str(price_each),
                "total_price": float(item_total),
            })

        total_value = order.total_price or computed_total

        user_obj = getattr(order, 'user', None)
        phone = None
        if user_obj:
            for attr in ('phone', 'phone_number', 'mobile', 'contact', 'telephone'):
                phone = getattr(user_obj, attr, None)
                if phone:
                    break
            if not phone and hasattr(user_obj, 'user_profile'):
                profile = user_obj.user_profile
                phone = getattr(profile, 'phone', None) or getattr(
                    profile, 'phone_number', None)
            if not phone and hasattr(user_obj, 'merchant_profile'):
                merchant = user_obj.merchant_profile
                phone = getattr(merchant, 'phone_number', None)
        phone = phone or None

        deliveryman_obj = getattr(order, 'deliveryman', None)
        deliveryman_data = None
        if deliveryman_obj:
            deliveryman_data = {
                "id": deliveryman_obj.id,
                "name": f"{getattr(deliveryman_obj, 'Firstname', '')} {getattr(deliveryman_obj, 'Lastname', '')}".strip(),
                "email": getattr(deliveryman_obj, 'email', None),
                "phone": getattr(deliveryman_obj, 'phone', None),
            }

        restaurant_user = getattr(order.restaurant, 'user', None)
        restaurant_user_data = None
        if restaurant_user:
            restaurant_user_data = {
                "id": restaurant_user.id,
                "username": restaurant_user.username,
                "first_name": restaurant_user.first_name,
                "last_name": restaurant_user.last_name,
                "email": restaurant_user.email,
            }

        restaurant_data = {
            "id": order.restaurant.pk,
            "user": restaurant_user_data,
            "restaurant_name": order.restaurant.restaurant_name,
            "owner_name": order.restaurant.owner_name,
            "owner_email": order.restaurant.owner_email,
            "owner_contact": order.restaurant.owner_contact,
            "restaurant_address": order.restaurant.restaurant_address,
            "latitude": order.restaurant.latitude,
            "longitude": order.restaurant.longitude,
            "cuisine": order.restaurant.cuisine,
            "description": order.restaurant.description,
            "restaurant_type": order.restaurant.restaurant_type,
            "profile_picture": safe_url(order.restaurant.profile_picture),
            "cover_photo": safe_url(order.restaurant.cover_photo),
            "menu": safe_url(order.restaurant.menu),
            "created_at": order.restaurant.created_at.isoformat() if getattr(order.restaurant, 'created_at', None) else None,
            "approved": order.restaurant.approved,
        }

        data.append({
            "order_id": order.pk,
            "user": {
                "id": user_obj.id if user_obj else None,
                "username": user_obj.username if user_obj else '',
                "first_name": user_obj.first_name if user_obj else '',
                "last_name": user_obj.last_name if user_obj else '',
                "email": user_obj.email if user_obj else '',
            },
            "deliveryman": deliveryman_data,
            "restaurant_id": order.restaurant.pk,
            "restaurant": restaurant_data,
            "is_transited": order.is_transited,
            "delivery_charge": f"{order.delivery_charge or Decimal('0.00'):.2f}",
            "total_price": f"{total_value:.2f}",
            "order_items": items,
            "order_date": order.order_date.isoformat() if order.order_date else None,
            "status": order.status,
            "payment_method": (order.payment_method or '').lower(),
            "latitude": str(order.latitude) if order.latitude is not None else None,
            "longitude": str(order.longitude) if order.longitude is not None else None,
            "customer_details": {
                "email": user_obj.email if user_obj else '',
                "phone": phone,
            },
            "assigned": getattr(order, "assigned", False),
        })

    return JsonResponse({"success": True, "data": data, "finished": finished}, encoder=DjangoJSONEncoder, safe=True)


@login_required
def application_status_view(request):
    if request.user.is_authenticated:
        try:
            obj = GoToDashClickCheck.objects.get(user=request.user)
            if obj.go_to_dash_clicked:
                return redirect('deliveryman-dashboard')
        except GoToDashClickCheck.DoesNotExist:
            pass

    profile = (
        getattr(request.user, 'deliveryman_profile', None)
        or getattr(request.user, 'restaurant_profile', None)
    )
    if profile is None:
        messages.error(
            request, "Access Denied! You are neither a deliveryman nor a restaurant owner.")
        return redirect('home')

    return render(request, "merchant/application_status.html", {
        'profile': profile,
    })


def merchant_forgetpassword_view(request):
    if request.method == 'POST':
        form = MerchantForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')

            try:
                user = User.objects.get(email=email)

                try:
                    merchant = Merchant.objects.get(user=user)

                    current_site = get_current_site(request)
                    mail_subject = 'Reset your merchant password'
                    message = render_to_string('merchant/password_reset_email.html', {
                        'user': user,
                        'merchant': merchant,
                        'domain': current_site.domain,
                        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                        'token': account_activation_token.make_token(user),
                        'protocol': 'https' if request.is_secure() else 'http',
                    })

                    email_message = EmailMessage(
                        mail_subject, message, to=[email])
                    email_message.content_subtype = "html"

                    try:
                        email_message.send()
                        messages.success(
                            request, 'Password reset email has been sent. Please check your inbox.')
                        return redirect('email-sent')
                    except Exception as e:
                        messages.error(
                            request, 'Failed to send email. Please try again later.')

                except Merchant.DoesNotExist:
                    messages.error(
                        request, 'This email is not associated with any merchant account.')
            except User.DoesNotExist:
                messages.error(
                    request, 'No account found with that email address.')
    else:
        form = MerchantForgotPasswordForm()

    return render(request, 'merchant/forget_password.html', {'form': form})


def merchant_reset_password_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_user_model().objects.get(pk=uid)
        merchant = Merchant.objects.get(user=user)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist, Merchant.DoesNotExist):
        user = None
        merchant = None

    if user is not None and merchant is not None and account_activation_token.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                update_session_auth_hash(request, form.user)
                messages.success(
                    request, 'Your merchant password has been reset successfully.')
                return redirect('merchant-signin')
        else:
            form = SetPasswordForm(user)

        return render(request, 'merchant/reset_password.html', {'form': form, 'merchant': merchant})
    else:
        messages.error(
            request, 'Password reset link is invalid or has expired.')
        return redirect('mechant-signin')


def email_sent_view(request):
    return render(request, "merchant/email_sent.html")

@login_required
def restaurant_dashboard(request):
    from django.utils import timezone
    from datetime import timedelta, datetime, timezone as dt_timezone
    from django.db.models import Sum

    def format_number(num):
        num = float(num)
        if num >= 1_000_000_000:
            return f"{num/1_000_000_000:.1f}B"
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        if num >= 1_000:
            return f"{num/1_000:.1f}k"
        return str(int(num))

    obj, created = GoToDashClickCheck.objects.get_or_create(user=request.user)
    if not obj.go_to_dash_clicked:
        obj.go_to_dash_clicked = True
        obj.save()
    try:
        profile = Restaurant.objects.get(user=request.user)
    except Restaurant.DoesNotExist:
        return redirect('deliveryman-dashboard')
    fooditem_count = FoodItem.objects.filter(restaurant=profile).count()
    orders_count = Order.objects.filter(restaurant=profile).count()
    total_customers = OrderHistory.objects.filter(
        restaurant=profile
    ).values('user').distinct().count()
    total_revenue = OrderHistory.objects.filter(
        restaurant=profile
    ).aggregate(total=Sum('total_price'))['total'] or 0
    formatted_total_revenue = format_number(total_revenue)

    # --- Last 7 days orders sliding with today ---
    today = timezone.now().date()
    base_qs = OrderHistory.objects.filter(restaurant=profile)
    last_7_days_orders = []

    for d in range(6, -1, -1):  # 6 days ago → today
        day = today - timedelta(days=d)
        start = datetime.combine(day, datetime.min.time(), tzinfo=dt_timezone.utc)
        end = datetime.combine(day, datetime.max.time(), tzinfo=dt_timezone.utc)
        count = base_qs.filter(order_date__gte=start, order_date__lte=end).count()
        last_7_days_orders.append(count)

    print("Sliding last_7_days_orders:", last_7_days_orders)

    return render(request, "merchant/restaurant_dashboard.html", {
        'restaurant': profile,
        'fooditem_count': fooditem_count,
        'orders_count': orders_count,
        'total_customers': total_customers,
        'total_revenue': formatted_total_revenue,
        'last_7_days_orders': last_7_days_orders,
    })

@login_required
def restaurant_orders(request):
    try:
        profile = Restaurant.objects.get(user=request.user)
    except Restaurant.DoesNotExist:
        return redirect('deliveryman-dashboard')
    return render(request, "merchant/restaurant_orders.html", {
        'restaurant': profile,
    })


@login_required
def deliveryman_new_orders(request):
    try:
        profile = Deliveryman.objects.get(user=request.user)
    except Deliveryman.DoesNotExist:
        return redirect('restaurant-dashboard')
    return render(request, "merchant/deliveryman_new_orders.html", {
        'deliveryman': profile,
    })


@login_required
def deliveryman_current_orders(request):
    try:
        profile = Deliveryman.objects.get(user=request.user)
    except Deliveryman.DoesNotExist:
        return redirect('restaurant-dashboard')
    return render(request, "merchant/deliveryman_current_orders.html", {
        'deliveryman': profile,
    })


def serialize_item(request, item):
    return {
        "id": item.id,
        "name": item.name,
        "price": float(item.price) if item.price is not None else None,
        "discount": float(item.discount) if item.discount is not None else 0.0,
        "description": item.description or "",
        "veg_nonveg": item.veg_nonveg,
        "availability_status": item.availability_status,
        "profile_picture": request.build_absolute_uri(item.profile_picture.url) if item.profile_picture else None,
        "restaurant_id": item.restaurant_id,
    }


@login_required
def menu_update_view(request, pk):
    try:
        profile = Restaurant.objects.get(user=request.user)
    except Restaurant.DoesNotExist:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    item = get_object_or_404(FoodItem, pk=pk, restaurant=profile)

    data = {
        "id": item.id,
        "name": item.name,
        "price": str(item.price) if item.price is not None else "",
        "discount": str(item.discount) if item.discount is not None else "0",
        "veg_nonveg": item.veg_nonveg,
        "availability_status": item.availability_status,
        "profile_picture": item.profile_picture.url if item.profile_picture else None,
        "description": item.description or "",
    }

    return JsonResponse(data)


@login_required
def restaurant_menu_dishes(request):
    try:
        profile = Restaurant.objects.get(user=request.user)
    except Restaurant.DoesNotExist:
        return redirect('deliveryman-dashboard')

    if request.method == "POST":
        item_id = request.POST.get("item_id")
        if item_id:
            item = get_object_or_404(FoodItem, pk=item_id, restaurant=profile)
            form = FoodItemForm(request.POST, request.FILES, instance=item)
        else:
            form = FoodItemForm(request.POST, request.FILES)

        if form.is_valid():
            food_item = form.save(commit=False)
            food_item.restaurant = profile
            food_item.save()
            form.save_m2m()
            messages.success(
                request, "Item updated." if item_id else "Item created.")
            return redirect("restaurant-menu-dishes")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = FoodItemForm()

    qs = FoodItem.objects.filter(restaurant=profile).order_by("-id")
    foods = []
    for itm in qs:
        foods.append({
            "id": itm.id,
            "name": itm.name,
            "price": float(itm.price) if itm.price is not None else None,
            "discount": float(itm.discount) if itm.discount is not None else 0.0,
            "veg_nonveg": itm.veg_nonveg,
            "availability_status": itm.availability_status,
            "profile_picture": itm.profile_picture.url if itm.profile_picture else None,
            "description": itm.description or "",
        })

    return render(request, "merchant/restaurant_menu_dishes.html", {
        "restaurant": profile,
        "form": form,
        "foods": foods,
    })


@login_required
def delete_food_item(request):
    if request.method == "POST":
        try:
            profile = Restaurant.objects.get(user=request.user)
        except Restaurant.DoesNotExist:
            return redirect('deliveryman-dashboard')

        item_id = request.POST.get("item_id")
        item = get_object_or_404(FoodItem, pk=item_id, restaurant=profile)
        item.delete()
        messages.success(request, "Item deleted successfully.")
        return redirect("restaurant-menu-dishes")

    return redirect("restaurant-menu-dishes")


@login_required
def restaurant_customers(request):
    try:
        profile = Restaurant.objects.get(user=request.user)
    except Restaurant.DoesNotExist:
        return redirect('deliveryman-dashboard')
    return render(request, "merchant/restaurant_history.html", {
        'restaurant': profile,
    })


@login_required
def deliveryman_history(request):
    try:
        profile = Deliveryman.objects.get(user=request.user)
    except Deliveryman.DoesNotExist:
        return redirect('restaurant-dashboard')
    return render(request, "merchant/deliveryman_history.html", {
        'deliveryman': profile,
    })


@login_required
def deliveryman_profile(request):
    try:
        profile = Deliveryman.objects.get(user=request.user)
    except Deliveryman.DoesNotExist:
        return redirect('restaurant-dashboard')
    return render(request, "merchant/deliveryman_profile.html", {
        'deliveryman': profile,
    })


@login_required
def restaurant_settings(request):
    try:
        profile = Restaurant.objects.get(user=request.user)
    except Restaurant.DoesNotExist:
        return redirect('deliveryman-dashboard')
    return render(request, "merchant/restaurant_settings.html", {
        'restaurant': profile,
    })


def lobby_view(request):
    try:
        profile = Restaurant.objects.get(user=request.user)
    except Restaurant.DoesNotExist:
        return redirect('deliveryman-dashboard')
    return render(request, 'merchant/dummy_lobby.html')


def order_receive_view(request):
    try:
        profile = Restaurant.objects.get(user=request.user)
    except Restaurant.DoesNotExist:
        return redirect('deliveryman-dashboard')
    return render(request, 'merchant/order_receive.html')


@login_required
def deliveryman_order_receive_view(request):
    try:
        profile = Deliveryman.objects.get(user=request.user)
    except Deliveryman.DoesNotExist:
        return redirect('restaurant-dashboard')
    return render(request, 'merchant/deliveryman_order_receive.html', {'deliveryman': profile})


@login_required
@require_GET
def deliveryman_delivery_requests_json_view(request):
    Deliveryman = apps.get_model("merchant", "Deliveryman")
    DeliverymanStatus = apps.get_model("merchant", "DeliverymanStatus")
    Order = apps.get_model("merchant", "Order")
    OrderItem = apps.get_model("merchant", "OrderItem")

    deliveryman = None
    deliveryman_id = request.GET.get('deliveryman_id')
    if deliveryman_id:
        deliveryman = Deliveryman.objects.filter(pk=deliveryman_id).first()
    else:
        deliveryman = getattr(request.user, 'deliveryman_profile', None)

    if not deliveryman:
        return HttpResponseBadRequest(
            "No deliveryman specified and request.user is not a deliveryman."
        )

    status_obj, _ = DeliverymanStatus.objects.get_or_create(
        deliveryman=deliveryman)
    status_data = {
        "deliveryman_id": deliveryman.pk,
        "online": bool(status_obj.online),
        "on_delivery": bool(status_obj.on_delivery),
        "latitude": float(status_obj.latitude) if status_obj.latitude is not None else None,
        "longitude": float(status_obj.longitude) if status_obj.longitude is not None else None,
        "last_updated": status_obj.last_updated.isoformat() if status_obj.last_updated else None,
    }

    def _safe_image_url(obj, attr_name):
        f = getattr(obj, attr_name, None)
        if f:
            try:
                return f.url
            except Exception:
                return str(f)
        return None

    def _get_user_phone(user_obj):
        if not user_obj:
            return None
        for attr in ('phone', 'phone_number', 'mobile', 'contact', 'telephone'):
            phone = getattr(user_obj, attr, None)
            if phone:
                return phone
        if hasattr(user_obj, 'user_profile'):
            profile = user_obj.user_profile
            return getattr(profile, 'phone', None) or getattr(profile, 'phone_number', None)
        if hasattr(user_obj, 'merchant_profile'):
            merchant = user_obj.merchant_profile
            return getattr(merchant, 'phone_number', None)
        return None

    def _build_order_detail(order_obj):
        items = []
        computed_total = Decimal('0.00')
        try:
            order_items_qs = order_obj.order_items.select_related(
                "food_item").all()
        except Exception:
            order_items_qs = []

        for oi in order_items_qs:
            fi = getattr(oi, "food_item", None)
            price_each = oi.price_at_order or (
                getattr(fi, 'price', Decimal('0.00')) if fi else Decimal('0.00'))
            qty = oi.quantity or 0
            item_total = (price_each or Decimal('0.00')) * qty
            computed_total += item_total
            image_url = None
            if fi:
                try:
                    image_url = fi.profile_picture.url if getattr(
                        fi, 'profile_picture', None) else getattr(fi, 'external_image_url', None)
                except Exception:
                    image_url = getattr(fi, 'external_image_url', None)
            items.append({
                "id": getattr(oi, "pk", None),
                "food_item": getattr(fi, "pk", None),
                "food_item_name": getattr(fi, "name", "") if fi else "",
                "restaurant_name": getattr(getattr(fi, 'restaurant', None), 'restaurant_name', getattr(getattr(order_obj, 'restaurant', None), 'restaurant_name', '')) if fi or getattr(order_obj, 'restaurant', None) else '',
                "food_item_image": image_url,
                "quantity": qty,
                "price_at_order": str(price_each),
                "total_price": float(item_total),
            })

        total_value = getattr(order_obj, "total_price", None) or computed_total
        user_obj = getattr(order_obj, 'user', None)
        phone = _get_user_phone(user_obj)
        rest = getattr(order_obj, 'restaurant', None)

        restaurant_user_data = None
        if rest and getattr(rest, 'user', None):
            ru = rest.user
            restaurant_user_data = {
                "id": getattr(ru, 'id', None),
                "username": getattr(ru, 'username', ''),
                "first_name": getattr(ru, 'first_name', ''),
                "last_name": getattr(ru, 'last_name', ''),
                "email": getattr(ru, 'email', ''),
            }

        restaurant_data = None
        if rest:
            restaurant_data = {
                "id": getattr(rest, 'pk', None),
                "user": restaurant_user_data,
                "restaurant_name": getattr(rest, 'restaurant_name', ''),
                "owner_name": getattr(rest, 'owner_name', ''),
                "owner_email": getattr(rest, 'owner_email', ''),
                "owner_contact": getattr(rest, 'owner_contact', ''),
                "restaurant_address": getattr(rest, 'restaurant_address', ''),
                "latitude": getattr(rest, 'latitude', None),
                "longitude": getattr(rest, 'longitude', None),
                "cuisine": getattr(rest, 'cuisine', None),
                "description": getattr(rest, 'description', None),
                "restaurant_type": getattr(rest, 'restaurant_type', None),
                "profile_picture": _safe_image_url(rest, 'profile_picture'),
                "cover_photo": _safe_image_url(rest, 'cover_photo'),
                "menu": _safe_image_url(rest, 'menu'),
                "created_at": getattr(rest, 'created_at', None).isoformat() if getattr(rest, 'created_at', None) else None,
                "approved": getattr(rest, 'approved', None),
            }

        order_assigned = bool(order_obj.assigned)

        return {
            "order_assigned": order_assigned,
            "order_id": getattr(order_obj, "pk", None),
            "user": {
                "id": getattr(user_obj, 'id', None),
                "username": getattr(user_obj, 'username', '') if user_obj else '',
                "first_name": getattr(user_obj, 'first_name', '') if user_obj else '',
                "last_name": getattr(user_obj, 'last_name', '') if user_obj else '',
                "email": getattr(user_obj, 'email', '') if user_obj else '',
            },
            "restaurant_id": getattr(rest, 'pk', None) if rest else None,
            "restaurant": restaurant_data,
            "is_transited": getattr(order_obj, 'is_transited', False),
            "delivery_charge": f"{(getattr(order_obj, 'delivery_charge', None) or Decimal('0.00')):.2f}",
            "total_price": f"{(total_value or Decimal('0.00')):.2f}",
            "order_items": items,
            "order_date": getattr(order_obj, 'order_date', None).isoformat() if getattr(order_obj, 'order_date', None) else None,
            "status": getattr(order_obj, 'status', None),
            "payment_method": (getattr(order_obj, 'payment_method', '') or '').lower(),
            "latitude": str(getattr(order_obj, 'latitude', None)) if getattr(order_obj, 'latitude', None) is not None else None,
            "longitude": str(getattr(order_obj, 'longitude', None)) if getattr(order_obj, 'longitude', None) is not None else None,
            "customer_details": {
                "email": getattr(user_obj, 'email', '') if user_obj else '',
                "phone": phone,
            },
            "customer_location": getattr(order_obj, 'customer_location', '')
        }

    order_qs = Order.objects.select_related("user", "restaurant", "deliveryman").prefetch_related(
        Prefetch("order_items",
                 queryset=OrderItem.objects.select_related("food_item"))
    ).filter(status='WAITING_FOR_DELIVERY', assigned=False, deliveryman__isnull=True).order_by('-order_date')

    detailed_orders = [_build_order_detail(o) for o in order_qs]

    assigned_to_me_flag = Order.objects.filter(
        deliveryman=deliveryman, assigned=True).exists()

    assigned_order = Order.objects.filter(
        deliveryman=deliveryman, assigned=True).select_related('restaurant').first()
    assigned_restaurant = None
    if assigned_order and getattr(assigned_order, 'restaurant', None):
        assigned_restaurant = getattr(
            getattr(assigned_order, 'restaurant'), 'restaurant_name', None)

    return JsonResponse({
        "status": status_data,
        "assigned_to_me": assigned_to_me_flag,
        "assigned_restaurant": assigned_restaurant,
        "orders": detailed_orders,
        "returned_at": timezone.now().isoformat(),
    }, encoder=DjangoJSONEncoder, safe=False)


@login_required
@require_GET
def deliveryman_current_delivery_json_view(request):
    Deliveryman = apps.get_model("merchant", "Deliveryman")
    DeliverymanStatus = apps.get_model("merchant", "DeliverymanStatus")
    Order = apps.get_model("merchant", "Order")
    OrderItem = apps.get_model("merchant", "OrderItem")

    deliveryman_id = request.GET.get('deliveryman_id')
    if deliveryman_id:
        deliveryman = Deliveryman.objects.filter(pk=deliveryman_id).first()
    else:
        deliveryman = getattr(request.user, 'deliveryman_profile', None)

    if not deliveryman:
        return HttpResponseBadRequest("No deliveryman specified and request.user is not a deliveryman.")

    status_obj, _ = DeliverymanStatus.objects.get_or_create(
        deliveryman=deliveryman)
    status_data = {
        "deliveryman_id": deliveryman.pk,
        "online": bool(status_obj.online),
        "on_delivery": bool(status_obj.on_delivery),
        "latitude": float(status_obj.latitude) if status_obj.latitude is not None else None,
        "longitude": float(status_obj.longitude) if status_obj.longitude is not None else None,
        "last_updated": status_obj.last_updated.isoformat() if status_obj.last_updated else None,
    }

    def _safe_image_url(obj, attr_name):
        f = getattr(obj, attr_name, None)
        if f:
            try:
                return f.url
            except:
                return str(f)
        return None

    def _get_user_phone(user_obj):
        if not user_obj:
            return None
        for attr in ('phone', 'phone_number', 'mobile', 'contact', 'telephone'):
            phone = getattr(user_obj, attr, None)
            if phone:
                return phone
        if hasattr(user_obj, 'user_profile'):
            p = user_obj.user_profile
            return getattr(p, 'phone', None) or getattr(p, 'phone_number', None)
        if hasattr(user_obj, 'merchant_profile'):
            m = user_obj.merchant_profile
            return getattr(m, 'phone_number', None)
        return None

    def _build_order_detail(order_obj):
        items = []
        computed_total = Decimal('0.00')
        try:
            order_items_qs = order_obj.order_items.select_related(
                "food_item").all()
        except:
            order_items_qs = []

        for oi in order_items_qs:
            fi = getattr(oi, "food_item", None)
            price_each = oi.price_at_order or (
                getattr(fi, 'price', Decimal('0.00')) if fi else Decimal('0.00'))
            qty = oi.quantity or 0
            item_total = (price_each or Decimal('0.00')) * qty
            computed_total += item_total
            try:
                image_url = fi.profile_picture.url if getattr(
                    fi, 'profile_picture', None) else getattr(fi, 'external_image_url', None)
            except:
                image_url = getattr(fi, 'external_image_url', None)

            items.append({
                "id": getattr(oi, "pk", None),
                "food_item": getattr(fi, "pk", None),
                "food_item_name": getattr(fi, "name", "") if fi else "",
                "restaurant_name": getattr(getattr(fi, 'restaurant', None), 'restaurant_name', getattr(getattr(order_obj, 'restaurant', None), 'restaurant_name', '')) if fi or getattr(order_obj, 'restaurant', None) else '',
                "food_item_image": image_url,
                "quantity": qty,
                "price_at_order": str(price_each),
                "total_price": float(item_total),
            })

        total_value = getattr(order_obj, "total_price", None) or computed_total
        user_obj = getattr(order_obj, 'user', None)
        phone = _get_user_phone(user_obj)
        rest = getattr(order_obj, 'restaurant', None)
        restaurant_user_data = None
        if rest and getattr(rest, 'user', None):
            ru = rest.user
            restaurant_user_data = {
                "id": getattr(ru, 'id', None),
                "username": getattr(ru, 'username', ''),
                "first_name": getattr(ru, 'first_name', ''),
                "last_name": getattr(ru, 'last_name', ''),
                "email": getattr(ru, 'email', ''),
            }

        restaurant_data = None
        if rest:
            restaurant_data = {
                "id": getattr(rest, 'pk', None),
                "user": restaurant_user_data,
                "restaurant_name": getattr(rest, 'restaurant_name', ''),
                "owner_name": getattr(rest, 'owner_name', ''),
                "owner_email": getattr(rest, 'owner_email', ''),
                "owner_contact": getattr(rest, 'owner_contact', ''),
                "restaurant_address": getattr(rest, 'restaurant_address', ''),
                "latitude": getattr(rest, 'latitude', None),
                "longitude": getattr(rest, 'longitude', None),
                "cuisine": getattr(rest, 'cuisine', None),
                "description": getattr(rest, 'description', None),
                "restaurant_type": getattr(rest, 'restaurant_type', None),
                "profile_picture": _safe_image_url(rest, 'profile_picture'),
                "cover_photo": _safe_image_url(rest, 'cover_photo'),
                "menu": _safe_image_url(rest, 'menu'),
                "created_at": getattr(rest, 'created_at', None).isoformat() if getattr(rest, 'created_at', None) else None,
                "approved": getattr(rest, 'approved', None),
            }

        return {
            "order_assigned": bool(order_obj.assigned),
            "order_id": getattr(order_obj, "pk", None),
            "user": {
                "id": getattr(user_obj, 'id', None),
                "username": getattr(user_obj, 'username', '') if user_obj else '',
                "first_name": getattr(user_obj, 'first_name', '') if user_obj else '',
                "last_name": getattr(user_obj, 'last_name', '') if user_obj else '',
                "email": getattr(user_obj, 'email', '') if user_obj else '',
            },
            "restaurant_id": getattr(rest, 'pk', None) if rest else None,
            "restaurant": restaurant_data,
            "is_transited": getattr(order_obj, 'is_transited', False),
            "delivery_charge": f"{(getattr(order_obj, 'delivery_charge', None) or Decimal('0.00')):.2f}",
            "total_price": f"{(total_value or Decimal('0.00')):.2f}",
            "order_items": items,
            "order_date": getattr(order_obj, 'order_date', None).isoformat() if getattr(order_obj, 'order_date', None) else None,
            "status": getattr(order_obj, 'status', None),
            "payment_method": (getattr(order_obj, 'payment_method', '') or '').lower(),
            "latitude": str(getattr(order_obj, 'latitude', None)) if getattr(order_obj, 'latitude', None) is not None else None,
            "longitude": str(getattr(order_obj, 'longitude', None)) if getattr(order_obj, 'longitude', None) is not None else None,
            "customer_details": {
                "email": getattr(user_obj, 'email', '') if user_obj else '',
                "phone": phone,
            },
            "customer_location": getattr(order_obj, 'customer_location', '')
        }

    order_qs = Order.objects.select_related("user", "restaurant", "deliveryman").prefetch_related(
        Prefetch("order_items",
                 queryset=OrderItem.objects.select_related("food_item"))
    ).filter(deliveryman=deliveryman, assigned=True, status__in=["WAITING_FOR_DELIVERY", "OUT_FOR_DELIVERY"]).order_by('-order_date')

    detailed_orders = [_build_order_detail(o) for o in order_qs]

    assigned_restaurant = None
    latitude = None
    longitude = None
    assigned_order = order_qs.select_related('restaurant').first()
    if assigned_order and getattr(assigned_order, 'restaurant', None):
        rest = getattr(assigned_order, 'restaurant')
        assigned_restaurant = getattr(rest, 'restaurant_name', None)
        latitude = getattr(rest, 'latitude', None)
        longitude = getattr(rest, 'longitude', None)

    return JsonResponse({
        "status": status_data,
        "has_current_assignments": order_qs.exists(),
        "assigned_restaurant": assigned_restaurant,
        "latitude": latitude,
        "longitude": longitude,
        "orders": detailed_orders,
        "returned_at": timezone.now().isoformat(),
    }, encoder=DjangoJSONEncoder, safe=False)


@login_required
def current_delivery_websocket_view(request):
    return render(request, 'merchant/current_delivery_websocket.html')

# def check_deliveryman_status(request):
#     # Get all active sessions
#     sessions = Session.objects.filter(expire_date__gte=timezone.now())
#     user_ids = []

#     for session in sessions:
#         data = session.get_decoded()
#         uid = data.get("_auth_user_id")
#         if uid:
#             user_ids.append(int(uid))

#     # Get online and offline deliverymen
#     online_deliverymen = Deliveryman.objects.filter(user__id__in=user_ids)
#     offline_deliverymen = Deliveryman.objects.exclude(user__id__in=user_ids)

#     # For testing - print them out
#     print("ONLINE DELIVERYMEN:")
#     for d in online_deliverymen:
#         print(f"- {d.Firstname} {d.Lastname}")

#     print("\nOFFLINE DELIVERYMEN:")
#     for d in offline_deliverymen:
#         print(f"- {d.Firstname} {d.Lastname}")

#     return JsonResponse({
#         "online": [f"{d.Firstname} {d.Lastname}" for d in online_deliverymen],
#         "offline": [f"{d.Firstname} {d.Lastname}" for d in offline_deliverymen],
#     })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_update_order_status_api(request):
    order_ids = request.data.get('order_ids')
    deliveryman_location = request.data.get('deliveryman_location')

    if not order_ids or not isinstance(order_ids, (list, tuple)):
        return Response(
            {"detail": "'order_ids' is required and must be a list."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        order_ids = [int(i) for i in order_ids]
    except:
        return Response(
            {"detail": "'order_ids' must contain only integers."},
            status=status.HTTP_400_BAD_REQUEST
        )

    new_status = "OUT_FOR_DELIVERY"
    updated = []
    not_found = []

    for oid in order_ids:
        try:
            order = Order.objects.get(pk=oid)
        except Order.DoesNotExist:
            not_found.append(oid)
            continue

        try:
            order.status = new_status
            order.save()

            deliveryman = order.deliveryman
            if deliveryman:
                dm_status, _ = DeliverymanStatus.objects.get_or_create(
                    deliveryman=deliveryman)
                dm_status.on_delivery = True
                dm_status.save()

            updated.append(oid)
        except Exception as exc:
            return Response(
                {"detail": f"Error updating order {oid}: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    channel_layer = get_channel_layer()
    try:
        for order_id in order_ids:
            async_to_sync(channel_layer.group_send)(
                f"order_{order_id}",
                {
                    "type": "order_status_change",
                    "payload": {
                        "order_id": order_id,
                        "new_status": new_status,
                        "deliveryman_location": deliveryman_location
                    }
                }
            )
    except Exception:
        pass

    response_data = {
        "updated_order_ids": updated,
        "not_found_order_ids": not_found,
        "detail": f"Processed {len(order_ids)} order(s): {len(updated)} updated, {len(not_found)} not found."
    }

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def archive_and_delete_order_api(request):
    order_id = request.data.get('order_id')
    if order_id is None:
        return Response({"detail": "'order_id' is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order_id = int(order_id)
    except (ValueError, TypeError):
        return Response({"detail": "'order_id' must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order = Order.objects.select_related('user', 'restaurant', 'deliveryman').prefetch_related(
            'order_items__food_item'
        ).get(pk=order_id)
    except Order.DoesNotExist:
        return Response({"detail": f"Order with id {order_id} does not exist."}, status=status.HTTP_404_NOT_FOUND)

    try:
        with transaction.atomic():
            oh = OrderHistory.objects.create(
                user=order.user,
                restaurant=order.restaurant,
                total_price=order.total_price,
                deliveryman=order.deliveryman,
                order_date=order.order_date,
                status='DELIVERED',
                payment_method=order.payment_method,
                customer_location=order.customer_location,
                latitude=order.latitude,
                longitude=order.longitude,
                delivery_charge=order.delivery_charge,
                original_order=str(order.pk)
            )

            for oi in order.order_items.all():
                OrderItemHistory.objects.create(
                    order_history=oh,
                    food_item=oi.food_item,
                    quantity=oi.quantity,
                    price_at_order=oi.price_at_order if oi.price_at_order is not None else oi.food_item.price
                )

            deliveryman = order.deliveryman
            order.delete()

            if deliveryman:
                has_remaining_orders = Order.objects.filter(
                    deliveryman=deliveryman,
                    assigned=True,
                    status='OUT_FOR_DELIVERY'
                ).exists()

                if not has_remaining_orders:
                    dm_status, _ = DeliverymanStatus.objects.get_or_create(
                        deliveryman=deliveryman)
                    dm_status.on_delivery = False
                    dm_status.save()

    except Exception as exc:
        return Response(
            {"detail": "Failed to archive and delete order.",
             "error": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    channel_layer = get_channel_layer()

    try:
        async_to_sync(channel_layer.group_send)(
            f"order_{order_id}",
            {
                "type": "order_status_change",
                "payload": {
                    "order_id": order_id,
                    "new_status": "DELIVERED"
                }
            }
        )
    except Exception:
        pass

    return Response(
        {"detail": f"Order {order_id} archived to OrderHistory #{oh.pk} and deleted from Orders."},
        status=status.HTTP_200_OK
    )


@login_required
def deliveryman_status_and_orders(request):
    user = request.user
    try:
        deliveryman = Deliveryman.objects.get(user=user)
    except Deliveryman.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "detail": "Access denied. User is not registered as a Deliveryman."
            },
            status=403
        )
    status_obj = getattr(deliveryman, "status", None)
    if not status_obj or not status_obj.on_delivery:
        return JsonResponse({"success": True, "status": "IDLE"})
    active_statuses = ['OUT_FOR_DELIVERY',
                       'WAITING_FOR_DELIVERY', 'PROCESSING']
    orders_qs = Order.objects.filter(
        deliveryman=deliveryman,
        assigned=True,
        status__in=active_statuses
    )

    order_ids = list(orders_qs.values_list('id', flat=True))

    return JsonResponse({
        "success": True,
        "status": "OUT_FOR_DELIVERY",
        "order_ids": order_ids
    })


@login_required
def deliveryman_order_history_json_response(request):
    user = request.user
    try:
        deliveryman = Deliveryman.objects.get(user=user)
    except Deliveryman.DoesNotExist:
        return JsonResponse(
            {"success": False,
             "detail": "Access denied. User is not registered as a Deliveryman."},
            status=403
        )

    try:
        historical_orders = OrderHistory.objects.filter(
            deliveryman=deliveryman,
            status__in=['DELIVERED', 'COMPLETED', 'ARCHIVED']
        ).select_related(
            'user',
            'restaurant'
        ).prefetch_related(
            'order_items_history__food_item',
            'user__user_profile'  # prefetch Customer profile
        ).order_by('-order_date')

    except Exception as e:
        print(f"Database query error: {e}")
        return JsonResponse(
            {"success": False, "detail": "An internal error occurred while fetching order history."},
            status=500
        )

    history_data = []

    for order in historical_orders:
        restaurant_name = getattr(order.restaurant, 'restaurant_name', getattr(
            order.restaurant, 'name', 'N/A'))
        restaurant_address = getattr(
            order.restaurant, 'restaurant_address', 'N/A')
        restaurant_contact = getattr(order.restaurant, 'owner_contact', 'N/A')

        customer_name = order.user.get_full_name() or order.user.username

        # Fetch phone from Customer profile if exists
        customer_number = "N/A"
        if hasattr(order.user, 'user_profile') and getattr(order.user.user_profile, 'phone_number', None):
            customer_number = order.user.user_profile.phone_number

        # Order items
        order_items_data = []
        for item in order.order_items_history.all():
            order_items_data.append({
                "item_name": item.food_item.name if item.food_item else "N/A",
                "quantity": item.quantity,
                "price_at_order": str(item.price_at_order),
            })

        order_entry = {
            "order_id": order.pk,
            "original_order_id": order.original_order,
            "customer_info": {
                "customer": customer_name,
                "address": order.customer_location,
                "number": customer_number
            },
            "merchant_info": {
                "restaurant_name": restaurant_name,
                "address": restaurant_address,
                "contact_no": restaurant_contact,
            },
            "order_status": order.status,
            "total_price": str(order.total_price),
            "order_date": order.order_date.isoformat(),
            "order_items": order_items_data
        }
        history_data.append(order_entry)

    return JsonResponse({"success": True, "data": history_data}, status=200)


@login_required
def restaurant_order_list_json_response(request):
    user = request.user
    try:
        restaurant = Restaurant.objects.get(user=user)
    except Restaurant.DoesNotExist:
        return JsonResponse(
            {"success": False, "detail": "Access denied. User is not registered as a Restaurant owner."},
            status=403
        )

    try:
        orders = list(OrderHistory.objects.filter(restaurant=restaurant))
        orders = sorted(orders, key=lambda o: o.order_date, reverse=True)
    except Exception as e:
        print(f"Database query error: {e}")
        return JsonResponse(
            {"success": False, "detail": "An internal error occurred while fetching orders."},
            status=500
        )

    order_list = []

    for order in orders:
        customer_name = order.user.get_full_name() or order.user.username
        customer_number = getattr(order.user.user_profile, 'phone_number', 'N/A') if hasattr(order.user, 'user_profile') else 'N/A'

        customer_info = {
            "customer": customer_name,
            "address": getattr(order, 'customer_location', 'N/A'),
            "number": customer_number
        }

        deliveryman_info = {}
        if hasattr(order, 'deliveryman') and order.deliveryman:
            deliveryman = order.deliveryman
            phone_number = None
            if hasattr(deliveryman.user, 'user_profile'):
                phone_number = getattr(deliveryman.user.user_profile, 'phone_number', None)
            if not phone_number and hasattr(deliveryman.user, 'merchant_profile'):
                phone_number = getattr(deliveryman.user.merchant_profile, 'phone_number', None)
            if not phone_number:
                phone_number = 'N/A'

            deliveryman_info = {
                "deliveryman_name": f"{deliveryman.Firstname} {deliveryman.Lastname}",
                "phone_number": phone_number,
                "vehicle": getattr(deliveryman, 'Vehicle', 'N/A')
            }

        if hasattr(order, 'order_items_history'):
            order_items = order.order_items_history.all()
        else:
            order_items = []

        order_items_data = []
        for item in order_items:
            order_items_data.append({
                "item_name": item.food_item.name if item.food_item else "N/A",
                "quantity": item.quantity,
                "price_at_order": str(item.price_at_order)
            })

        order_entry = {
            "order_id": order.pk,
            "original_order_id": getattr(order, 'original_order', None),
            "customer_info": customer_info,
            "deliveryman_info": deliveryman_info,
            "order_status": getattr(order, 'status', 'N/A'),
            "total_price": str(getattr(order, 'total_price', 0)),
            "order_date": getattr(order, 'order_date', None),
            "order_items": order_items_data
        }
        order_list.append(order_entry)

    return JsonResponse({"success": True, "data": order_list}, status=200)