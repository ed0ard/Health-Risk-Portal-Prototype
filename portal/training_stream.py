import json
import logging
from queue import Queue
from threading import Thread

from django.db import close_old_connections, transaction
from django.http import StreamingHttpResponse
from django.urls import reverse

from .learning import train
from .models import Activity


def stream_training(request,kind,start,end,validate,method):
    events = Queue()
    actor_id = request.user.pk

    def worker():
        close_old_connections()
        try:
            fit = train(kind,start,end,validate,method,lambda value: events.put({"progress":value}))
            Activity.objects.create(actor_id=actor_id,event="training",subject=kind)
            events.put({"progress":100,"url":reverse("portal",args=["training"])+f"?model={kind}&completed={fit.pk}"})
        except ValueError as error:
            events.put({"error":str(error)})
        except Exception:
            logging.getLogger(__name__).exception("Training failed")
            events.put({"error":"failed"})
        finally:
            close_old_connections()
            events.put(None)

    def chunks():
        Thread(target=worker,daemon=True).start()
        while True:
            event = events.get()
            if event is None:
                break
            yield json.dumps(event)+"\n"

    response=StreamingHttpResponse(chunks(),content_type="application/x-ndjson")
    response["Cache-Control"]="no-store"
    response["X-Accel-Buffering"]="no"
    return response
