from django.http import HttpResponse
from django.http import JsonResponse
from django.template import loader
import os


def index(request, task_id):
    tmpl = loader.get_template('tasks/' + task_id + '.html')
    return HttpResponse(tmpl.render(None, request))


def runner(request):
    return JsonResponse({'RUNNER_WEBSOCKET_URL': 'ws://' + os.getenv('RUNNER_HOST') + '/run'})
