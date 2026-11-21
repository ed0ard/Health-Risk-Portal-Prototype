import csv
import json
import math
import re
import shutil
from collections import Counter
from datetime import date, timedelta
from importlib.util import find_spec
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.cache import never_cache

from .catalog import EVENTS, FIELDS, KINDS, MODEL_NAMES, NAV, record_fields
from .learning import assessments, observations, train, active_fit
from .models import Activity, Fit, Record, SiteOptions, LoginAttempt
from .reports import display, pdf_report, sections
from .timezones import format_timestamp
from .risk import MODEL_BP, MOOD, READING, latest_readings, distribution


def language(request):
    return "zh" if request.COOKIES.get("portal_lang") == "zh" else "en"


def translator(request):
    return lambda en, zh: zh if language(request) == "zh" else en


@require_POST
def switch(request):
    target = request.POST.get("next","/")
    if not url_has_allowed_host_and_scheme(target, {request.get_host()}):
        target = "/"
    response = redirect(target)
    response.set_cookie("portal_lang", "zh" if request.POST.get("lang")=="zh" else "en", max_age=31536000, samesite="Lax")
    return response


def log(request, event, subject=""):
    Activity.objects.create(actor=request.user,event=event,subject=subject)


@require_http_methods(["GET","POST"])
@never_cache
def signin(request):
    if request.user.is_authenticated:
        return redirect("portal",page="home")
    loc = translator(request)
    error = ""
    if request.method == "POST":
        options, _ = SiteOptions.objects.get_or_create(pk=1)
        name = request.POST.get("username","")[:150]
        with transaction.atomic():
            attempt, _ = LoginAttempt.objects.get_or_create(username=name)
            attempt = LoginAttempt.objects.select_for_update().get(pk=attempt.pk)
            if attempt.locked_until and attempt.locked_until > timezone.now():
                return render(request,"portal/login.html",{"lang":language(request),
                    "error":loc("Too many failed attempts. Try again later.","登录失败次数过多，请稍后重试。")})
            if attempt.locked_until:
                attempt.failures = 0
                attempt.locked_until = None
            user = authenticate(request,username=name,password=request.POST.get("password",""))
            attempt.failures = 0 if user else attempt.failures + 1
            if attempt.failures >= options.login_limit:
                attempt.locked_until = timezone.now() + timedelta(minutes=options.lock_minutes)
            attempt.save()

        if user:
            last = user.last_login
            login(request,user)
            request.session.set_expiry(options.session_minutes * 60)
            request.session["previous_login"] = last.isoformat(timespec="minutes") if last else ""
            log(request,"login")
            return redirect("portal",page="home")
        error = loc("Check your username and password.","请检查用户名和密码。")
    return render(request,"portal/login.html",{"lang":language(request),"error":error})


@require_POST
def signout(request):
    logout(request)
    return redirect("signin")


def good_password(value):
    groups = sum(bool(re.search(p,value)) for p in ("[a-z]","[A-Z]","[0-9]","[^A-Za-z0-9]"))
    return 6 <= len(value) <= 12 and groups >= 3


def activity_rows(query,loc):
    return [(r.created,r.actor.username,loc(*EVENTS[r.event]),r.subject) for r in query.select_related("actor")]


def make_fields(kind,loc,posted):
    return [dict(key=f.key,label=loc(f.en,f.zh),lo=f.lo,hi=f.hi,step=f.step,
                 choices=[(str(i),loc(*pair)) for i,pair in enumerate(f.choices)],
                 value=posted.get(f.key,"")) for f in FIELDS[kind]]


class DataValidationError(ValueError):
    def __init__(self, english, chinese):
        self.labels=(english,chinese)
        super().__init__(english)


