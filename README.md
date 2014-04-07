## Uso 

### Subistitua o que estiver entre {{  }}

### configure o arquivo _settings.ini_ no mesmo path que o arquivo _fabfile.py_

    [DEPLOY]
    config_file=/opt/django/configs/apps/{{ project_name }}.conf
    deploy_hosts={{ user }}@{{ ip }}:{{ port }}
    project_name={{ project_name }}
    repository=git@{{ server }}:{{ user }}/{{ repo_name }}.git
    repository_type=git

    gunicorn_bind="127.0.0.1:{{ port }}"
    additional_packages=''

    [APP]
    settings_file={{ project_name }}.settings.production


### deixei seu arquivo _fabfile.py_ como este:
    # coding: utf-8
    import os
    import sys

    from ConfigParser import ConfigParser

    from fabric.contrib import django
    from tasks_manager.tasks import *
    from tasks_manager.generic_fabfile import generic_fabfile

    from django.conf import settings

    # Abre o Arquivo settings.ini com o ConfigParser
    ini = ConfigParser()
    ini.readfp(open('settings.ini'))

    # Lê o nome do projeto
    PROJECT_NAME = ini.get('DEPLOY', 'project_name')
    try:
        PROJECT_DIR = ini.get('DEPLOY', 'project_dir')
    except:
        PROJECT_DIR = False

    # Lê qual settings usar na produção
    PROD_SETTINGS = ini.get('APP', 'settings_file')

    sys.path.append(join('..', PROJECT_NAME))


    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    django.settings_module(PROD_SETTINGS)


    @task
    def {{ project_name }}():
        # chama o fabfile genérico
        # reescrever aqui caso seja necessário
        generic_fabfile(env, settings, ini, PROJECT_NAME, PROJECT_DIR, PROD_SETTINGS)()



### O settings de produção deve seguir este modelo:
#### é importante o _OPT_DJANGO_CONF_APP_, _read_config_file_ para ler a secretkey do arquivo de conf e o  _gen_get_config_or_ existirem no arquivo _utils.py_

___settings/production.py___

    # coding: utf-8
    import os

    from .base import *
    from .utils import gen_get_config_or, read_config_file
    
    config = read_config_file()
    get_config_or = gen_get_config_or(config)


    SECRET_KEY = get_config_or('APP', 'secret_key', SECRET_KEY)
    
    DJANGO_HOME = os.path.join('/opt', 'django')
    STATIC_DIR = os.path.join(DJANGO_HOME, 'static_files', '{{ project_name }}')
    MEDIA_ROOT = os.path.join(STATIC_DIR, 'media')
    STATIC_ROOT = os.path.join(STATIC_DIR, 'static')
    
    DATABASE_NAME = get_config_or('DATABASE', 'NAME', default='')
    DATABASE_USER = get_config_or('DATABASE', 'USER', default='')
    DATABASE_PASS = get_config_or('DATABASE', 'PASSWORD', default='')
    DATABASE_HOST = get_config_or('DATABASE', 'HOST', default='localhost')
    DATABASE_PORT = get_config_or('DATABASE', 'PORT', default='5432')
    
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.',
            'NAME': DATABASE_NAME,
            'USER': DATABASE_USER,
            'PASSWORD': DATABASE_PASS,
            'HOST': DATABASE_HOST,
            'PORT': DATABASE_PORT,
        }
    }

___settings/utils.py___

    # coding: utf-8
    from ConfigParser import ConfigParser

    OPT_DJANGO_CONF_APP = '/opt/django/configs/apps/{{ project_name }}.conf'


    def gen_get_config_or(config):
        def inner(section, option, default=None):
            try:
                return config.get(section, option)
            except:
                return default
        return inner


    def read_config_file():
        '''
        tenta ler arquivo de configuração
        Return: objeto do tipo ConfigParser
        '''
        config = ConfigParser()
        config_file = None
        try:
            config_file = open(OPT_DJANGO_CONF_APP)
        except:
            return config

        config.readfp(config_file)

        return config
        
----

#### Se servidor novo, sem pacotes 

    $ fab {{ project_name }} setup

#### Se os pacotes do sistema já estão instalados, 

    $ fab {{ project_name }} setup:dependencies=no


##Como funciona ?

###SETUP 
1. faz teste de variáveis do setup. 
1. __?__ Confirmação do usuário se inicia setup.
1. Inicia cronômetro
1. SUDO: verifica se é possível executar sudo com um _cd_
1. Verifica se a _home_ do user _django_ existe
1. __Instala pacotes do sistema__ se a _home_ não existe, __e se__ o parametros _dependencies_ é igual __"yes"__
1. __cria user _django_ __ se _home_ não existe
1. __cria direórios da _home_ __ se _home_ não existe
1. __cria chave ssh__ se não foi encontrado um arquivo em _/opt/django/.ssh/id_rsa.pub_ . Se já existe, mostra chave SSH pública encontrada.
1. __?__ Confirmação do usuário se a chave ssh encontrada tem acesso ao repositório. Caso contrário é possível adicionar e continuar a execução.
1. cria o diretório que conterá todos os _virtualenvs_ __deste servidor__.
1. baixa código pro servidor : __git clone__.
1. faz upload do arquivo de configuração (__config_template.conf__).
    
    Durante essa etapa, é criada a chave do django (_SECRET_KEY_ utilizado no settings.) A chave fica armazenada no arquivo de coonfiguaração de cada aplicação. 
    >IMPORTANTE Caso o arquivo já exista, a chave não é criada novamente para evitar problemas de perda de usuários e outros objetos que dependem da SECRET_KEY.
    
    Também é pedido para você entrar um um Json no formato:
    
            {
                "Section": {
                    "key": "value",
                    "key2": "value"
                },
                "Section2": {
                    "key": "value",
                    "key2": "value"
                }
            }
    Para configurar variáveis sensíveis no servidor como _DATABASE_NAME_, _DATABASE_USER_, _DATABASE_PASS_, _DATABASE_HOST_ e _DATABASE_PORT_ essas variáveis são recuperadas no settings com o _get_config_or_. Ao final será mostrado como ficou o novo arquivo de configruação, e pedirá para confirmar as alterações.

1. instala o apcote do _virtualenv_.
1. cria o virtualenv da aplicação que está sendo feito deploy.
1. Instala o pacote do __greenunicorn__.
1. Upload do template do __greenunicorn__
1. Upload do template do __supervidor__
1. Upload do template do __nginx__
1. Instala os pacotes python da aplicação (_requirements.txt_)


### Tasks
1. setup: Realiza o Setup Inicial do projeto instala dependências por padrão utilizar _dependencies=no_ para não instalá-las
1. deploy: Realiza o deploy do projeto
1. remove: Remove os arquivos do projeto do servidor
1. hg_pull: Realiza um HG Pull
1. git_pull: Realiza um GIT Pull
1. reset_nginx: Reseta o NGINX
1. test_configuration: Roda os testes de configruação
1. print_configs: Imprime o arquivo de configuração do projeto
    > tem 2 parâmetros nginx: printa as congigs do nginx e superviort: printa as consigs do supervidor
    > fab znc_dummy print_configs:supervisor,nginx
1. manage: Roda
1. restart: Restarta o supervisor
1. set_manual_config_file: Seta manualmente o arquivo de configuração através de um JSON
1. suggestion_of_port: Task que sugere uma porta para ser utilizada na aplicação
