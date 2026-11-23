"""Population coverage and year eligibility, without running every year's predictions."""
from collections import Counter,defaultdict
from django.db.models import Count,Min,Max
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .models import Record,SiteOptions,Activity
from .learning import active_fit

def eligible_years():
    fits={kind:active_fit(kind) for kind in ('hbp','depre')}
    groups=defaultdict(dict)
    for subject,day,kind,version in Record.objects.values_list('subject','day','kind','form_version').iterator():groups[(subject,day)][kind]=version
    years=set()
    for (_,day),group in groups.items():
        bp=fits['hbp'];mood=fits['depre']
        bp_required={'hbp'} if not bp else {'baseline','hbp'} if bp.artifact.get('engine')=='source' else {'baseline'}
        mood_required={'depre'} if not mood else {'baseline','psqi','depre'}
        if bp_required<=group.keys():years.add(day.year)
        elif mood_required<=group.keys() and (not mood or group.get('psqi')==mood.artifact.get('form_version','legacy')):years.add(day.year)
    return sorted(years,reverse=True)

def overview():
    import shutil
    from django.conf import settings
    options=SiteOptions.objects.filter(pk=1).first()
    groups=defaultdict(set);subjects=set();kinds=Counter();years=Counter()
    for subject,day,kind in Record.objects.values_list('subject','day','kind').iterator():
        groups[(subject,day)].add(kind);subjects.add(subject);kinds[kind]+=1;years[day.year]+=1
    complete=sum({'baseline','hbp','depre','psqi'}<=group for group in groups.values())
    disk=shutil.disk_usage(settings.BASE_DIR)
    return {'accounts':{'total':User.objects.count(),'enabled':User.objects.filter(is_active=True).count(),'activity_window_days':getattr(options,'active_days',30),
                        'recently_active':User.objects.filter(last_login__gte=timezone.now()-timedelta(days=getattr(options,'active_days',30))).count()},
            'population_data':{'participants_with_records':len(subjects),'total_records':sum(kinds.values()),
                'records_by_category':dict(kinds),'records_by_year':dict(sorted(years.items())),
                'same_day_visits':len(groups),'complete_four_category_visits':complete,
                'incomplete_visits':len(groups)-complete,**Record.objects.aggregate(first_record=Min('day'),latest_record=Max('day'))},
            'system':{'status':'online','disk_used_percent':round(disk.used/disk.total*100),
                'events_last_7_days':Activity.objects.filter(created__gte=timezone.now()-timedelta(days=7)).count(),
                'models_available':{kind:active_fit(kind) is not None for kind in ('hbp','depre','age')},
                'docpup_enabled':(getattr(options,'docpup',{}) or {}).get('enabled',True)}}
