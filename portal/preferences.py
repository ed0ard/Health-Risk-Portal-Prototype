from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone

from .catalog import MODEL_NAMES
from .models import Activity, Fit, LoginAttempt


def settings_page(request, ctx, loc, options):
    ctx["options"] = options
    ctx["active_days"] = options.active_days
    ctx["model_choices"] = [
        dict(key=kind,label=loc(*name),enabled=options.selected_models.get(kind)!="none",selected=str(options.selected_models.get(kind,"latest")) if options.selected_models.get(kind)!="none" else "latest",
             fits=[fit for fit in Fit.objects.filter(kind=kind) if fit.available])
        for kind,name in MODEL_NAMES.items()
    ]
    ctx["member_names"] = list(get_user_model().objects.filter(is_staff=False).order_by("username").values_list("username",flat=True))
    if request.method != "POST":
        return
    action = request.POST.get("section","activity")
    try:
        with transaction.atomic():
            if action=="accounts":
                fields={"session_minutes":(5,10080),"login_limit":(3,20),"lock_minutes":(1,1440),"active_days":(1,365)}
                for name,(low,high) in fields.items():
                    value=int(request.POST.get(name,getattr(options,name)))
                    if not low<=value<=high:
                        raise ValueError
                    setattr(options,name,value)
                options.save(update_fields=list(fields))
            elif action=="reset":
                from .views import good_password
                user=get_user_model().objects.filter(username=request.POST.get("username",""),is_staff=False).first()
                password=request.POST.get("password","")
                if not user or not good_password(password):
                    raise ValueError
                user.set_password(password)
                user.save(update_fields=["password"])
                LoginAttempt.objects.filter(username=user.username).delete()
                Activity.objects.create(actor=request.user,event="password",subject=user.username)
            elif action=="models":
                selected={}
                for kind in MODEL_NAMES:
                    value=request.POST.get(kind,"latest")
                    if value != "latest" and not any(fit.available for fit in Fit.objects.filter(kind=kind,pk=int(value))):
                        raise ValueError
                    selected[kind]="none" if request.POST.get("toggle_models")=="1" and request.POST.get("enabled_"+kind)!="on" else value
                options.selected_models=selected
                options.training_start=date.fromisoformat(request.POST.get("start",""))
                if options.training_start>timezone.localdate():
                    raise ValueError
                options.training_validate=request.POST.get("validate")=="on"
                options.save(update_fields=["selected_models","training_start","training_validate"])
            elif action=="activity":
                days=int(request.POST.get("days",""))
                if not 1<=days<=365:
                    raise ValueError
                options.active_days=days
                options.save(update_fields=["active_days"])
            else:
                raise ValueError
            Activity.objects.create(actor=request.user,event="settings")
        messages.success(request,loc("Settings saved.","设置已保存。"))
        return redirect("portal",page="settings")
    except (ValueError,TypeError):
        ctx["error"]=loc("Check the settings and allowed values.","请检查设置值及允许范围。")
