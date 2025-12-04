import re
from django.utils import timezone
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction

# Validator for Nepali phone numbers
phone_validator = RegexValidator(
    regex=r'^(?:((98|97|96)\d{8})|(0\d{2,3}\d{6}))$',
    message="Enter a valid Nepali mobile or landline number"
)

vehicle_validator = RegexValidator(
    regex=(
        r'^(?:'
        r'[A-Z]{1,2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,2}[-\s]?\d{1,4}'
        r'|\d{1,2}-\d{1,2}-[A-Z]{1,3}-\d{1,4}'
        r')$'
    ),
    message="Enter a valid vehicle number (e.g. 'BA 01 PA 1234', 'BA-07-PA-1234', or '3-01-PA-1234').",
    flags=re.IGNORECASE
)


class Merchant(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='merchant_profile')
    phone_number = models.CharField(
        max_length=15, validators=[phone_validator])
    name = models.CharField(max_length=250, null=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class Customer(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='user_profile')
    profile_picture = models.ImageField(
        upload_to='user_images/', blank=True, null=True)
    phone_number = models.CharField(
        max_length=15, blank=True, null=True)  # Add this

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Cuisine(models.Model):
    cuisine_name = models.CharField(max_length=100)

    def __str__(self):
        return self.cuisine_name


class Restaurant(models.Model):
    RESTAURANT_TYPE_CHOICES = [
        ('local', 'Local'),
        ('fine_dining', 'Fine Dining'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='restaurant_profile', null=True
    )
    restaurant_name = models.CharField(max_length=100, default='')
    owner_name = models.CharField(max_length=100, default='')
    owner_email = models.EmailField(max_length=255, null=True, blank=True)
    owner_contact = models.CharField(
        max_length=15, null=True, validators=[phone_validator]
    )
    restaurant_address = models.TextField(default='')
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    cuisine = models.CharField(max_length=50, default='')
    description = models.TextField(null=True, blank=True)
    restaurant_type = models.CharField(
        max_length=20, choices=RESTAURANT_TYPE_CHOICES, default='local'
    )
    profile_picture = models.ImageField(
        upload_to='restaurant/profile_pics/', blank=True, null=True)
    cover_photo = models.ImageField(
        upload_to='restaurant/cover_photos/', blank=True, null=True)
    menu = models.FileField(
        upload_to='restaurant/menus/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return self.restaurant_name


class FoodItem(models.Model):
    AVAILABILITY_CHOICES = [
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('LOW_STOCK', 'Low Stock'),
        ('AVAILABLE', 'Available'),
    ]

    VEG_NONVEG_CHOICES = [
        ('veg', 'Vegetarian'),
        ('nonveg', 'Non-Vegetarian'),
    ]

    RATING_CHOICES = [
        (0, '0'),
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '5'),
    ]

    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=7, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    description = models.TextField(blank=True)
    restaurant = models.ForeignKey(
        'Restaurant', on_delete=models.CASCADE, related_name='food_items')
    veg_nonveg = models.CharField(
        max_length=6, choices=VEG_NONVEG_CHOICES, default='veg')
    profile_picture = models.ImageField(
        upload_to='food_images/', blank=True, null=True)
    external_image_url = models.URLField(blank=True, null=True)
    availability_status = models.CharField(
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default='AVAILABLE'
    )
    review_rating = models.IntegerField(
        choices=RATING_CHOICES,
        null=True,
        blank=True,
        help_text="Rate the food item from 0 to 5"
    )

    def __str__(self):
        return f"{self.name} - Rs. {self.price:.2f}"


class Deliveryman(models.Model):
    VEHICLE_CHOICES = [
        ('Scooter', 'Scooter'),
        ('Bike', 'Bike'),
    ]
    ZONE_CHOICES = [
        ('Kathmandu', 'Kathmandu'),
        ('Bhaktapur', 'Bhaktapur'),
        ('Lalitpur', 'Lalitpur'),
    ]
    DUTYTIME_CHOICES = [
        ('day', 'Day (10AM-6PM)'),
        ('night', 'Night (6PM-2AM)'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='deliveryman_profile', null=True)
    Firstname = models.CharField(max_length=100)
    Lastname = models.CharField(max_length=100)
    Address = models.CharField(max_length=255, null=True)
    Vehicle = models.CharField(
        max_length=20, blank=False, choices=VEHICLE_CHOICES)
    Zone = models.CharField(max_length=20, blank=False, choices=ZONE_CHOICES)
    PanNumber = models.CharField(
        max_length=9,
        validators=[
            RegexValidator(
                regex=r'^\d{9}$', message='Enter a valid 9-digit PAN number')
        ],
        help_text='Enter a 9-digit PAN number issued by IRD Nepal.'
    )
    BillBookScanCopy = models.FileField(upload_to='bill_book_files/')
    DutyTime = models.CharField(
        max_length=10, blank=False, choices=DUTYTIME_CHOICES)
    VehicleNumber = models.CharField(
        null=True,
        max_length=13,
        validators=[vehicle_validator],
        help_text="Enter the vehicle number in capital letters (e.g., BA 2 PA 1234 or 3-01-Pa-1234)."
    )
    DateofBirth = models.DateField()
    UserImage = models.ImageField(upload_to='user_images/')
    created_at = models.DateTimeField(default=timezone.now)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.Firstname} {self.Lastname}'


class Cart(models.Model):
    cart_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    restaurant = models.ForeignKey(
        'Restaurant',
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    food_item = models.ForeignKey(
        'FoodItem',
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total price for this cart item"
    )
    created_at = models.DateTimeField(default=timezone.now)
    checked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        unique_together = ['user', 'restaurant', 'food_item']

    def clean(self):
        if self.food_item and self.restaurant:
            if self.food_item.restaurant_id != self.restaurant_id:
                raise ValidationError({
                    'food_item': "This food item does not belong to the selected restaurant."
                })
        if self.quantity < 1:
            raise ValidationError({'quantity': "Quantity must be at least 1."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.food_item:
            self.total_price = self.food_item.price * self.quantity
        with transaction.atomic():
            super().save(*args, **kwargs)

    def calculate_total(self):
        if self.food_item:
            return self.food_item.price * self.quantity
        return 0

    def update_total_price(self):
        self.total_price = self.calculate_total()
        self.save(update_fields=['total_price'])

    def __str__(self):
        return f"Cart: {self.user.username} - {self.food_item.name} x{self.quantity}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('WAITING_FOR_DELIVERY', 'Waiting for Deliviery'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    PAYMENT_CHOICES = [
        ('CashOnDelivery', 'CashOnDelivery'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='order_profile')
    restaurant = models.ForeignKey(
        'Restaurant', on_delete=models.CASCADE, related_name='orders')
    food_item = models.ManyToManyField(
        'FoodItem',
        through='OrderItem',
        related_name='orders',
        blank=True
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    is_transited = models.BooleanField(default=True)
    assigned = models.BooleanField(default=False)
    deliveryman = models.ForeignKey(
        'Deliveryman', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    order_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(
        max_length=50,
        choices=PAYMENT_CHOICES,
        default='CashOnDelivery'
    )
    customer_location = models.CharField(max_length=255, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-order_date']

    def calculate_total(self):
        total = Decimal('0.00')
        for oi in self.order_items.all():
            price_each = oi.price_at_order if oi.price_at_order is not None else oi.food_item.price
            total += (price_each or Decimal('0.00')) * oi.quantity
        return total

    def update_total_price(self):
        self.total_price = self.calculate_total()
        self.save(update_fields=['total_price'])

    def save(self, *args, **kwargs):
        self.is_transited = self.status in ['OUT_FOR_DELIVERY', 'DELIVERED']
        super().save(*args, **kwargs)

        def update_total():
            try:
                self.update_total_price()
            except Exception:
                pass
        transaction.on_commit(update_total)

    def __str__(self):
        return f"Order #{self.pk} by {self.user.get_full_name() or self.user.username}"


class OrderHistory(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='order_history')
    restaurant = models.ForeignKey(
        'Restaurant', on_delete=models.CASCADE, related_name='order_history')
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    deliveryman = models.ForeignKey(
        'Deliveryman', on_delete=models.SET_NULL, null=True, blank=True, related_name='order_history')
    order_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='DELIVERED')
    payment_method = models.CharField(max_length=50, default='CashOnDelivery')
    customer_location = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    original_order = models.CharField(
        max_length=50, null=True, blank=True,
        help_text='ID of the original order from the Order table before deletion.'
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"OrderHistory #{self.pk} (User: {self.user.username if self.user else 'N/A'})"


class OrderItemHistory(models.Model):
    order_history = models.ForeignKey(
        OrderHistory, on_delete=models.CASCADE, related_name='order_items_history')
    food_item = models.ForeignKey(
        'FoodItem', on_delete=models.CASCADE, related_name='order_items_history')
    quantity = models.PositiveIntegerField(default=1)
    price_at_order = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Order Item History"
        verbose_name_plural = "Order Items History"

    def save(self, *args, **kwargs):
        if self.price_at_order is None:
            self.price_at_order = self.food_item.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.food_item.name} x{self.quantity} (OrderHistory #{self.order_history.pk})"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='order_items')
    # keep field named `food_item` here too — consistent naming
    food_item = models.ForeignKey(
        'FoodItem', on_delete=models.CASCADE, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    price_at_order = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def save(self, *args, **kwargs):
        if self.price_at_order is None:
            self.price_at_order = self.food_item.price
        super().save(*args, **kwargs)
        # update parent order total
        try:
            self.order.update_total_price()
        except Exception:
            pass

    def __str__(self):
        return f"{self.food_item.name} x{self.quantity} (Order #{self.order.pk})"


class FoodOrderCount(models.Model):
    food_item = models.OneToOneField(
        'FoodItem',
        on_delete=models.CASCADE,
        related_name='order_count'
    )
    no_of_orders = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Food Order Count"
        verbose_name_plural = "Food Order Counts"

    def __str__(self):
        return f"{self.food_item.name} - {self.no_of_orders} orders"

    def increment_count(self, quantity=1):
        """Helper method to increment order count"""
        self.no_of_orders += quantity
        self.save(update_fields=['no_of_orders', 'updated_at'])

    def reset_count(self):
        """Helper method to reset order count"""
        self.no_of_orders = 0
        self.save(update_fields=['no_of_orders', 'updated_at'])


# class DeliveryPersonnel(models.Model):
#     name = models.CharField(max_length=255)
#     phone_number = models.CharField(
#         max_length=15, validators=[phone_validator])
#     vehicle_type = models.CharField(max_length=50)
#     latitude = models.FloatField(blank=True, null=True)
#     longitude = models.FloatField(blank=True, null=True)
#     current_order = models.OneToOneField(
#         Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_personnel')
#     deliveryman_profile = models.OneToOneField(
#         'Deliveryman', on_delete=models.CASCADE, related_name='personnel_record', null=True)

#     def __str__(self):
#         status = f"Assigned to Order #{self.current_order.pk}" if self.current_order else "Available"
#         return f"{self.name} - {status}"


# class Delivery(models.Model):
#     STATUS_CHOICES = [
#         ('ASSIGNED', 'Assigned'),
#         ('PICKED_UP', 'Picked Up'),
#         ('IN_TRANSIT', 'In Transit'),
#         ('DELIVERED', 'Delivered'),
#         ('FAILED', 'Failed'),
#     ]

#     order = models.OneToOneField(
#         Order, on_delete=models.CASCADE, related_name='delivery')
#     personnel = models.ForeignKey(
#         DeliveryPersonnel, on_delete=models.SET_NULL, null=True, related_name='deliveries')
#     delivery_address = models.TextField()
#     assigned_time = models.DateTimeField(
#         default=timezone.now)  # Fixed: use timezone.now
#     delivery_time = models.DateTimeField(blank=True, null=True)
#     status = models.CharField(
#         max_length=20, choices=STATUS_CHOICES, default='ASSIGNED')

#     def __str__(self):
#         return f"Delivery #{self.pk} - Status: {self.status}"

#     class Meta:
#         verbose_name_plural = "Deliveries"

# class DeliveryStatus(models.Model):
#     STATUS_CHOICES = [
#         ('ASSIGNED', 'Assigned'),
#         ('PICKED_UP', 'Picked Up'),
#         ('IN_TRANSIT', 'In Transit'),
#         ('DELIVERED', 'Delivered'),
#         ('FAILED', 'Failed'),
#         ('CANCELLED', 'Cancelled'),
#     ]
#
#     order = models.OneToOneField(
#         Order, on_delete=models.CASCADE, related_name='delivery_status')
#     user = models.ForeignKey(AppUser, on_delete=models.CASCADE)
#     restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
#     deliveryman = models.ForeignKey(
#         DeliveryPersonnel, on_delete=models.SET_NULL, null=True, blank=True)
#     status = models.CharField(
#         max_length=20, choices=STATUS_CHOICES, default='ASSIGNED')
#     updated_at = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return f"Order #{self.order.id} - {self.status}"
class DeliverymanStatus(models.Model):
    deliveryman = models.OneToOneField(
        'Deliveryman',
        on_delete=models.CASCADE,
        related_name='status'
    )
    online = models.BooleanField(default=False)
    on_delivery = models.BooleanField(default=False)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.deliveryman.Firstname} {self.deliveryman.Lastname} - {'Online' if self.online else 'Offline'} - {'On Delivery' if self.on_delivery else 'Free'}"


class GoToDashClickCheck(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="go_to_dash_check")
    go_to_dash_clicked = models.BooleanField(default=False)


class DeliveryNotification(models.Model):
    deliveryman = models.ForeignKey(
        'merchant.Deliveryman',
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
    )
    order = models.ForeignKey(
        'merchant.Order',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ('deliveryman', 'order')
        indexes = [
            models.Index(fields=['deliveryman', 'order']),
        ]

    def __str__(self):
        return f"Notification entry: Order {self.order_id} -> Deliveryman {self.deliveryman_id}"
