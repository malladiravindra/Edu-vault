from django.db import migrations, models

from accounts import crypto


def encrypt_existing_secrets(apps, schema_editor):
    """Secrets written before encryption existed are plaintext base32; encrypt them in place."""
    User = apps.get_model("accounts", "User")
    for user in User.objects.exclude(totp_secret=""):
        try:
            crypto.decrypt(user.totp_secret)  # already encrypted
        except ValueError:
            user.totp_secret = crypto.encrypt(user.totp_secret)
            user.save(update_fields=["totp_secret"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="totp_secret",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(encrypt_existing_secrets, migrations.RunPython.noop),
    ]
