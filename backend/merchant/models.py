from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


class Merchant(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='merchant_profile')
    company_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, validators=[RegexValidator(
        regex=r'^(?:((98|97|96)\d{8})|(0\d{2,3}\d{6}))$',
        message="Enter a valid Nepali mobile or landline number"
    )])


class Restaurant:
    def __init__(self, restaurant_id, store_name, store_contact_name, contact_number, secondary_contact_number=None, city=None, store_address=None, cuisine=None, latitude=None, longitude=None):
        self.restaurant_id = restaurant_id
        self.store_name = store_name
        self.store_contact_name = store_contact_name
        self.contact_number = contact_number
        self.secondary_contact_number = secondary_contact_number
        self.city = city
        self.store_address = store_address
        self.cuisine = cuisine
        self.latitude = latitude
        self.longitude = longitude

    def __str__(self):
        info = f"Restaurant ID: {self.restaurant_id}, Store Name: {self.store_name}, Contact: {self.store_contact_name} ({self.contact_number})"
        if self.secondary_contact_number:
            info += f", Secondary Contact: {self.secondary_contact_number}"
        if self.city:
            info += f", City: {self.city}"
        if self.store_address:
            info += f", Address: {self.store_address}"
        if self.cuisine:
            info += f", Cuisine: {self.cuisine}"
        if self.latitude is not None and self.longitude is not None:
            info += f", Location: ({self.latitude}, {self.longitude})"
        return info

class FoodItem:
    def __init__(self, item_id, name, description, price, restaurant_id):
        self.item_id = item_id
        self.name = name
        self.description = description
        self.price = price
        self.restaurant_id = restaurant_id

    def __str__(self):
        return f"Item ID: {self.item_id}, Name: {self.name}, Price: Rs. {self.price:.2f} (Restaurant ID: {self.restaurant_id})"

class Order:
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]

    def __init__(self, order_id, user_id, restaurant_id, order_date=None, status='PENDING'):
        self.order_id = order_id
        self.user_id = user_id
        self.restaurant_id = restaurant_id
        self.order_date = order_date if order_date else datetime.now()
        self.status = status
        self.items = []

    def add_item(self, food_item, quantity=1):
        self.items.append({'item': food_item, 'quantity': quantity})

    def calculate_total(self):
        total = 0
        for item_data in self.items:
            total += item_data['item'].price * item_data['quantity']
        return total

    def __str__(self):
        item_details = "\n  - ".join([f"{item['item'].name} (x{item['quantity']})" for item in self.items])
        return (f"Order ID: {self.order_id}, User ID: {self.user_id}, Restaurant ID: {self.restaurant_id}, "
                f"Date: {self.order_date.strftime('%Y-%m-%d %H:%M:%S')}, Status: {self.status}\n"
                f"Items:\n  - {item_details}\n"
                f"Total: Rs. {self.calculate_total():.2f}")

class DeliveryPersonnel:
    def __init__(self, personnel_id, name, phone_number, vehicle_type, latitude=None, longitude=None, current_order_id=None):
        self.personnel_id = personnel_id
        self.name = name
        self.phone_number = phone_number
        self.vehicle_type = vehicle_type
        self.latitude = latitude
        self.longitude = longitude
        self.current_order_id = current_order_id

    def assign_order(self, order_id):
        self.current_order_id = order_id

    def unassign_order(self):
        self.current_order_id = None

    def __str__(self):
        status = f"Currently assigned to Order ID: {self.current_order_id}" if self.current_order_id else "Currently available"
        location_str = f"Location: ({self.latitude}, {self.longitude})" if self.latitude is not None and self.longitude is not None else "Location: (Not Available)"
        return f"Personnel ID: {self.personnel_id}, Name: {self.name}, {location_str}, Status: {status}"

class Delivery:
    STATUS_CHOICES = [
        ('ASSIGNED', 'Assigned'),
        ('PICKED_UP', 'Picked Up'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
    ]

    def __init__(self, delivery_id, order_id, personnel_id, delivery_address, assigned_time=None, status='ASSIGNED'):
        self.delivery_id = delivery_id
        self.order_id = order_id
        self.personnel_id = personnel_id
        self.delivery_address = delivery_address
        self.assigned_time = assigned_time if assigned_time else datetime.now()
        self.status = status
        self.delivery_time = None


    def mark_as_picked_up(self):
        self.status = 'PICKED_UP'

    def mark_as_in_transit(self):
        self.status = 'IN_TRANSIT'

    def mark_as_delivered(self):
        self.status = 'DELIVERED'
        self.delivery_time = datetime.now()

    def mark_as_failed(self):
        self.status = 'FAILED'
        self.delivery_time = datetime.now()

    def __str__(self):
        delivery_time_str = self.delivery_time.strftime('%Y-%m-%d %H:%M:%S') if self.delivery_time else 'Not yet delivered'
        return (f"Delivery ID: {self.delivery_id}, Order ID: {self.order_id}, Personnel ID: {self.personnel_id}, "
                f"Delivery Address: {self.delivery_address}, Assigned Time: {self.assigned_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"Status: {self.status}, Delivery Time: {delivery_time_str}")
