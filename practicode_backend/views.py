from django.http import HttpResponse
from django.http import JsonResponse
from django.template import loader, Template
import os
from typing import Tuple
import pybase64 as base64


def parse_task(tmpl: Template) -> Tuple[str, str, str, str, str]: # returns [title, text, task_template, lang, source_code]
    # NOTE: this function is intentially NOT good, it will be replaced with mongodb I guess
    full_text = tmpl.render(None).strip(" \n\t")

    if full_text.startswith("<!--"):
        full_text = full_text[len("<!--"):].strip("\n")

    i1 = full_text.find("-->")
    if i1 == -1:
        raise RuntimeError("couldn't find enclosing tag '-->' for params in the template text")

    params_text = full_text[:i1-1]
    params = eval(params_text)

    full_text = full_text[i1+len("-->"):]
    full_text = full_text.strip(" \n")

    i2 = full_text.find("<!--")
    if i2 == -1:
        raise RuntimeError("couldn't find opening tag '<!--' for code in the template text")
    code = full_text[i2+len("<!--"):]
    if code.endswith("-->"):
        code = code[:len(code)-len("-->")].strip("\n")

    text = full_text[:i2-1]
    return params["title"], text, params["task_template"], params["lang"], code


def get_task(request, task_id):
    tmpl = loader.get_template('tasks/' + task_id + '.html')

    title, text, task_template, lang, source_code = parse_task(tmpl)
    resp = {
        "title": title,
        "text": base64.b64encode(text.encode('utf-8')).decode('ascii'),
        "task_template": task_template,
        "lang": lang,
        "code": [
            {
                "file": "src0",
                "text": base64.b64encode(source_code.encode('utf-8')).decode('ascii'),
            },
        ],
    }
    return JsonResponse(resp)


def runner(request):
    return JsonResponse({
        'RUNNER_WEBSOCKET_URL': 'ws://' + os.getenv('RUNNER_HOST', 'localhost:8000') + '/run',
    })
