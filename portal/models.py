from django.conf import settings
from django.db import models


class SiteOptions(models.Model):
    active_days = models.PositiveSmallIntegerField(default=30)
    session_minutes = models.PositiveIntegerField(default=120)
    login_limit = models.PositiveSmallIntegerField(default=5)
    lock_minutes = models.PositiveSmallIntegerField(default=15)
    selected_models = models.JSONField(default=dict)
    training_start = models.DateField(default="2020-01-01")
    training_validate = models.BooleanField(default=True)
    source_accounts_loaded = models.BooleanField(default=False)
    examples_loaded = models.BooleanField(default=False)


class Record(models.Model):
    subject = models.CharField(max_length=150)
    kind = models.CharField(max_length=16)
    day = models.DateField()
    values = models.JSONField()
    form_version = models.CharField(max_length=12,default="legacy")

    class Meta:
        ordering = ["-day", "-pk"]
        constraints = [models.UniqueConstraint(fields=["subject", "kind", "day"], name="portal_record_day")]
        indexes = [models.Index(fields=["kind", "day"])]


class Activity(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.CharField(max_length=32)
    subject = models.CharField(max_length=150, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]


class Fit(models.Model):
    kind = models.CharField(max_length=16)
    start = models.DateField()
    end = models.DateField()
    samples = models.PositiveIntegerField()
    artifact = models.JSONField()
    scores = models.JSONField(default=list)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]

    @property
    def available(self):
        if self.artifact.get("engine") != "source":
            return True
        from pathlib import Path
        root=Path(settings.BASE_DIR).resolve()
        path=(root/self.artifact.get("path","")).resolve()
        return root in path.parents and path.is_file()

    @property
    def mean_accuracy(self):
        return sum(self.scores) / len(self.scores) if self.scores else None


class LoginAttempt(models.Model):
    username = models.CharField(max_length=150, unique=True)
    failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True)