def data_values(kind, posted):
    values = {}
    for f in FIELDS[kind]:
        try:
            v = float(posted.get(f.key,""))
        except (ValueError,TypeError,OverflowError):
            raise DataValidationError(f"{f.en}: enter a number.",f"{f.zh}：请输入数值。")
        if not math.isfinite(v) or not f.lo <= v <= f.hi or (f.step=="1" and not v.is_integer()):
            raise DataValidationError(f"{f.en}: enter a value from {f.lo:g} to {f.hi:g}"+(" (whole numbers)." if f.step=="1" else "."),
                                      f"{f.zh}：请输入{f.lo:g}至{f.hi:g}"+("之间的整数。" if f.step=="1" else "之间的数值。"))
        values[f.key] = int(v) if f.step=="1" else v
    if kind=="baseline" and not 11 <= values["weight"] / (values["height"]/100)**2 <= 75:
        raise DataValidationError("Height and weight imply a BMI outside 11–75. Check units and values.","身高体重对应的BMI超出11–75，请核对单位和数值。")
    if kind=="hbp" and values["systolic_bp"] <= values["diastolic_bp"]:
        raise DataValidationError("Systolic must exceed diastolic pressure.","收缩压必须高于舒张压。")
    return values


def go(page, **params):
    return redirect(reverse("portal",args=[page])+"?"+urlencode(params))


def select_subject(request, params):
    if not request.user.is_staff:
        return request.user.username
    return params.get("subject","1").strip()[:150]


def detail_rows(query,kind,loc):
    fields = FIELDS[kind]
    questionnaire = kind in ("depre","psqi")
    rows = []
    for r in query:
        fields = record_fields(r)
        vals = r.values
        cells = [display(f,vals[f.key],loc) for f in fields]
        rows.append(dict(day=r.day.isoformat(),cells=cells,total=sum(vals.values()) if questionnaire else None,
                         details=[(loc(f.en,f.zh),v,vals[f.key]) for f,v in zip(fields,cells)]))
    return rows


def health_data(request, page, ctx, loc, params):
    kind, subject = ctx["kind"],ctx["subject"]
    ctx["kind_label"] = loc(*KINDS[kind])
    ctx.update(fields=make_fields(kind,loc,request.POST),questionnaire=kind in ("depre","psqi"))
    if page=="query":
        records = Record.objects.filter(subject=subject,kind=kind)
        pager = Paginator(records,30).get_page(request.GET.get("p"))
        ctx.update(rows=detail_rows(pager,kind,loc),pager=pager)
    elif page=="entry" and request.method=="POST":
        try:
            values = data_values(kind,request.POST)
            day = date.fromisoformat(request.POST.get("day",""))
            if not subject or day > timezone.localdate():
                raise ValueError
            with transaction.atomic():
                record, new = Record.objects.get_or_create(subject=subject,kind=kind,day=day,defaults={"values":values,"form_version":"source"})
                if not new and not request.POST.get("replace"):
                    ctx["error"] = loc("A record exists for that date. Select Replace to update it.","该日期已有记录。如需更新，请勾选替换。")
                    return
                if not new:
                    record.values = values
                    record.form_version = "source"
                    record.save(update_fields=["values","form_version"])
                log(request,"entry",subject)
            messages.success(request,loc("Health record saved.","健康数据已保存。"))
            return go("query",kind=kind,subject=subject)
        except DataValidationError as exc:
            ctx["error"]=loc(*exc.labels)
        except (ValueError,OverflowError):
            ctx["error"] = loc("Check the user ID, date and field values. Systolic must exceed diastolic.","请检查用户编号、日期及字段值。收缩压应大于舒张压。")
    elif page=="report":
        if params.get("format")=="batch":
            if not request.user.is_staff or request.method!="POST":
                return HttpResponseForbidden(loc("Administrator access required.","需要管理员权限。"))
            ids=list(dict.fromkeys(re.split(r"[,，\s]+",params.get("subjects","").strip())))
            if not ids or not all(ids) or len(ids)>50 or any(len(s)>150 for s in ids):
                ctx["error"]=loc("Enter 1–50 user IDs.","请输入 1 至 50 个用户编号。")
            elif set(ids)-set(Record.objects.filter(subject__in=ids).values_list("subject",flat=True).distinct()):
                ctx["error"]=loc("One or more IDs have no health records.","有用户编号尚无健康记录。")
            else:
                bundle=BytesIO()
                with ZipFile(bundle,"w",ZIP_DEFLATED) as archive:
                    for i,member in enumerate(ids,1):
                        response=pdf_report(member,sections(member,loc),loc)
                        try:
                            filename=re.sub(r"[^\w-]","_",member)
                            archive.writestr(f"{i}-health-{filename}.pdf",b"".join(response.streaming_content))
                        finally:
                            response.close()
                bundle.seek(0)
                log(request,"report")
                return FileResponse(bundle,as_attachment=True,filename="health-reports.zip")
        parts = sections(subject,loc)
        ctx["parts"] = parts
        if params.get("format")=="pdf":
            log(request,"report",subject)
            return pdf_report(subject,parts,loc)


