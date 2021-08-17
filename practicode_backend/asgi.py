"""
ASGI config for practicode_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from django.urls import resolve
from practicode_backend.websocket import WebSocket

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'practicode_backend.settings')

django_http_application = get_asgi_application()

async def application(scope, receive, send):
    if scope['type'] == 'http':
        await django_http_application(scope, receive, send)

    elif scope['type'] == 'websocket':
        handler = resolve(scope['raw_path'])
        await handler.func(WebSocket(scope, receive, send), *handler.args, **handler.kwargs)

    else:
        raise NotImplementedError(f"Unknown scope type {scope['type']}")
