from django.db import migrations

CATEGORIES = ["Hardware", "Software", "Rede", "Acesso e senha", "Outros"] 

def seed(apps, schema_editor):    
    Category = apps.get_model("tickets", "Category")    
    Group = apps.get_model("auth", "Group")    
    
    for name in CATEGORIES:        
        Category.objects.get_or_create(name=name)    
    Group.objects.get_or_create(name="Atendentes") 
        
class Migration(migrations.Migration):    
    dependencies = [        
        ("tickets", "0001_initial"),        
        ("auth", "0012_alter_user_first_name_max_length"),    
        ]    
                
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]