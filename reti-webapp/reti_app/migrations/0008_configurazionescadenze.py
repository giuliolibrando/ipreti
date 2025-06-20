# Generated by Django 4.2.7 on 2025-05-30 15:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reti_app', '0007_alter_indirizzoip_stato'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigurazioneScadenze',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ore_inattivita_avviso', models.IntegerField(default=24, help_text="Dopo quante ore di inattività mostrare l'avviso di scadenza", verbose_name='Ore di inattività per avviso scadenza')),
                ('mesi_scadenza', models.IntegerField(default=3, help_text="Dopo quanti mesi di inattività liberare automaticamente l'IP", verbose_name='Mesi per scadenza definitiva')),
                ('giorni_preavviso_scadenza', models.IntegerField(default=30, help_text="Quanti giorni prima della scadenza iniziare a mostrare l'avviso", verbose_name='Giorni di preavviso scadenza')),
            ],
            options={
                'verbose_name': 'Configurazione Scadenze IP',
                'verbose_name_plural': 'Configurazione Scadenze IP',
            },
        ),
    ]