def alert_data(request,ctx,loc):
    staff = request.user.is_staff
    query = Record.objects.all() if staff else Record.objects.filter(subject=request.user.username)
    years = [d.year for d in query.dates("day","year",order="DESC")]
    try:
        year = int(request.GET.get("year",years[0] if years else timezone.localdate().year))
        if not 1 <= year <= 9999:
            raise ValueError
    except ValueError:
        raise Http404
    ctx.update(year=year,years=years)
    if staff:
        dates = observations(date(year,1,1),date(year,12,31))
    else:
        dates = {}
        for r in query:
            group = dates.setdefault((r.subject,r.day),{})
            group[r.kind] = r.values
            if r.kind=="psqi":
                group["_sleep_version"] = r.form_version
    age_rows = query.filter(kind="baseline").order_by("subject","day").values_list("subject","day","values")
    readings = latest_readings(dates,age_rows)
    ctx["cards"] = []
    ctx["assessed_at"] = timezone.now()
    for kind in ("hbp","depre"):
        fit = active_fit(kind)
        if kind=="hbp" and not fit:
            latest = readings
            bands = READING
            title = loc("Blood pressure assessment","血压读数评估")
            guide = loc("Adult office ranges (mmHg): high-normal starts at 120 or 80; grades 1, 2 and 3 start at 140/90, 160/100 and 180/110. Use the higher category. A single reading cannot establish a diagnosis.",
                        "成人诊室血压参考（mmHg）：正常高值始于收缩压120或舒张压80；1、2、3级起点分别为140/90、160/100、180/110，两项取较高级别。诊断需结合多次规范测量。")
        else:
            latest = assessments(kind,dates,fit)
            if kind=="hbp":
                bands = MODEL_BP
                title = loc("Hypertension risk assessment","高血压风险评估")
                guide = loc("Model score: low below 30%, moderate from 30% to 70%, high above 70%.",
                            "模型评分：低于30%为低风险，30%至70%为中风险，高于70%为高风险。")
            else:
                bands = MOOD
                title = loc("Mood risk assessment","抑郁风险评估")
                guide = loc("Questionnaire bands: 0–4 low, 5–9 moderate, 10–27 high.",
                            "情绪问卷分组：0–4分为低风险，5–9分为中风险，10–27分为高风险。")
        rows, gradient = distribution(latest,bands,loc)
        ranges = ("< 0.30","0.30–0.70","> 0.70") if kind=="hbp" and fit else ()
        for row,limit in zip(rows,ranges):
            row["range"] = limit
        summary = "—"
        if latest:
            if kind=="hbp" and fit:
                summary = f"{sum(v[3] for v in latest.values())/len(latest):.3f}"
            else:
                counts = Counter(row[1] for row in latest.values())
                modes = sorted(i for i,n in counts.items() if n==max(counts.values()))
                summary = " / ".join(rows[i]["label"] for i in modes)
        summary_label = loc("Mean estimate","平均模型评分") if kind=="hbp" and fit else loc("Most frequent band","最常见分组")
        card = dict(title=title,count=len(latest),guide=guide,rows=rows,gradient=gradient,
                    summary=summary,summary_label=summary_label,bp_reference=bands is READING,
                    chart=json.dumps({"labels":[r["label"] for r in rows],"values":[r["count"] for r in rows],"colors":[r["color"] for r in rows]},ensure_ascii=False))
        own = latest.get(request.user.username)
        if not staff and own:
            day,band,value,_ = own
            label = rows[band]["label"]
            if kind=="depre":
                result = label
            else:
                result = f"{value} - {label}"
            card.update(result=result,tone=bands[band][2],day=day,trained=bool(fit))
        if not staff and fit and kind=="hbp" and request.user.username in readings:
            day,band,value,_ = readings[request.user.username]
            card["observation"] = (day,value,loc(*READING[band][:2]),READING[band][2])
        if not staff and kind=="depre":
            visits = [(day,g["depre"]) for (_,day),g in dates.items() if "depre" in g]
            if visits:
                day,answers = max(visits,key=lambda visit:visit[0])
                if fit:
                    score = sum(answers.values())
                    level = int(score>=5)+int(score>=10)
                    card["observation"] = (day,f"{score}/27",loc(*MOOD[level][:2]),MOOD[level][2])
                if answers.get("depre_question_9",0)>0:
                    card["follow_up"] = loc("Your latest response about self-harm warrants follow-up with a health professional.",
                                            "最近一次问卷的自伤想法条目有阳性回答，建议单独与医护人员沟通。")
        ctx["cards"].append(card)


