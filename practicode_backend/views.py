from django.http import HttpResponse
from django.template import loader

def index(request, task_id):
    tmpl = loader.get_template('tasks/' + task_id + '.html')
    return HttpResponse(tmpl.render(None, request))
