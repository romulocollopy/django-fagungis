## Uso 

### configure o arquivo settings.ini no mesmo path que o arquivo fabfile.py

    [DEPLOY]
    config_file=/opt/django/configs/apps/{{ project_name }}.conf
    deploy_hosts={{ user }}@{{ ip }}:{{ port }}
    project_name={{ project_name }}
    repository=git@{{ server }}:{{ user }}/{{ repo_name }}.git
    repository_type=git

    gunicorn_bind="127.0.0.1:{{ port }}"

    [APP]
    settings_file={{ project_name }}.settings.production
    debug=False

    [EMAIL]
    default_from_email=
    email_host=
    email_host_password=
    email_host_user=
    email_port=
    email_use_tls=
    email_use_ssl=


### deixei seu arquivo fabfile.py como este:
    # coding: utf-8
    import ConfigParser
    import os
    import sys


    from fabric.contrib import django
    from tasks_manager.tasks import *

    sys.path.append('../{{ project_name }}')

    ini = ConfigParser.ConfigParser()
    ini.readfp(open('settings.ini'))

    PROD_SETTINGS = ini.get('APP', 'settings_file')

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    django.settings_module(PROD_SETTINGS)

    from django.conf import settings


    env.SECRET_KEY = settings.SECRET_KEY


    @task
    def {{ project_name }}():
        env.repository_type = 'git'
        env.secret_key = settings.SECRET_KEY

        if 'branch' not in env:
            env.branch = 'master'
        #  name of your project - no spaces, no special chars
        env.project = ini.get('DEPLOY', 'project_name')
        #  hg repository of your project
        env.repository = ini.get('DEPLOY', 'repository')
        ##env.repository = '<URL REPO GIT/BIT - PASSADO POR LINHA DE COMANDO>'
        #  hosts to deploy your project, users must be sudoers
        env.hosts = ini.get('DEPLOY', 'deploy_hosts').split(',')
        ##env.hosts = < LISTA DE HOSTS - PASSADO POR LINHA DE COMANDO>
        # additional packages to be installed on the server
        env.additional_packages = [
            'git-core',
        ]
        #  system user, owner of the processes and code on your server
        #  the user and it's home dir will be created if not present
        env.django_user = 'django'
        # user group
        env.django_user_group = env.django_user

        env.django_project_settings = PROD_SETTINGS

        #############################
        # PATHS
        ##############################

        # the code of your project will be located here
        env.django_user_home = join('/opt', env.django_user)
        #  projects paths
        env.projects_path = join(env.django_user_home, 'projects')
        env.code_root = join(env.projects_path, env.project)

        # manage.py path - used to run manangment commands
        env.django_project_root = join(env.code_root, '{{ project_name }}')

        # this is the server path for all projects static_files
        STATIC_DIR = join(env.django_user_home, 'static_files')

        # MEDIA
        env.django_media_path = settings.MEDIA_ROOT  # Cara do settings
        env.django_media_root = settings.STATIC_DIR  # env usada para setar nginx.
        env.django_media_url = settings.MEDIA_URL

        # MEDIA
        env.django_static_path = settings.STATIC_ROOT  # usado no nginx
        env.django_static_root = settings.STATIC_DIR
        env.django_static_url = settings.STATIC_URL

        #
        # SOUTH CHECK                           ##
        #
        env.south_used = settings.INSTALLED_APPS.count('south') != 0

        #
        # VIRTUAL ENV                           ##
        #
        env.virtenv = join(env.django_user_home, 'envs', env.project)
        #  some virtualenv options, must have at least one
        env.virtenv_options = ['no-site-packages', ]  # 'distribute' is default
        #  location of your pip requirements file
        # http://www.pip-installer.org/en/latest/requirements.html#the-requirements-file-format
        #  set it to None to not use
        # cadu mudou abaixo
        # DEPLOY_DIR=os.path.dirname(__file__)
        #env.requirements_file = join(DEPLOY_DIR, 'requirements.txt')
        env.requirements_file = join(env.code_root, 'requirements', 'production.txt')
        #  always ask user for confirmation when run any tasks
        env.ask_confirmation = False

        # START gunicorn settings ###
        #  be sure to not have anything running on that port
        env.gunicorn_bind = "127.0.0.1:8032"
        env.rungunicorn_script = '%(django_user_home)s/scripts/rungunicorn_%(project)s.sh' % env
        env.gunicorn_workers = 1
        env.gunicorn_worker_class = "eventlet"
        env.gunicorn_loglevel = "info"
        # END gunicorn settings ###

        # START nginx settings ###
        # 'camargocorrea.znc.com.br'  # Only domain name, without 'www' or 'http://'
        env.nginx_server_name = " ".join(settings.ALLOWED_HOSTS)
        env.nginx_conf_file = '%(django_user_home)s/configs/nginx/%(project)s.conf' % env

        # Maximum accepted body size of client request, in MB
        env.nginx_client_max_body_size = 10
        env.nginx_htdocs = '%(django_user_home)s/htdocs' % env
        # will configure nginx with ssl on, your certificate must be installed
        # more info here: http://wiki.nginx.org/HttpSslModule
        env.nginx_https = False
        # END nginx settings ###

        # START supervisor settings ###
        # http://supervisord.org/configuration.html#program-x-section-settings
        # default: env.project
        env.supervisor_program_name = env.project
        env.supervisorctl = '/usr/bin/supervisorctl'  # supervisorctl script
        env.supervisor_autostart = 'true'  # true or false
        env.supervisor_autorestart = 'true'  # true or false
        env.supervisor_redirect_stderr = 'true'  # true or false
        env.supervisord_conf_file = '%(django_user_home)s/configs/supervisord/%(project)s.conf' % env
        # END supervisor settings ###


