from django.db import migrations

def populate_grade_levels(apps, schema_editor):
    # Get the model from the versioned app registry
    GradeLevel = apps.get_model('school', 'GradeLevel')

    grades_to_create = [
        # Kindergarten: Order 1-3
        {"name": "ABC", "tuition_fee": 50000, "description": "Kindergarten", "order": 1},
        {"name": "K-I", "tuition_fee": 50000, "description": "Kindergarten", "order": 2},
        {"name": "K-II", "tuition_fee": 50000, "description": "Kindergarten", "order": 3},

        # Lower Elementary: Order 4-6
        {"name": "Grade 1", "tuition_fee": 60000, "description": "Lower Elementary", "order": 4},
        {"name": "Grade 2", "tuition_fee": 60000, "description": "Lower Elementary", "order": 5},
        {"name": "Grade 3", "tuition_fee": 60000, "description": "Lower Elementary", "order": 6},

        # Upper Elementary: Order 7-9
        {"name": "Grade 4", "tuition_fee": 65000, "description": "Upper Elementary", "order": 7},
        {"name": "Grade 5", "tuition_fee": 65000, "description": "Upper Elementary", "order": 8},
        {"name": "Grade 6", "tuition_fee": 65000, "description": "Upper Elementary", "order": 9},

        # Junior High: Order 10-12
        {"name": "Grade 7", "tuition_fee": 73000, "description": "Junior High", "order": 10},
        {"name": "Grade 8", "tuition_fee": 73000, "description": "Junior High", "order": 11},
        {"name": "Grade 9", "tuition_fee": 73000, "description": "Junior High", "order": 12},

        # Senior High: Order 13-15
        # Note: Set to 73000 as default; adjust if Senior High has different fees
        {"name": "Grade 10", "tuition_fee": 73000, "description": "Senior High", "order": 13},
        {"name": "Grade 11", "tuition_fee": 73000, "description": "Senior High", "order": 14},
        {"name": "Grade 12", "tuition_fee": 73000, "description": "Senior High", "order": 15},
    ]

    for grade in grades_to_create:
        GradeLevel.objects.update_or_create(
            name=grade['name'],
            defaults={
                'tuition_fee': grade['tuition_fee'],
                'description': grade['description'],
                'order': grade['order']
            }
        )

def remove_grade_levels(apps, schema_editor):
    """Optional: Logic to reverse the migration if needed"""
    GradeLevel = apps.get_model('school', 'GradeLevel')
    GradeLevel.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        # This will automatically point to your previous migration file
        ('school', '0001_initial'), 
    ]

    operations = [
        migrations.RunPython(populate_grade_levels, reverse_code=remove_grade_levels),
    ]