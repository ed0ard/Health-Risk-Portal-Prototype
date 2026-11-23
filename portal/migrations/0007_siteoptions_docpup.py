from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('portal','0006_siteoptions_training_start_date')]
    operations=[migrations.AddField(model_name='siteoptions',name='docpup',field=models.JSONField(default=dict))]
