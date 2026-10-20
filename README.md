# Help Desk em Django

Sistema de chamados (help desk) feito com Django. Usuários abrem chamados, atendentes assumem, respondem e acompanham o status até a conclusão. Projeto de estudo com login, permissões por perfil, regras de negócio e testes automatizados.

## Sumário

1. [Funcionalidades](#funcionalidades)
2. [Perfis de usuário](#perfis-de-usuário)
3. [Tecnologias](#tecnologias)
4. [Instalação passo a passo](#instalação-passo-a-passo)
5. [Roteiro de teste na mão](#roteiro-de-teste-na-mão)
6. [Testes automatizados](#testes-automatizados)
7. [Regras de negócio](#regras-de-negócio)
8. [Rotas](#rotas)
9. [Estrutura do projeto](#estrutura-do-projeto)
10. [Problemas comuns](#problemas-comuns)
11. [Trabalhando em equipe com Git](#trabalhando-em-equipe-com-git)
12. [Desafios extras](#desafios-extras)

## Funcionalidades

- Login e logout (sistema de autenticação do Django)
- Abertura de chamados com título, categoria, prioridade e descrição
- Lista de chamados com filtro por status e paginação
- Tela de detalhe com conversa (comentários)
- Notas internas visíveis apenas para atendentes
- Atendente pode assumir chamado, mudar status, prioridade e responsável
- Mudança de status validada por regras (um chamado fechado é final)
- E-mail ao abrir chamado e ao receber uma resposta (aparece no terminal em desenvolvimento)
- Painel administrativo em `/admin/`
- 13 testes automatizados

## Perfis de usuário

| Perfil | Como é criado | O que pode |
|---|---|---|
| Solicitante | Usuário comum | Abre chamados, vê apenas os seus e comenta |
| Atendente | Usuário no grupo `Atendentes` (ou `is_staff`) | Vê todos os chamados, assume, muda status, prioridade e responsável, escreve notas internas |
| Admin | `createsuperuser` | Tudo, mais categorias e usuários no `/admin/` |

## Tecnologias

- Python 3.12 ou mais novo
- Django 6.1
- SQLite (banco local, não vai para o Git)
- HTML com templates do Django

## Instalação passo a passo

Pré-requisitos: Python 3.12+, Git e um terminal. Confira a versão com `python3 --version`.

### 1. Clonar o repositório

```bash
git clone https://github.com/otzjoao/helpdesk.git
cd helpdesk
```

### 2. Criar e ativar o ambiente virtual

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação, rode uma vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tente de novo.

O terminal deve mostrar `(.venv)` no início da linha.

### 3. Instalar as dependências

```bash
python -m pip install -r requirements.txt
```

### 4. Criar o banco de dados

```bash
python manage.py migrate
```

Esse comando também cadastra automaticamente 5 categorias (Hardware, Software, Rede, Acesso e senha, Outros) e o grupo `Atendentes`.

### 5. Criar o administrador

```bash
python manage.py createsuperuser
```

### 6. Rodar o servidor

```bash
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`. O painel admin fica em `http://127.0.0.1:8000/admin/`.

## Roteiro de teste na mão

Faça este roteiro para validar que tudo funciona. Use uma **janela anônima** para o segundo usuário: duas contas na mesma janela dividem a sessão e uma desloga a outra.

| # | Ação | Resultado esperado |
|---|---|---|
| 1 | No `/admin/`, crie o usuário `ana` com e-mail preenchido | Solicitante comum |
| 2 | Crie o usuário `carlos`, abra-o e em Grupos escolha `Atendentes` | Atendente (não precisa marcar staff) |
| 3 | Janela anônima: entre em `/contas/login/` como `ana` e abra um chamado em `/novo/` | Vai para o detalhe do chamado. O e-mail de confirmação aparece no terminal |
| 4 | Janela normal: entre como `carlos`, abra o chamado e clique em **Assumir chamado** | Status vira "Em atendimento" e `carlos` fica como responsável |
| 5 | Como `carlos`, escreva uma nota interna e depois uma resposta normal | A resposta normal gera e-mail para `ana` no terminal |
| 6 | Volte à janela da `ana` e atualize | Ela vê a resposta, mas não vê a nota interna |
| 7 | Como `carlos`, em um chamado "Aberto", tente mudar direto para "Resolvido" | Mensagem de erro de transição inválida |
| 8 | Crie o usuário `bia` e tente abrir o chamado da `ana` pela URL | Erro 404: chamado de outra pessoa é invisível |

## Testes automatizados

```bash
python manage.py test
```

O esperado é `Ran 13 tests ... OK`. Os testes cobrem:

- visitante é redirecionado para o login
- solicitante vê só os próprios chamados e recebe 404 no de outra pessoa
- atendente vê todos os chamados
- criação de chamado define o solicitante e envia e-mail
- nota interna não aparece para o solicitante, e ele não consegue criá-la
- resposta do atendente envia e-mail ao solicitante
- solicitante não consegue gerenciar chamado (403)
- assumir chamado muda para "Em atendimento"
- transições de status válidas e inválidas
- chamado fechado é final
- filtro por status

## Regras de negócio

### Transições de status

| De | Pode ir para |
|---|---|
| Aberto | Em atendimento, Fechado |
| Em atendimento | Aguardando solicitante, Resolvido, Fechado |
| Aguardando solicitante | Em atendimento, Fechado |
| Resolvido | Em atendimento, Fechado |
| Fechado | Nenhum (final) |

### Visibilidade e permissões

- Atendente vê todos os chamados. Solicitante vê somente os seus, e chamado de outra pessoa retorna 404.
- Comentários marcados como internos nunca aparecem para o solicitante, nem na tela.
- Só atendentes mudam status, prioridade e responsável (os demais recebem 403).
- A lista de responsáveis possíveis mostra apenas atendentes ativos.
- Atendente = usuário `is_staff` ou membro do grupo `Atendentes`.

### E-mails

O projeto usa a configuração `MAILERS` do Django 6.1 apontando para o backend de console. Os e-mails aparecem no terminal onde o `runserver` está rodando. Para o usuário receber, ele precisa ter e-mail preenchido. Para enviar e-mails de verdade, troque o backend em `config/settings.py` por um servidor SMTP.

## Rotas

| URL | Descrição | Quem acessa |
|---|---|---|
| `/` | Lista de chamados (aceita `?status=` e `?mine=1`) | Logado |
| `/novo/` | Abrir chamado | Logado |
| `/<id>/` | Detalhe e conversa | Dono do chamado ou atendente |
| `/<id>/comentar/` | Enviar comentário (POST) | Dono do chamado ou atendente |
| `/<id>/gerenciar/` | Mudar status, prioridade e responsável (POST) | Atendente |
| `/<id>/assumir/` | Assumir chamado (POST) | Atendente |
| `/contas/login/` | Login | Todos |
| `/contas/logout/` | Logout (somente POST, botão "Sair") | Logado |
| `/admin/` | Painel administrativo | Staff |

## Estrutura do projeto

```text
helpdesk/
  manage.py
  requirements.txt
  .gitignore
  config/
    settings.py          configurações do projeto
    urls.py              rotas principais (admin, contas, tickets)
  tickets/
    models.py            Category, Ticket, Comment
    permissions.py       is_agent e mixin de atendente
    forms.py             TicketForm, CommentForm, ManageForm
    views.py             lista, criação, detalhe, comentar, gerenciar, assumir
    urls.py              rotas do app
    admin.py             admin com comentários dentro do chamado
    tests.py             13 testes
    migrations/
      0001_initial.py
      0002_seed_data.py  categorias e grupo Atendentes
    templates/
      registration/login.html
      tickets/base.html
      tickets/ticket_list.html
      tickets/ticket_form.html
      tickets/ticket_detail.html
```

## Problemas comuns

| Sintoma | Causa e correção |
|---|---|
| `No module named 'django'` | O ambiente virtual não está ativo ou as dependências não foram instaladas. Ative o `.venv` e rode `python -m pip install -r requirements.txt` |
| `No module named 'pip'` dentro do `.venv` | O venv foi criado quebrado ou copiado de outra máquina. Apague (`rm -rf .venv`), recrie e instale de novo. No Ubuntu/Debian pode faltar `sudo apt install python3-venv python3-pip` |
| `Could not open requirements file` | Você não está na pasta do projeto. Rode `ls -A` e confira se `manage.py` e `requirements.txt` aparecem |
| `TemplateDoesNotExist` | Pasta de template no lugar errado. Confira `tickets/templates/tickets/` e `tickets/templates/registration/` |
| Logout dá erro 405 | O logout só aceita POST. Use o botão **Sair** do menu |
| Erro 403 ao assumir ou gerenciar | O usuário não é atendente. Coloque no grupo `Atendentes` ou marque staff |
| Atendente não aparece em Responsável | Ele precisa estar ativo e no grupo `Atendentes` (ou staff) |
| Formulário sem categorias | A migration de dados não rodou. Rode `python manage.py migrate` ou cadastre em `/admin/` |
| Nenhum e-mail no terminal | O usuário precisa ter e-mail preenchido e o servidor precisa estar rodando |
| Erro de conflito entre `MAILERS` e `EMAIL_BACKEND` | Use só `MAILERS`. Remova `EMAIL_BACKEND` do settings |

## Trabalhando em equipe com Git

Fluxo sugerido para a atividade em grupo:

```bash
# 1. clonar e entrar na pasta
git clone https://github.com/otzjoao/helpdesk.git
cd helpdesk

# 2. criar uma branch para a sua tarefa
git checkout -b minha-tarefa

# 3. trabalhar, testar e commitar
python manage.py test
git add .
git commit -m "Descreva o que foi feito"

# 4. enviar a branch
git push -u origin minha-tarefa
```

Depois, abra um Pull Request no GitHub para a branch `main`. Antes de começar uma nova tarefa, atualize a `main`:

```bash
git checkout main
git pull
```

Não commite `.venv`, `db.sqlite3` nem `.env`: o `.gitignore` já cuida disso. Cada pessoa cria o próprio banco com `migrate` e o próprio administrador com `createsuperuser`.

## Desafios extras

| Melhoria | Como começar |
|---|---|
| Prazo por prioridade (SLA) | Campo `due_at` calculado no `save()` e destaque dos chamados atrasados na lista |
| Dashboard | `Count` por status com `annotate` e uma página só para atendentes |
| Anexos | Model `Attachment` com `FileField`, `MEDIA_ROOT` e `MEDIA_URL` |
| Histórico | Model `TicketEvent` registrando quem mudou status, prioridade e responsável |
| API | Django REST Framework com os mesmos filtros de visibilidade |
| Comentar sem recarregar | htmx no formulário de comentário |
| Deploy | Variáveis de ambiente, PostgreSQL e Railway ou Render |

## Aviso sobre segurança

O `settings.py` contém uma `SECRET_KEY` de desenvolvimento e `DEBUG = True`. Isso é adequado para estudo. Para qualquer uso real, mova a chave para uma variável de ambiente (`.env`) e desligue o `DEBUG`.
