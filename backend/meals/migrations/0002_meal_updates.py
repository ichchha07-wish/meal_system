# meals/migrations/0002_meal_updates.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0001_initial'),  # ✅ correct dependency
    ]

    operations = [

        # ❌ REMOVED AddField for meal_image
        # because it already exists in the database / model

        # Add proximity_radius field
        migrations.AddField(
            model_name='meal',
            name='proximity_radius',
            field=models.FloatField(
                default=5.0,
                help_text='Radius in km for beneficiary search (default: 5km)'
            ),
        ),

        # Ensure latitude is indexed
        migrations.AlterField(
            model_name='meal',
            name='latitude',
            field=models.DecimalField(
                max_digits=9,
                decimal_places=6,
                blank=True,
                null=True,
                db_index=True,
                help_text='Latitude for location mapping',
            ),
        ),

        # Ensure longitude is indexed
        migrations.AlterField(
            model_name='meal',
            name='longitude',
            field=models.DecimalField(
                max_digits=9,
                decimal_places=6,
                blank=True,
                null=True,
                db_index=True,
                help_text='Longitude for location mapping',
            ),
        ),
    ]
