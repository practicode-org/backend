from django.http import HttpResponse
from django.http import JsonResponse
from django.template import loader
import os


def index(request, task_id):
    tmpl = loader.get_template('tasks/' + task_id + '.html')
    return HttpResponse(tmpl.render(None, request))


def info(request):
    # For debugging TODO REMOVE
    server_info = {
        'HOSTNAME': os.getenv('HOSTNAME'),
        'PRACTICODE_RUNJAIL_WEBSOCKET': os.getenv('PRACTICODE_RUNJAIL_WEBSOCKET')
    }
    return JsonResponse(server_info)


def runjail(request):
    return JsonResponse({'RUNJAIL_WEBSOCKET': os.getenv('PRACTICODE_RUNJAIL_WEBSOCKET')})
