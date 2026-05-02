from django.urls import re_path
from . import consumers

# This is the variable your asgi.py file is trying to import!
websocket_urlpatterns = [
    re_path(r'ws/status/$', consumers.StatusConsumer.as_asgi()),
    # The URL will look like: ws://127.0.0.1:8000/ws/chat/<conversation_id>/
    re_path(r'ws/chat/(?P<conversation_id>\w+)/$', consumers.ChatConsumer.as_asgi()),

    re_path(r"ws/call/(?P<conversation_id>\w+)/$", consumers.CallConsumer.as_asgi()),
]