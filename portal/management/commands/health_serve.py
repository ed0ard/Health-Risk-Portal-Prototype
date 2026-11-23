import socket
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Start the local portal on an available loopback port."

    def handle(self, *args, **options):
        from portal.bootstrap import ensure_assistant
        ensure_assistant()
        for port in range(8000, 8020):
            with socket.socket() as probe:
                try:
                    probe.bind(("127.0.0.1",port))
                except OSError:
                    continue
            self.stdout.write(f"Health portal: http://127.0.0.1:{port}/")
            self.stdout.flush()
            call_command("runserver", f"127.0.0.1:{port}", use_reloader=False)
            return
        raise CommandError("Ports 8000 through 8019 are busy.")
