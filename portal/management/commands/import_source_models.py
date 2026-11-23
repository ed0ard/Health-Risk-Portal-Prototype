from datetime import date

import joblib
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from portal.models import Fit, Record
from django.db.models import Min, Max


class Command(BaseCommand):
    help = "Register the supplied model files."

    @transaction.atomic
    def handle(self,*args,**options):
        span=Record.objects.aggregate(start=Min('day'),end=Max('day'))
        for i,kind in enumerate(("hbp","depre","age"),1):
            path=f"data/source/model/model_{i}.pkl"
            if Fit.objects.filter(artifact__path=path).exists():
                continue
            payload=joblib.load(settings.BASE_DIR/path)
            model=payload["model"]
            metadata={"engine":"source","path":path,"form_version":"legacy","feature_names":payload["feature_names"]}
            if kind=="age": metadata["variance"]=model.explained_variance_ratio_.tolist()
            else: metadata["classes"]=payload.get("classes", model.classes_.tolist())
            Fit.objects.create(kind=kind,start=span['start'] or date(2023,1,1),end=span['end'] or date(2026,1,1),
                               samples=0,artifact=metadata)
            self.stdout.write(f"Registered original {kind} model")
