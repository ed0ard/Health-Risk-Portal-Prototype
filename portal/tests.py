import csv
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import override_settings
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import TestCase

from .catalog import FIELDS
from .models import Activity, Fit, Record
from .risk import reading_band


class PortalTest(TestCase):
    def test_validation_scaler_only_sees_training_folds(self):
        from unittest.mock import patch
        from sklearn.preprocessing import StandardScaler
        from .learning import train
        sizes = []
        original_fit = StandardScaler.fit

        def fit(scaler, values, *args, **kwargs):
            sizes.append(len(values))
            return original_fit(scaler, values, *args, **kwargs)

        with patch.object(StandardScaler, 'fit', fit):
            result = train('hbp', date(2023,1,1), date(2023,1,1), True)
        self.assertEqual(sizes, [30, 24, 24, 24, 24, 24])
        self.assertEqual(len(result.scores), 5)

    def test_training_first_visit_without_options(self):
        from .models import SiteOptions
        SiteOptions.objects.all().delete()
        self.client.force_login(self.staff)
        response = self.client.get('/health/training/')
        self.assertContains(response, '2020-01-01')

    def test_large_model_ids_are_rejected_without_server_error(self):
        self.client.force_login(self.staff)
        huge = '9' * 100
        response = self.client.post('/health/settings/', {
            'section': 'models', 'hbp': huge, 'start': '2020-01-01',
        })
        self.assertContains(response, 'Check the settings')
        self.assertEqual(self.client.get('/health/training/', {
            'completed': huge,
        }).status_code, 302)

    def test_legacy_mood_model_skips_visit_without_questionnaire(self):
        from unittest.mock import patch
        import numpy as np
        Fit.objects.create(kind='depre', start=date(2023,1,1), end=date(2023,1,1),
                           samples=30, artifact={'classes': [0, 1, 2]})
        for kind in ('baseline', 'psqi'):
            record = Record.objects.get(subject='1', kind=kind)
            Record.objects.create(subject='1', kind=kind, day=date(2024,1,1), values=record.values)
        self.client.force_login(self.member)
        with patch('portal.learning.predict', return_value=np.array([[.8,.1,.1]])):
            response = self.client.get('/health/alerts/')
        self.assertEqual(response.context['cards'][1]['day'], date(2023,1,1))

    def test_training_error_preserves_validation_choice(self):
        self.client.force_login(self.staff)
        response = self.client.post('/health/training/', {
            'model': 'hbp', 'start': '2024-01-01', 'end': '2020-01-01',
        })
        self.assertContains(response, 'Check the date range')
        self.assertNotContains(response, 'name="validate" checked')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        temporary = TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        override = override_settings(BASE_DIR=Path(temporary.name))
        override.enable()
        cls.addClassCleanup(override.disable)

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.member = User.objects.create_user("1",password="Member12!")
        cls.staff = User.objects.create_user("staff",password="Staff12!",is_staff=True)
        for i in range(30):
            for kind, fields in FIELDS.items():
                values = {f.key: i % 4 for f in fields}
                if kind == "baseline":
                    values.update(age=22+i,gender=i%2,height=170,weight=60+i,smoking=0,drinking=0)
                if kind == "hbp":
                    values.update(systolic_bp=100+4*i,diastolic_bp=75,hbp_family=0)
                Record.objects.create(kind=kind,subject=str(i+1),day=date(2023,1,1),values=values)

    def test_login_language_and_role(self):
        self.assertContains(self.client.get("/"),'<html lang="en">')
        self.client.post("/language/",{"lang":"zh","next":"/"})
        self.assertContains(self.client.get("/"),"用户登录")
        self.client.post("/",{"username":"1","password":"Member12!"})
        self.assertContains(self.client.get("/health/home/"),"用户健康中心")
        for route in ["users","training","settings","logs"]:
            self.assertEqual(self.client.get(f"/health/{route}/").status_code,403)
        self.client.post("/signout/")
        self.assertContains(self.client.get("/"),'<html lang="zh-CN">')

    def test_entry_isolation_and_duplicate(self):
        self.client.force_login(self.member)
        data=dict(subject="2",kind="hbp",day="2024-01-01",systolic_bp=125,diastolic_bp=80,hbp_family=0)
        self.assertEqual(self.client.post("/health/entry/",data).status_code,302)
        self.assertFalse(Record.objects.filter(subject="2",day=data["day"]).exists())
        self.assertContains(self.client.post("/health/entry/",data),"A record exists")
        self.assertEqual(self.client.post("/health/entry/",dict(data,replace="on",systolic_bp=118)).status_code,302)
        self.assertEqual(Record.objects.get(subject="1",day=data["day"]).values["systolic_bp"],118)
        self.assertContains(self.client.get("/health/query/?subject=2&kind=hbp"),"2024-01-01")
        self.assertEqual(self.client.get("/health/report/?subject=2").context["subject"],"1")
        self.assertContains(self.client.post("/health/entry/",dict(data,systolic_bp=40)),"Systolic must exceed")

    def test_reports_and_language(self):
        self.client.force_login(self.member)
        for lang in ["en","zh"]:
            self.client.post("/language/",{"lang":lang,"next":"/health/report/"})
            for kind in FIELDS:
                self.assertEqual(self.client.get("/health/query/",{"kind":kind}).status_code,200)
            self.assertContains(self.client.get("/health/report/"),"BMI")
            pdf=self.client.get("/health/report/?format=pdf")
            self.assertEqual(pdf["Content-Type"],"application/pdf")
            self.assertTrue(b"".join(pdf.streaming_content).startswith(b"%PDF"))

    def test_admin_models_and_population(self):
        self.client.force_login(self.staff)
        for page in ["home","settings","users","logs","training","entry","query","report","alerts","password"]:
            self.assertEqual(self.client.get(f"/health/{page}/").status_code,200)
        for kind in ["hbp","depre","age"]:
            data=dict(model=kind,start="2020-01-01",end="2024-01-01",validate="on")
            self.assertEqual(self.client.post("/health/training/",data).status_code,302)
            fit=Fit.objects.get(kind=kind)
            self.assertEqual(fit.samples,30)
            self.assertEqual(len(fit.scores),0 if kind=="age" else 5)
        self.assertContains(self.client.get("/health/alerts/?year=2023"),"Mean estimate")
        self.assertContains(self.client.get("/health/report/"),"PC1")
        batch=self.client.post("/health/report/",{"format":"batch","subjects":"1,2"})
        with ZipFile(BytesIO(b"".join(batch.streaming_content))) as archive:
            self.assertEqual(len(archive.namelist()),2)
            self.assertTrue(all(archive.read(name).startswith(b"%PDF") for name in archive.namelist()))
        self.assertContains(self.client.post("/health/training/",dict(data,start="2026-01-01")),"Check the date range")
        self.assertContains(self.client.get("/health/alerts/?year=2010"),"0")
        self.client.force_login(self.member)
        self.assertEqual(self.client.post("/health/report/",{"format":"batch","subjects":"1,2"}).status_code,403)
        self.assertTrue(self.client.get("/health/alerts/").context["cards"][1]["trained"])

    def test_account_lifecycle(self):
        self.client.force_login(self.staff)
        data={"username":"newuser","password":"Welcome1!"}
        self.assertEqual(self.client.post("/health/users/",data).status_code,302)
        self.client.post("/health/settings/",{"days":"7"})
        self.assertContains(self.client.get("/health/settings/"),'value="7"')
        self.client.post("/signout/")
        self.client.post("/",data)
        self.assertEqual(self.client.post("/health/password/",{"old":"Welcome1!","new":"Changed1!","confirm":"Changed1!"}).status_code,302)
        self.client.post("/signout/")
        self.assertContains(self.client.post("/",data),"Check your username")
        self.assertEqual(self.client.post("/",dict(data,password="Changed1!")).status_code,302)

    def test_user_search_pagination_and_actions(self):
        User = get_user_model()
        User.objects.bulk_create([User(username=f"search-{i:02}") for i in range(35)])
        self.client.force_login(self.staff)
        response = self.client.get("/health/users/?q=search-&p=2")
        self.assertEqual(response.context["pager"].paginator.count, 35)
        self.assertEqual(len(response.context["accounts"]), 5)
        self.assertContains(response, "?p=1&amp;q=search-")
        response = self.client.post("/health/users/?q=search-&p=2",
                                    {"action":"toggle", "username":"search-34"})
        self.assertRedirects(response, "/health/users/?q=search-&p=2")
        self.assertFalse(User.objects.get(username="search-34").is_active)
        self.assertContains(self.client.get("/health/users/?q=missing"), "No matching users.")
        self.assertEqual(self.client.get("/health/users/?p=invalid").status_code, 200)
        self.assertEqual(self.client.get("/health/users/?p=999").status_code, 200)
        self.assertNotContains(self.client.get("/health/settings/"), "Reset User Password")

    def test_password_reset_permissions_and_validation(self):
        from .models import LoginAttempt
        LoginAttempt.objects.create(username=self.member.username, failures=5)
        data = {"action":"reset", "username":self.member.username, "password":"Reset12!"}
        self.client.force_login(self.member)
        self.assertEqual(self.client.post("/health/users/", data).status_code, 403)
        self.client.force_login(self.staff)
        for change in ({"password":"bad"}, {"username":"missing"}, {"username":self.staff.username}):
            self.assertContains(self.client.post("/health/users/", dict(data, **change)), "Select a member")
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password("Member12!"))
        self.assertTrue(LoginAttempt.objects.filter(username=self.member.username).exists())
        response = self.client.post("/health/users/", data, follow=True)
        self.assertContains(response, "Password reset and account unlocked.")
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password("Reset12!"))
        self.assertFalse(LoginAttempt.objects.filter(username=self.member.username).exists())
        self.assertTrue(Activity.objects.filter(event="password", subject=self.member.username).exists())

    def test_success_messages_are_consumed_before_language_switch(self):
        self.client.force_login(self.staff)
        response = self.client.post("/health/settings/", {"section":"accounts", "session_minutes":"30"}, follow=True)
        self.assertContains(response, "data-success")
        response = self.client.post("/language/", {"lang":"zh", "next":"/health/settings/"}, follow=True)
        self.assertNotContains(response, "data-success")
        fit = Fit.objects.create(kind="hbp", start=date(2023,1,1), end=date(2023,1,1), samples=1, artifact={})
        response = self.client.get(f"/health/training/?model=hbp&completed={fit.pk}", follow=True)
        self.assertRedirects(response, "/health/training/?model=hbp")
        self.assertContains(response, "data-success")
        self.assertNotContains(response, f"completed={fit.pk}")
        response = self.client.post("/language/", {"lang":"en", "next":"/health/training/?model=hbp"}, follow=True)
        self.assertNotContains(response, "data-success")

    def test_personal_reading_categories_and_tabs(self):
        for s,d,expected in [(110,72,0),(120,75,1),(115,80,1),(140,88,2),(125,100,3),
                             (180,75,4),(138,110,4),(85,53,5)]:
            self.assertEqual(reading_band(s,d,30),expected)
        self.assertEqual(reading_band(110,72,16),6)
        self.assertEqual(reading_band(110,72,None),6)
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get("/health/query/"),"Query Records")
        self.assertContains(self.client.get("/health/alerts/"),"Normal range")
        self.client.force_login(self.staff)
        self.assertContains(self.client.get("/health/query/"),"Query Records")

    def test_log_export_all_pages_and_permissions(self):
        Activity.objects.bulk_create([Activity(actor=self.staff,event="users",subject="=2+2") for _ in range(54)])
        self.client.force_login(self.member)
        self.assertEqual(self.client.get("/health/logs/?format=csv").status_code,403)
        self.client.force_login(self.staff)
        self.client.post("/language/",{"lang":"zh","next":"/health/logs/"})
        response = self.client.get("/health/logs/?p=2&format=csv")
        rows = list(csv.reader(response.content.decode("utf-8-sig").splitlines()))
        self.assertEqual(rows[0],["时间","用户名","操作","对象"])
        self.assertEqual(len(rows),55)
        self.assertEqual(rows[-1][-1],"'=2+2")

    def test_settings_are_applied(self):
        from .models import SiteOptions
        from .learning import active_fit
        from .reports import sections
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get("/health/settings/"),"Report configuration")
        self.assertEqual(self.client.post("/health/settings/",{"section":"models","hbp":"latest",
            "depre":"latest","age":"latest","start":"2020-01-01","validate":"on"}).status_code,302)
        self.assertIsNone(active_fit("hbp"))
        self.assertEqual(self.client.post("/health/settings/",{"section":"accounts","session_minutes":"30",
            "login_limit":"3","lock_minutes":"5"}).status_code,302)
        self.client.post("/signout/")
        for _ in range(3):
            self.client.post("/",{"username":"1","password":"wrong"})
        self.assertContains(self.client.post("/",{"username":"1","password":"Member12!"}),"Too many failed attempts")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post("/health/users/",{"action":"reset","username":self.member.username,
            "password":"NewPass1!"}).status_code,302)
        self.client.post("/signout/")
        self.assertEqual(self.client.post("/",{"username":"1","password":"NewPass1!"}).status_code,302)
        self.assertEqual(self.client.session.get_expiry_age(),1800)

    def test_measurement_ranges_and_filtered_logs(self):
        from datetime import datetime
        from django.utils import timezone
        from .views import data_values, DataValidationError
        valid={"age":"60","gender":"1","height":"170","weight":"65","smoking":"0","drinking":"0"}
        self.assertEqual(data_values("baseline",valid)["age"],60)
        self.assertEqual(data_values("baseline",dict(valid,age="12"))["age"],12)
        for change in ({"height":"99"},{"weight":"351"},{"age":"-1"},{"age":"126"},{"age":"60.5"},{"weight":"nan"}):
            with self.assertRaises(DataValidationError):
                data_values("baseline",dict(valid,**change))
        for change in ({"systolic_bp":"39"},{"diastolic_bp":"201"},{"diastolic_bp":"130"}):
            with self.assertRaises(DataValidationError):
                data_values("hbp",dict({"systolic_bp":"120","diastolic_bp":"80","hbp_family":"0"},**change))
        old=Activity.objects.create(actor=self.staff,event="login")
        new=Activity.objects.create(actor=self.staff,event="settings")
        Activity.objects.filter(pk=old.pk).update(created=timezone.make_aware(datetime(2025,1,2,12)))
        Activity.objects.filter(pk=new.pk).update(created=timezone.make_aware(datetime(2025,1,3,12)))
        self.client.force_login(self.staff)
        response=self.client.get("/health/logs/",{"start":"2025-01-03","end":"2025-01-03","format":"csv"})
        rows=list(csv.reader(response.content.decode("utf-8-sig").splitlines()))
        self.assertEqual(len(rows),2)
        self.assertIn("Updated Settings",rows[1])

    def test_latest_source_model_skips_missing_files_and_incomplete_visits(self):
        from .learning import active_fit, assessments, observations
        from unittest.mock import patch
        good=Fit.objects.create(kind="hbp",start=date(2023,1,1),end=date(2023,1,1),samples=1,
                                artifact={"classes":[0,1]})
        Fit.objects.create(kind="hbp",start=date(2023,1,1),end=date(2023,1,1),samples=1,
                           artifact={"engine":"source","path":"data/models/missing.pkl"})
        self.assertEqual(active_fit("hbp").pk,good.pk)
        good.artifact={"engine":"source","classes":[0,1],"path":"unused"}
        Record.objects.create(subject="1",kind="hbp",day=date(2024,1,1),
                              values={"systolic_bp":120,"diastolic_bp":80,"hbp_family":0})
        import numpy as np
        with patch("portal.original_models.source_predictions",return_value=np.tile([.8,.2],(30,1))):
            results=assessments("hbp",observations(date(2023,1,1),date(2024,1,1)),good)
        self.assertEqual(results["1"][0],date(2023,1,1))

    def test_system_timezone_conversion_and_log_dates(self):
        from datetime import datetime, timezone as utc_timezone
        from zoneinfo import ZoneInfo
        from unittest.mock import patch
        from django.utils import timezone
        from .timezones import format_timestamp
        stamp=datetime(2026,7,1,1,30,tzinfo=utc_timezone.utc)
        with timezone.override(ZoneInfo("America/New_York")):
            self.assertEqual(format_timestamp(stamp),"2026-06-30 21:30 (UTC-4)")
        with timezone.override(ZoneInfo("Asia/Kolkata")):
            self.assertEqual(format_timestamp(stamp),"2026-07-01 07:00 (UTC+5:30)")
        event=Activity.objects.create(actor=self.staff,event="login")
        Activity.objects.filter(pk=event.pk).update(created=stamp)
        self.client.force_login(self.staff)
        with patch("portal.timezones.reload_localzone",return_value=ZoneInfo("America/New_York")):
            response=self.client.get("/health/logs/",{"start":"2026-06-30","end":"2026-06-30","format":"csv"})
        rows=list(csv.reader(response.content.decode("utf-8-sig").splitlines()))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[1][0],"2026-06-30 21:30:00 (UTC-4)")

    def test_mood_groups_are_named(self):
        from unittest.mock import patch
        Fit.objects.create(kind="depre",start=date(2023,1,1),end=date(2023,1,1),samples=1,artifact={})
        self.client.force_login(self.staff)
        with patch("portal.views.assessments",return_value={"1":(date(2023,1,1),1,None,None)}):
            cards=self.client.get("/health/alerts/?year=2023").context["cards"]
        self.assertEqual(cards[1]["summary"],"Moderate risk")
        self.assertTrue(all(not row.get("range") for row in cards[1]["rows"]))


    def test_training_accepts_text_ids_and_preserves_mood_class_labels(self):
        import numpy as np
        from .learning import train, assessments, observations
        from .original_models import load_model
        Record.objects.filter(subject='1').update(subject='alice')
        for index, record in enumerate(Record.objects.filter(kind='depre')):
            record.values = {key: 1 + index % 2 for key in record.values}
            record.save(update_fields=['values'])
        visits = observations(date(2023, 1, 1), date(2023, 1, 1))
        for kind in ('hbp', 'depre', 'age'):
            with self.subTest(kind=kind):
                fit = train(kind, date(2023, 1, 1), date(2023, 1, 1), True)
                names = fit.artifact['feature_names']
                self.assertNotIn('user_id', names)
                if kind == 'depre':
                    self.assertFalse(any(name.startswith('depre_question_') for name in names))
                    self.assertEqual(fit.artifact['classes'], [1, 2])
                    self.assertEqual(load_model(fit.artifact['path'])['classes'], [1, 2])
                if kind != 'age':
                    results = assessments(kind, visits, fit)
                    self.assertIn('alice', results)
                    if kind == 'depre':
                        self.assertTrue(all(row[1] in (1, 2) for row in results.values()))

    def test_training_rejects_single_class_before_saving_model(self):
        from .learning import train
        for record in Record.objects.filter(kind='hbp'):
            record.values.update(systolic_bp=120, diastolic_bp=80)
            record.save(update_fields=['values'])
        for validate in (False, True):
            with self.assertRaisesRegex(ValueError, '^classes$'):
                train('hbp', date(2023, 1, 1), date(2023, 1, 1), validate)
        self.assertFalse(Fit.objects.exists())

    def test_standalone_loader_joins_same_day_visits(self):
        import pandas as pd
        from unittest.mock import patch
        from training.database import load_model_trainer_data, load_model_test_data
        baseline, pressures = [], []
        for subject in range(6):
            for day, age, bp in [('2023-01-01', 20, 110), ('2024-01-01', 21, 120)]:
                baseline.append(dict(user_id=str(subject), time=day, age=age))
                pressures.append(dict(user_id=str(subject), time=day, systolic_bp=bp))
        def read(path, **kwargs):
            return pd.DataFrame(baseline if path.stem == 'baseline' else pressures)
        with patch('training.database.pd.read_excel', side_effect=read):
            data = load_model_trainer_data(['baseline', 'hbp'], ['2023-01-01', '2024-01-01'])
            self.assertEqual(len(data), 12)
            self.assertTrue((data.systolic_bp == (data.age - 20) * 10 + 110).all())
            own = load_model_test_data(['baseline', 'hbp'], ['2023-01-01', '2024-01-01'], '1')
            self.assertEqual(len(own['combined']), 2)

    def test_legacy_predictions_support_text_username_and_explicit_feature_names(self):
        import numpy as np
        import pandas as pd
        from types import SimpleNamespace
        from unittest.mock import patch
        from .original_models import source_predictions
        from .learning import observations
        group = next(iter(observations(date(2023, 1, 1), date(2023, 1, 1)).values()))
        seen = []
        def predict(data):
            seen.append(data)
            return np.array([[0.2, 0.8]])
        payload = {
            'model': SimpleNamespace(predict_proba=predict),
            'feature_names': ['user_id', 'age'],
            'scaler': SimpleNamespace(feature_names_in_=np.array(['age']), transform=lambda data: data),
        }
        fit = SimpleNamespace(artifact={'path': 'legacy.pkl'})
        with patch('portal.original_models.load_model', return_value=payload):
            result = source_predictions('hbp', fit, [('alice', group)])
        self.assertEqual(result.tolist(), [[0.2, 0.8]])
        self.assertEqual(seen[0].user_id.iloc[0], 0)
