from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from datetime import datetime

class Merchant(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='merchant_profile')
    company_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, validators=[RegexValidator(
        regex=r'^(?:((98|97|96)\d{8})|(0\d{2,3}\d{6}))$',
        message="Enter a valid Nepali mobile or landline number"
    )])



class AppUser(models.Model):  # renamed to avoid conflict with Django's User
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, validators=[phone_validator])
    address = models.TextField()

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class Restaurant(models.Model):
    store_name = models.CharField(max_length=255)
    store_contact_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=15, validators=[phone_validator])
    secondary_contact_number = models.CharField(max_length=15, validators=[phone_validator], blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    store_address = models.TextField(blank=True, null=True)
    cuisine = models.CharField(max_length=100, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.store_name} - {self.city or 'No city'}"


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


class DeliveryPersonnel(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, validators=[phone_validator])
    vehicle_type = models.CharField(max_length=50)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    current_order = models.OneToOneField(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_personnel')

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
