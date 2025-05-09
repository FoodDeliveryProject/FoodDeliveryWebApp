from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from datetime import datetime

# Validator for Nepali phone numbers
phone_validator = RegexValidator(
    regex=r'^(?:((98|97|96)\d{8})|(0\d{2,3}\d{6}))$',
    message="Enter a valid Nepali mobile or landline number"
)


class Merchant(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='merchant_profile')
    phone_number = models.CharField(
        max_length=15, validators=[phone_validator])
    name = models.CharField(max_length=250, null=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class AppUser(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(
        max_length=15, validators=[phone_validator])
    address = models.TextField()

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class Cuisine(models.Model):
    cuisine_name = models.CharField(max_length=100)

    def __str__(self):
        return self.cuisine_name


class Restaurant(models.Model):
    restaurant_name = models.CharField(max_length=255, null=True)
    restaurant_contact_name = models.CharField(max_length=255, null=True)
    contact_number = models.CharField(
        max_length=15, validators=[phone_validator])
    secondary_contact_number = models.CharField(
        max_length=15, validators=[phone_validator], blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    restaurant_address = models.TextField(blank=True, null=True)
    cuisine = models.ForeignKey(
        Cuisine, on_delete=models.CASCADE, related_name='cuisine', default="Nepali")
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.restaurant_name} - {self.city or 'No city'}"


class FoodItem(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.FloatField()
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='food_items')

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

    user = models.ForeignKey(
        AppUser, on_delete=models.CASCADE, related_name='orders')
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='orders')
    order_date = models.DateTimeField(default=datetime.now)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDING')

    def calculate_total(self):
        return sum(item.food_item.price * item.quantity for item in self.items.all())

    def __str__(self):
        return f"Order #{self.pk} by {self.user.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.food_item.name} x{self.quantity}"


class DeliveryPersonnel(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(
        max_length=15, validators=[phone_validator])
    vehicle_type = models.CharField(max_length=50)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    current_order = models.OneToOneField(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_personnel')

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

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name='delivery')
    personnel = models.ForeignKey(
        DeliveryPersonnel, on_delete=models.SET_NULL, null=True, related_name='deliveries')
    delivery_address = models.TextField()
    assigned_time = models.DateTimeField(default=datetime.now)
    delivery_time = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ASSIGNED')

    def __str__(self):
        return f"Delivery #{self.pk} - Status: {self.status}"

    class Meta:
        verbose_name_plural = "Deliveries"
        
class DeliveryVehicle(models.Model):
    VEHICLE_CHOICES = [
        ('Scooter', 'Scooter'),
        ('Bike', 'Bike'),
    ]
    IDENTITY_CHOICES = [
        ('Passport', 'Passport'),
        ('Citizenship', 'Citizenship'),
        ('Driving License', 'Driving License'),
    ]
    Vehicletype=models.CharField(choices=VEHICLE_CHOICES)
    VehicleDocuments=models.CharField(choices=IDENTITY_CHOICES)
    VehicleNumberplate=models.CharField(max_length=13)

class Deliveryman(models.Model):
    DeliveryType_choice = [
        ('Freelance', 'Freelancer'),
        ('Salarybased', 'Salarybased'),
    ]
    Zone_choice = [
        ('Kathmandu', 'Kathmandu'),
        ('Bhaktapur', 'Bhaktapur'),
        ('Lalitpur', 'Lalitpur'),
    ]
    Dutytime_choices = [
        ('day', 'Day(10AM-6PM)'),
        ('night', 'Night(6PM-2AM)'),
    ]

    Firstname = models.CharField(max_length=100)
    Lastname = models.CharField(max_length=100)
    Email = models.EmailField()
    DeliveryType = models.CharField(max_length=20, choices=DeliveryType_choice)
    Zone = models.CharField(max_length=20, choices=Zone_choice)
    Vehicle = models.ForeignKey(DeliveryVehicle, on_delete=models.CASCADE, related_name='deliverymen')
    IdentityNumber = models.CharField(max_length=10)
    IdentityImage = models.ImageField(upload_to='identities/')
    PanNumber = models.CharField(max_length=9)
    DutyTime = models.CharField(max_length=20, choices=Dutytime_choices)
    DateofBirth = models.DateField()
    UserImage = models.ImageField(upload_to='users/')

    def __str__(self):
        return f"{self.Firstname} {self.Lastname} - {self.Zone}"

