from datetime import date

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0005_remove_siteoptions_report_charts_and_more')]

    operations = [
        migrations.AlterField(
            model_name='siteoptions', name='training_start',
            field=models.DateField(default=date(2020, 1, 1)),
        ),
    ]
