from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from openpyxl import load_workbook

from portal.catalog import FIELDS
from portal.models import Record, SiteOptions


class Command(BaseCommand):
    help = "Initialize local portal accounts and import the example workbooks."

    def add_arguments(self, parser):
        parser.add_argument("--import-data", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        for username, staff in [("1", False), ("admin", True)]:
            user, new = get_user_model().objects.get_or_create(username=username, defaults={"is_staff": staff})
            if new:
                password = "Password123!"
                user.set_password(password)
                user.save()
                self.stdout.write(f"Local account {username} | initial password {password}")
        if not options["import_data"]:
            return
        options_row, _ = SiteOptions.objects.get_or_create(pk=1)
        if not options_row.source_accounts_loaded:
            account_root = Path(settings.BASE_DIR) / "data" / "source" / "LoginData"
            for filename, id_key, password_key, staff in [
                ("User.xlsx","user_id","user_password",False),("Admin.xlsx","admin_id","admin_password",True)
            ]:
                self.stdout.write(f"Importing accounts from {filename} (password hashing may take several minutes)...")
                self.stdout.flush()
                book = load_workbook(account_root / filename, read_only=True, data_only=True)
                try:
                    sheet = book.active
                    sheet.reset_dimensions()
                    iterator = iter(sheet.values)
                    header = next(iterator)
                    for index, row in enumerate(iterator, 1):
                        data = dict(zip(header,row))
                        if data.get(id_key) is None:
                            continue
                        user, created = get_user_model().objects.get_or_create(username=str(data[id_key]),
                            defaults={"is_staff":staff})
                        if created:
                            user.set_password(str(data[password_key]))
                            user.save()
                        if index % 250 == 0:
                            self.stdout.write(f"{filename}: {index} accounts processed")
                            self.stdout.flush()
                finally:
                    book.close()
            options_row.source_accounts_loaded = True
            options_row.save(update_fields=["source_accounts_loaded"])
        if options_row.examples_loaded:
            return
        root = Path(settings.BASE_DIR) / "data" / "source"
        for kind, fields in FIELDS.items():
            book = load_workbook(root / f"table_{kind}.xlsx", read_only=True, data_only=True)
            try:
                sheet = book.active
                sheet.reset_dimensions()
                rows = iter(sheet.values)
                header = next(rows)
                batch = []
                for row in rows:
                    data = dict(zip(header, row))
                    if data.get("user_id") is None or data.get("time") is None:
                        continue
                    batch.append(Record(subject=str(data["user_id"]), kind=kind, day=data["time"].date(),
                                        values={f.key: data[f.key] for f in fields}))
                Record.objects.bulk_create(batch, ignore_conflicts=True, batch_size=150)
            finally:
                book.close()
            self.stdout.write(f"{kind}: {len(batch)} example rows processed")
        options_row.examples_loaded = True
        options_row.save(update_fields=["examples_loaded"])
