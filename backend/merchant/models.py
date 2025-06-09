from django.utils import timezone
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from datetime import datetime

# Validator for Nepali phone numbers
phone_validator = RegexValidator(
    regex=r'^(?:((98|97|96)\d{8})|(0\d{2,3}\d{6}))$',
    message="Enter a valid Nepali mobile or landline number"
)

vehicle_validator = RegexValidator(
    regex=(
        r'^(?:'
        r'[A-Z]{1,2}\s?\d{1,2}\s?[A-Z]{1,2}\s?\d{1,4}'
        r'|\d{1,2}-\d{1,2}-[A-Za-z]{1,3}-\d{1,4}'
        r')$'
    ),
    message="Enter a valid vehicle number"
)

class Merchant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='merchant_profile')
    phone_number = models.CharField(max_length=15, validators=[phone_validator])
    name = models.CharField(max_length=250, null=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class AppUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='appuser_profile', null=True)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, validators=[phone_validator])
    address = models.TextField()

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class Cuisine(models.Model):
    cuisine_name = models.CharField(max_length=100)

    def __str__(self):
        return self.cuisine_name


class Restaurant(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='restaurant_profile', null=True)
    restaurant_name = models.CharField(max_length=100, default='')
    vat_and_tax = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    restaurant_address = models.TextField(default='')
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    cuisine = models.CharField(max_length=50, default='')
    profile_picture = models.ImageField(upload_to='restaurant/profile_pics/', blank=True, null=True)
    cover_photo = models.ImageField(upload_to='restaurant/cover_photos/', blank=True, null=True)
    owner_name = models.CharField(max_length=100, default='')
    owner_contact = models.CharField(max_length=15, null=True, validators=[phone_validator])
    menu = models.FileField(upload_to='restaurant/menus/', null=True)
    BUSINESS_PLAN_CHOICES = [
        ('commission', 'Commission Base'),
        ('subscription', 'Subscription Base'),
    ]
    business_plan = models.CharField(max_length=20, choices=BUSINESS_PLAN_CHOICES, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return self.restaurant_name


class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_items')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=7, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    is_available = models.BooleanField(default=True)
    image = models.ImageField(upload_to='food_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.name} - Rs. {self.price:.2f}"


class FoodItem(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.FloatField()
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='food_items')

    def __str__(self):
        return f"{self.name} - Rs. {self.price:.2f}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]

    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name='orders')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='orders')
    deliveryman = models.ForeignKey('Deliveryman', on_delete=models.SET_NULL, null=True, related_name='orders')
    order_date = models.DateTimeField(default=datetime.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    def calculate_total(self):
        return sum(item.food_item.price * item.quantity for item in self.items.all())

    def __str__(self):
        return f"Order #{self.pk} by {self.user.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.food_item.name} x{self.quantity}"


class DeliveryPersonnel(models.Model):   #to record and transmit the real-time info of the delivery man
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, validators=[phone_validator])
    vehicle_type = models.CharField(max_length=50)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    current_order = models.OneToOneField(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_personnel')
    deliveryman_profile = models.OneToOneField('Deliveryman',on_delete=models.CASCADE,related_name='personnel_record')

    def __str__(self):
        status = f"Assigned to Order #{self.current_order.pk}" if self.current_order else "Available"
        return f"{self.name} - {status}"


class Delivery(models.Model):
    STATUS_CHOICES = [
        ('ASSIGNED', 'Assigned'),
        ('PICKED_UP', 'Picked Up'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    personnel = models.ForeignKey(DeliveryPersonnel, on_delete=models.SET_NULL, null=True, related_name='deliveries')
    delivery_address = models.TextField()
    assigned_time = models.DateTimeField(default=datetime.now)
    delivery_time = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ASSIGNED')

    def __str__(self):
        return f"Delivery #{self.pk} - Status: {self.status}"

    class Meta:
        verbose_name_plural = "Deliveries"


class Deliveryman(models.Model):    #to record the offficial details about the delivery man
    VEHICLE_CHOICES = [
        ('Scooter', 'Scooter'),
        ('Bike', 'Bike'),
    ]
    IDENTITY_CHOICES = [
        ('Citizenship', 'Citizenship'),
        ('Driving License', 'Driving License'),
    ]
    DELIVERY_TYPE_CHOICES = [
        ('Salarybased', 'Salarybased'),
    ]
    ZONE_CHOICES = [
        ('Kathmandu', 'Kathmandu'),
        ('Bhaktapur', 'Bhaktapur'),
        ('Lalitpur', 'Lalitpur'),
    ]
    DUTYTIME_CHOICES = [
    ('morning', 'Morning (6AM–10AM)'),
    ('late_morning', 'Late Morning (10AM–2PM)'),
    ('afternoon', 'Afternoon (2PM–6PM)'),
    ('evening', 'Evening (6PM–10PM)'),
    ('night', 'Night (10PM–2AM)'),
    ('late_night', 'Late Night (2AM–6AM)'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deliveryman_profile', null=True)
    Firstname = models.CharField(max_length=100)
    Lastname = models.CharField(max_length=100)
    Email = models.EmailField(unique=True)
    DeliveryType = models.CharField(max_length=20, blank=False, choices=DELIVERY_TYPE_CHOICES)
    Zone = models.CharField(max_length=20, blank=False, choices=ZONE_CHOICES)
    Vehicle = models.CharField(max_length=20, blank=False, choices=VEHICLE_CHOICES)
    IdentityType = models.CharField(choices=IDENTITY_CHOICES, blank=False, null=True)
    IdentityNumber = models.CharField(max_length=30, blank=False)
    IdentityImage = models.ImageField(upload_to='identity_images/')
    PanNumber = models.CharField(
        max_length=9,
        validators=[
            RegexValidator(
                regex=r'^\d{9}$',
                message='Enter a valid 9-digit PAN number'
            )
        ],
        help_text='Enter a 9-digit PAN number issued by IRD Nepal.'
    )
    BillBookScanCopy = models.ImageField(upload_to='bill_book_images/')
    DutyTime = models.CharField(
    max_length=20,
    choices=DUTYTIME_CHOICES,
    default='morning',
    )

    VehicleNumber = models.CharField(max_length=13, validators=[vehicle_validator], help_text="Enter the vehicle number in capital letters (e.g., BA 2 PA 1234 or 3-01-Pa-1234).", null=True)
    DateofBirth = models.DateField()
    UserImage = models.ImageField(upload_to='user_images/')
    created_at = models.DateTimeField(default=timezone.now)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.Firstname} {self.Lastname}'


class DeliveryStatus(models.Model):
    STATUS_CHOICES = [
        ('ASSIGNED', 'Assigned'),
        ('PICKED_UP', 'Picked Up'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_status')
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    deliveryman = models.ForeignKey(DeliveryPersonnel, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ASSIGNED')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.order.id} - {self.status}"
