import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True, verbose_name='Nome')),
            ],
            options={
                'verbose_name': 'Categoria',
                'verbose_name_plural': 'Categorias',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=120, verbose_name='Título')),
                ('description', models.TextField(verbose_name='Descrição')),
                ('priority', models.CharField(choices=[('low', 'Baixa'), ('medium', 'Média'), ('high', 'Alta')], default='medium', max_length=10, verbose_name='Prioridade')),
                ('status', models.CharField(choices=[('open', 'Aberto'), ('in_progress', 'Em atendimento'), ('waiting', 'Aguardando solicitante'), ('resolved', 'Resolvido'), ('closed', 'Fechado')], default='open', max_length=15, verbose_name='Status')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_tickets', to=settings.AUTH_USER_MODEL, verbose_name='Responsável')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='tickets.category', verbose_name='Categoria')),
                ('requester', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tickets', to=settings.AUTH_USER_MODEL, verbose_name='Solicitante')),
            ],
            options={
                'verbose_name': 'Chamado',
                'verbose_name_plural': 'Chamados',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField(verbose_name='Mensagem')),
                ('internal', models.BooleanField(default=False, verbose_name='Nota interna (só atendentes)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='tickets.ticket')),
            ],
            options={
                'verbose_name': 'Comentário',
                'verbose_name_plural': 'Comentários',
                'ordering': ['created_at'],
            },
        ),
    ]