### O settings de produção deve seguir este modelo:
#### é importante o OPT_DJANGO_CONF_APP, CONF_FILE_EXISTS e principalmente o read_config_file para ler a secretkey do arquivo de conf
    # coding: utf-8
    import ConfigParser
    import os

    from .base import *

    OPT_DJANGO_CONF_APP = '/opt/django/configs/apps/{{ project_name }}.conf'
    CONF_FILE_EXISTS = os.path.exists(OPT_DJANGO_CONF_APP)


    def read_config_file():
        '''
        tenta ler arquivo de configuração
        Return: objeto do tipo ConfigParser
        '''
        config = ConfigParser.ConfigParser()
        config_file = None
        try:
            config_file = open(OPT_DJANGO_CONF_APP)
        except IOError as e:
            raise Exception(u"I/O error({0}): {1} - Possível arquivo inexistente.".format(e.errno, e.strerror))
        except:
            raise Exception(u"Erro não esperado:", sys.exc_info()[0])

        config.readfp(config_file)

        return config

    if CONF_FILE_EXISTS:
        config = read_config_file()
        SECRET_KEY = config.get('APP', 'secret_key')


    DJANGO_HOME = os.path.join('/opt', 'django')
    STATIC_DIR = os.path.join(DJANGO_HOME, 'static_files', '{{ project_name }}')
    MEDIA_ROOT = os.path.join(STATIC_DIR, 'media')
    STATIC_ROOT = os.path.join(STATIC_DIR, 'static')

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.',
            'NAME': '',
            'USER': '',
            'PASSWORD': '',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }



Se servidor novo, sem pacotes 

    fab *nome_app* setup

Se os pacotes do sistema já estão instalados, 

    fab *nome_app* setup:dependencies=no


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
1. __cria  chave ssh__ se não foi encontrado um arquivo em _/opt/django/.ssh/id_rsa.pub_ . Se já existe, mostra chave SSH pública encontrada.
1. __?__ Confirmação do usuário se a chave ssh encontrada tem acesso ao repositório. Caso contrário é possível adicionar e continuar a execução.
1. cria o diretório que conterá todos os _virtualenvs_ __deste servidor__.
1. baixa código pro servidor : __git clone__.
1. faz upload do arquivo de configuração (__config_template.conf__).
    
    Durante essa etapa, é criada a chave do django (_SECRET_KEY_ utilizado no settings.) A chave fica armazenada no arquivo de coonfiguaração de cada aplicação. 
    >IMPORTANTE Caso o arquivo já exista, a chave não é criada novamente para evitar problemas de perda de usuários e outros objetos que dependem da SECRET_KEY.

1. instala o apcote do _virtualenv_.
1. cria o virtualenv da aplicação que está sendo feito deploy.
1. Instala o pacote do __greenunicorn__.
1. Upload do template do __greenunicorn__
1. Upload do template do __supervidor__
1. Upload do template do __nginx__
1. Instala os pacotes python da aplicação (_requirements.txt_)







