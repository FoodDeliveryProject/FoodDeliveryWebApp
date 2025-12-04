from django.urls import re_path
from merchant.consumers import ChatConsumer, DeliverymanConsumer, ClientConsumer


websocket_urlpatterns = [
    re_path(r"ws/socket-server/(?P<restaurant_id>\d+)/$", ChatConsumer.as_asgi()),
    re_path(r"ws/deliveryman/(?P<deliveryman_id>\d+)/$", DeliverymanConsumer.as_asgi()),
    re_path(r"ws/client/(?P<order_id>\d+)/$", ClientConsumer.as_asgi())
]
