from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework import serializers
from merchant.models import FoodItem, Restaurant, Order, FoodOrderCount, Cart, OrderItem, Deliveryman
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.apps import apps
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

User = get_user_model()


class AppUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name')


# Validator for Nepali phone numbers
phone_validator = RegexValidator(
    regex=r'^(?:((98|97|96)\d{8})|(0\d{2,3}\d{6}))$',
    message="Enter a valid Nepali mobile or landline number"
)


class RegisterSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    phone = serializers.CharField(
        write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "password", "phone")

    def validate_phone(self, value):
        """
        Validate phone with Nepali phone regex. Allow empty/blank.
        """
        if value in (None, ''):
            return value
        try:
            phone_validator(value)
        except DjangoValidationError:
            raise serializers.ValidationError(
                "Enter a valid Nepali phone number.")
        return value

    def validate_email(self, value):
        """
        Ensure email is unique (case-insensitive). Normalize to lower-case.
        """
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with that email already exists.")
        return value.lower()

    def create(self, validated_data):
        full_name = validated_data.pop("full_name")
        email = validated_data["email"]
        password = validated_data["password"]
        phone = validated_data.pop("phone", None)

        # generate unique username from email prefix
        base_username = email.split("@")[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # wrap create in transaction to reduce race conditions
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, email=email, password=password
                )
                # store full name in first_name (as in your original code)
                user.first_name = full_name
                user.save()
        except IntegrityError:
            # If a DB-level unique constraint exists and race happened, surface friendly error
            raise serializers.ValidationError(
                {"email": ["A user with that email already exists."]})

        # attempt to save phone to Merchant or Customer profile if available
        Merchant = None
        Customer = None
        try:
            Merchant = apps.get_model("merchant", "Merchant")
        except Exception:
            Merchant = None

        try:
            Customer = apps.get_model("merchant", "Customer")
        except Exception:
            Customer = None

        def _set_field_if_exists(inst, field_name, value):
            if not inst or value is None:
                return False
            if hasattr(inst, field_name):
                try:
                    setattr(inst, field_name, value)
                    inst.save()
                    return True
                except Exception:
                    return False
            return False

        saved = False
        if phone:
            if Merchant:
                try:
                    merchant_profile, created = Merchant.objects.get_or_create(
                        user=user)
                    if _set_field_if_exists(merchant_profile, "phone_number", phone):
                        saved = True
                except Exception:
                    saved = False

            if not saved and Customer:
                try:
                    customer_profile, created = Customer.objects.get_or_create(
                        user=user)
                    if (_set_field_if_exists(customer_profile, "phone", phone) or
                            _set_field_if_exists(customer_profile, "phone_number", phone)):
                        saved = True
                except Exception:
                    saved = False

        return user


class EmailAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.")

        user = authenticate(username=user.username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")

        attrs['user'] = user
        return attrs


class FooditemSerial(serializers.ModelSerializer):
    class Meta:
        model = FoodItem
        fields = '__all__'


class RestaurantSerial(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = '__all__'


class Orderserializer(serializers.ModelSerializer):
    cart_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Order
        fields = ['cart_id', 'user', 'restaurant', 'food_item',
                  'quantity', 'is_transited', 'total_price']


class CartSerializer(serializers.ModelSerializer):
    cart_id = serializers.IntegerField(
        read_only=True)  # uses AutoField from model

    class Meta:
        model = Cart
        fields = [
            'cart_id',
            'user',
            'restaurant',
            'food_item',
            'quantity',
            'total_price',
            'checked',
        ]


class CartReadSerializer(serializers.ModelSerializer):
    cart_id = serializers.IntegerField(
        read_only=True)  # uses AutoField from model
# i am going to cnange
    food_item = FooditemSerial(read_only=True)
    restaurant = RestaurantSerial(read_only=True)

    class Meta:
        model = Cart
        fields = [
            'cart_id',
            'user',
            'restaurant',
            'food_item',
            'quantity',
            'total_price',
            'checked',
        ]


class FoodOrderCountSerializer(serializers.ModelSerializer):
    food_item = FooditemSerial(read_only=True)

    class Meta:
        model = FoodOrderCount
        fields = ['food_item']


class OrderItemSerializer(serializers.ModelSerializer):
    food_item_name = serializers.CharField(
        source='food_item.name', read_only=True)
    restaurant_name = serializers.CharField(
        source='food_item.restaurant.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'food_item', 'food_item_name',
                  'restaurant_name', 'quantity', 'total_price']
        read_only_fields = ['id', 'total_price']


class PlaceOrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(
        many=True, read_only=True, source='orderitem_set')
    restaurant_name = serializers.CharField(
        source='restaurant.name', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'restaurant', 'restaurant_name',
                  'order_items', 'total_price', 'order_date', 'status']
        read_only_fields = ['id', 'order_date', 'status']


class Restaurantlistserial(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = [
            'restaurant_name',
            'cuisine',
            'restaurant_address',
            'profile_picture',
            'menu',
            'review_rating'
        ]


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        read_only_fields = fields


class RestaurantDetailSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    profile_picture = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    menu = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = [
            'id',
            'user',
            'restaurant_name',
            'owner_name',
            'owner_email',
            'owner_contact',
            'restaurant_address',
            'latitude',
            'longitude',
            'cuisine',
            'description',
            'restaurant_type',
            'profile_picture',
            'cover_photo',
            'menu',
            'created_at',
            'approved',
        ]
        read_only_fields = fields

    def _abs_url(self, val):
        request = self.context.get('request')
        if not val:
            return None
        try:
            url = getattr(val, 'url', str(val))
            if request:
                return request.build_absolute_uri(url)
            return url
        except Exception:
            return None

    def get_profile_picture(self, obj):
        return self._abs_url(obj.profile_picture)

    def get_cover_photo(self, obj):
        return self._abs_url(obj.cover_photo)

    def get_menu(self, obj):
        return self._abs_url(obj.menu)


class OrderItemDetailSerializer(serializers.ModelSerializer):
    food_item_name = serializers.CharField(
        source='food_item.name', read_only=True)
    restaurant_name = serializers.CharField(
        source='food_item.restaurant.restaurant_name', read_only=True)
    food_item_image = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'food_item', 'food_item_name', 'restaurant_name',
                  'food_item_image', 'quantity', 'price_at_order', 'total_price']
        read_only_fields = ['id', 'food_item_image', 'total_price']

    def _abs_url(self, val):
        request = self.context.get('request')
        if not val:
            return None
        try:
            url = getattr(val, 'url', str(val))
            if request:
                return request.build_absolute_uri(url)
            return url
        except Exception:
            return None

    def get_food_item_image(self, obj):
        fi = getattr(obj, 'food_item', None)
        if not fi:
            return None
        if getattr(fi, 'profile_picture', None):
            return self._abs_url(fi.profile_picture)
        if getattr(fi, 'external_image_url', None):
            return fi.external_image_url
        return None

    def get_total_price(self, obj):
        price = obj.price_at_order if obj.price_at_order is not None else getattr(
            obj.food_item, 'price', None)
        price = price or Decimal('0.00')
        return price * obj.quantity


class DeliverymanSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()

    class Meta:
        model = Deliveryman
        fields = ['id', 'full_name', 'email', 'phone']

    def get_full_name(self, obj):
        return f"{getattr(obj, 'Firstname', '')} {getattr(obj, 'Lastname', '')}".strip()

    def get_email(self, obj):
        user = getattr(obj, 'user', None)
        return getattr(user, 'email', None) if user else None

    def get_phone(self, obj):
        user = getattr(obj, 'user', None)
        return getattr(user, 'phone', None) if user else None

class OrderWithItemsSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='id', read_only=True)
    restaurant_id = serializers.IntegerField(
        source='restaurant.id', read_only=True)
    restaurant = RestaurantDetailSerializer(read_only=True)
    order_items = OrderItemDetailSerializer(many=True, read_only=True)
    user = UserBriefSerializer(read_only=True)
    deliveryman = DeliverymanSerializer(read_only=True)  # Added field
    delivery_charge = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_id',
            'user',
            'deliveryman',  # Added
            'restaurant_id',
            'restaurant',
            'is_transited',
            'delivery_charge',
            'total_price',
            'order_items',
            'order_date',
            'status',
            'payment_method',
            'latitude',
            'longitude',
        ]
        read_only_fields = ['order_id', 'user', 'deliveryman', 'restaurant_id', 'restaurant',
                            'delivery_charge', 'total_price', 'order_items', 'order_date']