def training(request,ctx,loc,params):
    model = params.get("model","hbp")
    if model not in MODEL_NAMES:
        raise Http404
    opts, _ = SiteOptions.objects.get_or_create(pk=1)
    ctx.update(training_start=opts.training_start.isoformat(), training_validate=opts.training_validate)
    ctx.update(model=model,models=[(k,loc(*v)) for k,v in MODEL_NAMES.items()],fits=Fit.objects.filter(kind=model)[:10])
    ctx["model_storage"] = str(settings.DATABASES["default"]["NAME"]) + " / portal_fit"
    completed = params.get("completed","")
    ctx["completed"] = completed.isdigit() and Fit.objects.filter(pk=completed,kind=model).exists()
    module = "sklearn" if model=="hbp" else "xgboost"
    ctx.update(original_name="Random Forest" if model=="hbp" else "XGBoost",original_ready=find_spec(module) is not None)
    if request.method != "POST":
        return
    try:
        start = date.fromisoformat(params.get("start",""))
        end = date.fromisoformat(params.get("end",""))
        if start>end:
            raise ValueError("range")
        method = params.get("method","original")
        if method not in ("light","original") or (model!="age" and method=="original" and not ctx["original_ready"]):
            raise ValueError("dependency")
        if request.headers.get("X-Training-Progress") == "1":
            from .training_stream import stream_training
            return stream_training(request,model,start,end,params.get("validate")=="on",method)
        with transaction.atomic():
            train(model,start,end,params.get("validate")=="on",method)
            log(request,"training",model)
        messages.success(request,loc("Training completed. The fitted model has been saved.","训练完成，已保存模型。"))
        return go("training",model=model)
    except ValueError as exc:
        reasons = {"versions":("Choose a range with one sleep questionnaire version.","请选择仅包含同一睡眠问卷版本的日期范围。"),
                   "dependency":("The optional training package is unavailable.","尚未安装可选训练包。"),
                   "classes":("The range needs examples from at least two classes.","所选范围需至少包含两个类别。"),
                   "folds":("Five-fold validation needs at least five visits per class.","五折验证要求每个类别至少有五组记录。"),
                   "samples":("At least three complete visits are required.","至少需要三组完整的同日记录。")}
        ctx["error"]=loc(*reasons.get(str(exc),("Check the date range.","请检查日期范围。")))


def accounts(request,page,ctx,loc):
    User = get_user_model()
    opts,_ = SiteOptions.objects.get_or_create(pk=1)
    if page=="settings":
        from .preferences import settings_page
        return settings_page(request,ctx,loc,opts)
    elif page=="password" and request.method=="POST":
        new=request.POST.get("new","")
        if not request.user.check_password(request.POST.get("old","")):
            ctx["error"]=loc("Current password is incorrect.","当前密码有误。")
        elif new!=request.POST.get("confirm") or not good_password(new):
            ctx["error"]=loc("Check the new password and confirmation.","请检查新密码格式和两次输入是否一致。")
        else:
            request.user.set_password(new)
            request.user.save()
            update_session_auth_hash(request,request.user)
            log(request,"password")
            messages.success(request,loc("Password updated.","密码已更新。"))
            return redirect("portal",page="home")
    elif page=="users":
        ctx["accounts"]=User.objects.order_by("username")
        if request.method=="POST":
            name=request.POST.get("username","").strip()
            password=request.POST.get("password","")
            with transaction.atomic():
                if request.POST.get("action")=="toggle":
                    user=User.objects.filter(username=name,is_staff=False).first()
                    if user:
                        user.is_active=not user.is_active
                        user.save(update_fields=["is_active"])
                    else: raise Http404
                elif not re.fullmatch(r"[\w.@+-]{1,150}",name) or not good_password(password):
                    ctx["error"]=loc("Check the username and password format.","请检查用户名与密码格式。")
                    return
                else:
                    user,created=User.objects.get_or_create(username=name)
                    if not created:
                        ctx["error"]=loc("Username already exists.","用户名已存在。")
                        return
                    user.set_password(password)
                    user.save()
                log(request,"users",name)
            return redirect("portal",page=page)
    elif page=="logs":
        query = Activity.objects.select_related("actor").all()
        start, end = request.GET.get("start",""), request.GET.get("end","")
        ctx.update(log_start=start,log_end=end)
        try:
            start_day = date.fromisoformat(start) if start else None
            end_day = date.fromisoformat(end) if end else None
            if start_day and end_day and start_day>end_day:
                raise ValueError
            if start_day: query=query.filter(created__date__gte=start_day)
            if end_day: query=query.filter(created__date__lte=end_day)
        except ValueError:
            ctx["error"]=loc("Check the log date range.","请检查日志日期范围。")
            ctx["events"]=[]
            return
        ctx["log_query"]=urlencode({"start":start,"end":end})
        if request.GET.get("format")=="csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="activity-log-{timezone.localdate():%Y-%m-%d}.csv"'
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow([loc("Time","时间"),loc("Username","用户名"),loc("Activity","操作"),loc("Subject","对象")])
            for event in query.iterator():
                values = [format_timestamp(event.created,seconds=True),event.actor.username,
                          loc(*EVENTS[event.event]),event.subject]
                writer.writerow(["'"+v if v.lstrip().startswith(("=","+","-","@")) or v.startswith(("\t","\r","\n")) else v for v in values])
            return response
        pager=Paginator(query,30).get_page(request.GET.get("p"))
        ctx.update(events=activity_rows(pager.object_list,loc),pager=pager)
    elif page=="home":
        events=Activity.objects.all()
        if request.user.is_staff:
            disk=shutil.disk_usage(settings.BASE_DIR)
            ctx["stats"]=[(loc("Total users","用户数量"),User.objects.count()),
                          (loc("Active users","活跃用户"),User.objects.filter(last_login__gte=timezone.now()-timedelta(days=opts.active_days)).count()),
                          (loc("System status","系统状态"),loc("Online","正常")),
                          (loc("Disk usage","存储使用"),f"{100*disk.used/disk.total:.0f}%")]
        else: events=events.filter(actor=request.user)
        ctx["events"]=activity_rows(events[:10],loc)
        ctx["previous_login"]=format_timestamp(request.session.get("previous_login"))



@require_http_methods(["GET","POST"])
@never_cache
def portal(request,page):
    if not request.user.is_authenticated: return redirect("signin")
    if page not in NAV: raise Http404
    loc=translator(request)
    admin_pages=("users","training","settings","logs")
    if page in admin_pages and not request.user.is_staff:
        return HttpResponseForbidden(loc("Administrator access required.","需要管理员权限。"))
    params=request.POST if request.method=="POST" else request.GET
    kind=params.get("kind","baseline")
    if kind not in KINDS: raise Http404
    nav=[(key,loc(*name)) for key,name in NAV.items() if key!="password" and (request.user.is_staff or key not in admin_pages)]
    ctx=dict(lang=language(request),page=page,title=loc(*NAV[page]),nav=nav,subject=select_subject(request,params),
             kind=kind,kinds=[(k,loc(*v)) for k,v in KINDS.items()],today=timezone.localdate().isoformat())
    response=None
    if page in ("entry","query","report"): response=health_data(request,page,ctx,loc,params)
    elif page=="alerts": alert_data(request,ctx,loc)
    elif page=="training": response=training(request,ctx,loc,params)
    else: response=accounts(request,page,ctx,loc)
    return response if response is not None else render(request,"portal/main.html",ctx)
