# coding: utf-8
import getpass
import json
import logging
import os.path
import random
import string
import sys  # mostrar mesgs de erro

from ConfigParser import ConfigParser, DuplicateSectionError
from copy import copy
from json import loads
from os.path import abspath, basename, dirname, isfile
from StringIO import StringIO

from fabric.api import abort, cd, env, hide, puts
from fabric.api import get
from fabric.contrib import console, files
from fabric.contrib.files import exists, upload_template
from fabric.operations import put, run, settings, sudo

from .colors import red, puts_red, puts_blue, puts_green

base_path = dirname(abspath(__file__))


OPT_DJANGO_CONF_APPS = '/opt/django/configs/apps/%(project)s.conf'


def _remote_open(remote_path):
    '''
        Função que abre um arquivo no servidor
    '''
    output = StringIO()
    try:
        get(remote_path, output)
    except IOError as e:
        raise Exception(u"I/O error({0}): {1} - Possível arquivo inexistente.".format(e.errno, e.strerror))
    except:
        raise Exception(u"Erro não esperado:", sys.exc_info()[0])
    output.seek(0)
    return output


def _create_django_user():
    '''
        Função que cria e verifica se o usuário Django Existe
    '''
    puts_blue(u" Cria usuário __django__ ...", 1, bg=107)
    puts_blue("== Verifica / Cria usuário 'django' ...", 1, bg=107)
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = sudo('useradd -d %(django_user_home)s -m -r %(django_user)s -s /bin/bash' % env)
    if 'already exists' in res:
        puts('User \'%(django_user)s\' already exists, will not be changed.' % env)
        return
        #  set password
    sudo('passwd %(django_user)s' % env)


def _verify_sudo():
    ''' apenas verifica se o usuário é sudoers '''
    puts_blue("== Verificando SUDOER  ...", 1, bg=107)
    sudo('cd .')


def _install_nginx():
    '''
        Instala o NGINX
    '''
    puts_blue("== Instalando NginX ...")
    sudo("add-apt-repository -y ppa:nginx/stable")
    sudo("apt-get update")
    sudo("apt-get -y install nginx")
    sudo("/etc/init.d/nginx start")


def _install_dependencies():
    ''' Assegura que os pacotes Debian / Ubuntu estão instalados '''
    puts_blue("== instalando pacotes do sistema  ...", 1, bg=107)
    packages = [
        "python-software-properties",
        "python-dev",
        "build-essential",
        "python-pip",
        "supervisor",
        "git-core",
    ]
    sudo("apt-get update")
    sudo("apt-get -y install %s" % " ".join(packages))
    if "additional_packages" in env and env.additional_packages:
        sudo("apt-get -y install %s" % " ".join(env.additional_packages))
    _install_nginx()
    sudo("pip install --upgrade pip")


def _install_requirements():
    '''
        Instala o requirements com pip install -r
    '''
    puts_blue("== requirements.txt ... instalando pacotes python ...", 1, bg=107)
    ''' you must have a file called requirements.txt in your project root'''
    if 'requirements_file' in env and env.requirements_file:
        _virtenvsudo('pip install -r %s' % env.requirements_file)


def _install_gunicorn():
    """
        força a instalação gunicorn no seu virtualenv, mesmo que seja instalada a nível global.
        para mais detalhes: https://github.com/benoitc/gunicorn/pull/280
    """
    puts_blue("== instalando green unicorn ...")
    _virtenvsudo('pip install -I gunicorn')


def _install_virtualenv():
    '''
        Instala o Virtual Env
    '''
    puts_blue("== Instalando virtualenv ...")
    sudo('pip install virtualenv')


def _create_virtualenv():
    '''
        Cria um virtualenv
    '''
    puts_blue("== cria virtualenv ...")
    sudo('virtualenv --%s %s' % (' --'.join(env.virtenv_options), env.virtenv))
    sudo('chown %(django_user)s %(virtenv)s ' % env)


def _setup_directories():
    '''
    cria estrutura de diretórios do projeto Django no servidor
    e da permissão para o user django
    /opt/django
            /projects
            /logs
            /scripts
            /configs
            ...

    '''
    puts_blue("== Criando árvore de diretórios do user django ...", 1, bg=107)

    sudo('mkdir -p %(projects_path)s' % env)
    sudo('mkdir -p %(django_user_home)s/logs/' % env)
    sudo('chown %(django_user)s %(django_user_home)s/logs' % env)

    sudo('mkdir -p %(django_user_home)s/configs/apps' % env)

    #sudo('chmod -R 775 %s' % dirname(env.gunicorn_logfile))

    sudo('mkdir -p %s' % dirname(env.nginx_conf_file))
    sudo('mkdir -p %s' % dirname(env.supervisord_conf_file))
    sudo('mkdir -p %s' % dirname(env.rungunicorn_script))
    sudo('mkdir -p %(django_user_home)s/tmp' % env)
    sudo('mkdir -p %(nginx_htdocs)s' % env)
    sudo('echo "<html><body>nothing here</body></html> " > %(nginx_htdocs)s/index.html' % env)
    sudo('chown -R %(django_user)s %(django_user_home)s ' % env)


def _directories_exist():
    '''
        verifica se o diretório do nginx htdocs existe
    '''
    return exists(dirname(env.nginx_htdocs), use_sudo=True)


def _remove_project_files():
    '''
        remove arquivos do projeto
    '''
    sudo('rm -rf %s' % env.virtenv)
    sudo('rm -rf %s' % env.code_root)
    sudo('rm -rf %(nginx_htdocs)s' % env)
    sudo('rm -rf %(django_user_home)s/logs/%(project)s_gunicorn.log' % env)
    sudo('rm -rf %(django_user_home)s/logs/%(project)s_supervisord.log' % env)
    # remove nginx conf
    sudo('rm -rf %s' % env.nginx_conf_file)
    sudo('rm -rf /etc/nginx/sites-enabled/%s' % basename(env.nginx_conf_file))
    # remove supervisord conf
    sudo('rm -rf %s' % env.supervisord_conf_file)
    sudo('rm -rf /etc/supervisor/conf.d/%s' % basename(env.supervisord_conf_file))
    # remove rungunicorn script
    sudo('rm -rf %s' % env.rungunicorn_script)


def _virtenvrun(command):
    '''
        roda um comando no virtualenv
    '''
    activate = 'source %s/bin/activate' % env.virtenv
    run(activate + ' && ' + command, )


def _virtenvsudo(command):
    '''
        roda um comando no virtualenv com sudo
    '''
    activate = 'source %s/bin/activate' % env.virtenv
    sudo(activate + ' && ' + command)  # , user=env.django_user)


def _git_clone():
    '''
        Faz um clone de um repositório
    '''
    puts_blue("== CLONE do repositório ...", 1, bg=107)

    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        with cd('%(django_user_home)s' % env):
            sudo('git clone %(repository)s %(code_root)s' % env, user=env.django_user)
    with cd(env.code_root):
        sudo('git fetch' % env, user=env.django_user)
        sudo('git checkout %(branch)s' % env, user=env.django_user)


def _test_nginx_conf():
    '''
        Testa configurações do nginx
    '''
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = sudo('nginx -t -c /etc/nginx/nginx.conf')
    if 'test failed' in res:
        abort(red('NGINX configuration test failed! Please review your parameters.'))


def _reload_nginx():
    '''
        reaload no nginx ($ nginx -s reload)
    '''
    sudo('nginx -s reload')


def _upload_nginx_conf():
    '''
        upload nas configurações do nginx
    '''
    puts_blue(u" enviando arquivo de conf. do NGINX  ...", 1, bg=107)
    local_nginx_conf_file = 'nginx.conf'
    if env.nginx_https:
        local_nginx_conf_file = 'nginx_https.conf'
    if isfile('conf/%s' % local_nginx_conf_file):
        ''' we use user defined conf template '''
        template = 'conf/%s' % local_nginx_conf_file
    else:
        template = '%s/conf/%s' % (base_path, local_nginx_conf_file)
    context = copy(env)
    # Template
    upload_template(template, env.nginx_conf_file,
                    context=context, backup=False, use_sudo=True)

    sudo('ln -sf %s /etc/nginx/sites-enabled/%s' % (env.nginx_conf_file, basename(env.nginx_conf_file)))
    sudo('ln -sf %s /etc/nginx/sites-available/%s' % (env.nginx_conf_file, basename(env.nginx_conf_file)))
    _test_nginx_conf()
    _reload_nginx()


def _reload_supervisorctl():
    '''
        Reload no supervisorctl
    '''
    #sudo('%(supervisorctl)s reread' % env)
    sudo('%(supervisorctl)s update' % env)
    #sudo('%(supervisorctl)s restart %(supervisor_program_name)s' % env)
    #sudo('%(supervisorctl)s reload' % env) # desnecessario reload, e leva mais tempo


def _upload_supervisord_conf():
    ''' upload nas configurações do supervisord '''
    puts_blue("Enviando arquivo de conf. do supervisor ...", 1, bg=107)
    if isfile('conf/supervisord.conf'):
        ''' we use user defined supervisord.conf template '''
        template = 'conf/supervisord.conf'
    else:
        template = '%s/conf/supervisord.conf' % base_path
    upload_template(template, env.supervisord_conf_file,
                    context=env, backup=False, use_sudo=True)
    sudo('ln -sf %s /etc/supervisor/conf.d/%s' % (env.supervisord_conf_file, basename(env.supervisord_conf_file)))
    _reload_supervisorctl()


def _atualiza_projs(database_name):
    if os.path.exists('projs.json'):
        j = json.load(open('projs.json'))
        query_file_path = '/tmp/%(project)s_query.sql' % env
        fd = StringIO()
        fd.name = '%(project)s_query.sql' % env
        sudo('touch %s' % query_file_path)
        for key, value in j.items():
            fd.write(value['postgis'] + '\n')
            srid_key = '<%s>' % key
            with settings(warn_only=True):
                res = sudo('grep -H "%s" /usr/share/proj/epsg ' % srid_key)
                if not srid_key in res:
                    string_epsg = "%s %s" % (srid_key, value['proj4text'])
                    sudo("echo '%s' >> %s" % (string_epsg, '/usr/share/proj/epsg'))

        put(fd, query_file_path, use_sudo=True)
    sudo("psql %s < %s" % (database_name, query_file_path), user='postgres')


def _setup_database():
    quer_criar_template = False
    quer_criar_user = False
    quer_criar_db = False
    puts_blue("Setup do Bano de Dados")
    with cd('%(django_user_home)s' % env):
        if 'postgis' in env.django_settings.DATABASES['default']['ENGINE']:
            # template postgis existe
            with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
                res = sudo('psql -tAc "SELECT \'template_postgis_encontrado\';" template_postgis', user='postgres')
                if not 'template_postgis_encontrado' in res:
                    # quer criar o template postgis?
                    quer_criar_template = console.confirm(u'quer criar o template postgis?')
        if quer_criar_template:
            script_path = '%s/scripts/create_template_postgis-debian.sh' % base_path
            remote = '/opt/django/create_template_postgis-debian.sh'
            if not files.exists(remote, use_sudo=True, verbose=False):
                put(
                    open(script_path),
                    remote,
                    use_sudo=True
                )
            sudo('/bin/bash %s' % remote, user='postgres')
            # cria template postgis

        rolname = env.django_settings.DATABASES['default']['USER']
        # user existe
        with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
            res = sudo(
                'psql -tAc \
                "SELECT \'user_encontrado\' FROM ( \
                    SELECT count(*) FROM pg_roles WHERE rolname=\'%s\'\
                ) AS COUNT WHERE COUNT.count >= 1;"' % rolname,
                user='postgres'
            )
            if not 'user_encontrado' in res:
                quer_criar_user = console.confirm(u'quer criar o user %s?' % rolname)

        if quer_criar_user:
            _create_postgre_user()

        database = env.django_settings.DATABASES['default']['NAME']
        # user existe
        with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
            res = sudo('psql -tAc "SELECT \'BD_encontrado\';" %s' % database, user='postgres')
            if not 'BD_encontrado' in res:
                quer_criar_db = console.confirm(u'quer criar o Database %s?' % database)
        if quer_criar_db:
            _create_postgre_database()

        _atualiza_projs(database)


def _setup_django_project():
    '''
        OLD: _prepare_django_project():
        Prepara o projeto Django
        roda o syncdb
        O MIGRATIONS eh fake !
    '''
    puts_blue(u" SETUP: Executando syncdb / migrations", 1, bg=107)
    with cd(env.django_project_root):
        if env.south_used:
            _virtenvrun('python manage.py syncdb --all --noinput --verbosity=1 --settings=%(django_project_settings)s' % env)
            _virtenvrun('python manage.py migrate --fake --noinput --verbosity=1 --settings=%(django_project_settings)s' % env)
        else:
            _virtenvrun('python manage.py syncdb --noinput --verbosity=1 --settings=%(django_project_settings)s' % env)


def _deploy_django_project():
    '''
        tal como o _setup_django_project
        roda o syncdb, migrate
        executando os migrations
    '''
    puts_blue(u" deploy: Executando syncdb / migrations ...", 1, bg=107)
    with cd(env.django_project_root):
        _virtenvrun('python manage.py syncdb --noinput --verbosity=1 --settings=%(django_project_settings)s' % env)
        if env.south_used:
            _virtenvrun('python manage.py migrate --noinput --verbosity=1 --settings=%(django_project_settings)s' % env)


def _collect_static():

    puts_blue(u" 'coletando' arquivos estáticos ...", 1, bg=107)
    with cd(env.django_project_root):
        _virtenvsudo('python manage.py collectstatic --noinput --settings=%(django_project_settings)s' % env)


def _prepare_media_path():
    '''
        Cria o diretório de media
    '''
    puts_blue(u" Prepara diretórios para receber 'media files' ...", 1, bg=107)
    puts_blue(u" Diretório criado em: %s " % env.django_media_path.rstrip('/'))
    path = env.django_media_path.rstrip('/')
    sudo('mkdir -p %s' % path)
    sudo('chmod -R 775 %s' % path)
    sudo('chown -R %s %s' % (env.django_user, path))


def _upload_rungunicorn_script():
    ''' upload nas configurações do rungunicorn '''
    puts_blue(" Copiando SCRIPT do gunicorn ...", 1, bg=107)
    if isfile('scripts/rungunicorn.sh'):
        ''' we use user defined rungunicorn file '''
        template = 'scripts/rungunicorn.sh'
    else:
        template = '%s/scripts/rungunicorn.sh' % base_path
    upload_template(template, env.rungunicorn_script,
                    context=env, backup=False,  use_sudo=True)
    sudo('chmod +x %s' % env.rungunicorn_script)


def _supervisor_restart():
    '''
        Restarta o supervisor
    '''
    puts_blue(" __restart__ da aplicação via supervisor ...", 1, bg=107)
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = sudo('%(supervisorctl)s stop %(supervisor_program_name)s' % env)
        puts_blue("-> Parando App:")
        puts_blue(" Mensagem do supervisor: %s " % (res))

        #start app
        res = sudo('%(supervisorctl)s start %(supervisor_program_name)s' % env)
        puts_blue("-> Reiniciando a App:")
        if 'ERROR' in res:
            puts_red("-> Erro ao reiniciar a app : %s" % env.supervisor_program_name)
        else:
            puts_green("==========================================")
            puts_green("      %s   iniciado com sucesso           " % env.supervisor_program_name)
            puts_green("==========================================")

        puts_blue(" Mensagem do supervisor: %s " % (res))


def _check_ssh_key():
    '''
    Verifica/cria arquivo de chave SSH
    e mostra conteúdo para adicionar ao serviço de repo.
    '''
    puts_blue("== Verifica chave SSH de acesso ao repo ...", 1, bg=107)
    res = files.exists("/opt/django/.ssh/id_rsa.pub", use_sudo=True, verbose=False)
    if not res:

        puts_red("chave pública do user django não encontrada em /opt/django/.ssh/id_rsa.pub")
        res = console.confirm("Criar chave agora ?", default=True)
        if res:
            res = sudo('chown django -R /opt/django')
            sudo('ssh-keygen', user=env.django_user)
    puts_red(" ==================[ L E I A  ]====================")
    puts_red(" !!!!!!!!!!!!!!! Chave pública utilizada !!!!!!!!!!")
    puts_red(" essa chave será utilizada para acessar o repositório.")
    sudo('cat /opt/django/.ssh/id_rsa.pub', user=env.django_user)
    res = console.confirm("Chave de deploy incluida no repo ?", default=True)


def _read_config_file():
    '''
    tenta ler arquivo de configuração
    Return: objeto do tipo ConfigParser
    '''

    opt_django_config_file = OPT_DJANGO_CONF_APPS % env
    config = ConfigParser()
    config_file = _remote_open(opt_django_config_file)
    config.readfp(config_file)
    return config


def _generate_secret_key():
    '''
        Gera uma secret key randomicamente
    '''
    secret_key = ''.join([random.SystemRandom().choice(string.printable[:-15]) for i in range(100)]).replace(' ', '')
    return secret_key


def _copy_ini_to_config(config):
    ini = env.proj_ini

    if ini.has_section('COPY_APP'):
        for op in ini.options('COPY_APP'):
            config.set('APP', op, ini.get('COPY_APP', op))


def _set_manual_config_file(config=None):
    '''
        Seta o arquivo de configuração em
        {{ django_user_home }}/configs/apps/{{ project_name }}.conf
        manualmente, entre com um json
    '''
    # path de destino
    destination_path = '%(django_user_home)s/configs/apps/%(project)s.conf' % env

    # lê arquivo de configuração
    if not config:
        config = _read_config_file()
    _copy_ini_to_config(config)

    # imprime help do JSON
    puts_blue(u"== Setar variaveis sensiveis ==")
    puts_blue(u"== Entre com um JSON no formato ==")
    puts_blue(u'{')
    puts_blue(u'    "Section": {')
    puts_blue(u'        "key": "value",')
    puts_blue(u'        "key2": "value"')
    puts_blue(u'    },')
    puts_blue(u'    "Section2": {')
    puts_blue(u'        "key": "value",')
    puts_blue(u'        "key2": "value"')
    puts_blue(u'    }')
    puts_blue(u'}')
    confirma = False
    # espera confirmação de arquivo de config valido
    while not confirma:
        json_valido = False
        # espera um json válido
        while not json_valido:
            # lê o json do prompt
            json_string = console.prompt(u'Entre com o JSON:', default='{}')
            try:
                # verifica se o json é válido
                json_dict = loads(json_string)
                json_valido = True
            except:
                puts_red(u'== JSON Invalido ==')
        # escreve seções
        for section, dic in json_dict.items():
            try:
                config.add_section(section)
            except DuplicateSectionError:
                # Não faz nada se a section já existir
                pass
            for key, value in dic.items():
                config.set(section, key, value)
        puts_blue(u"== Configuracao Final ==")
        # imprime as configs
        _print_configs(config)

        confirma = console.confirm(u'O arquivo de configuracao esta correto?')

    fd = StringIO()
    fd.name = '%(project)s.conf' % env
    config.write(fd)
    put(fd, destination_path, use_sudo=True)
    sudo('chown %(django_user)s ' % env + destination_path)


def _set_config_file():
    '''
    faz upload do arquivo de config
    baseado no template "config_template.conf"
    e seta a secret_key
    '''
    opt_django_config_file = OPT_DJANGO_CONF_APPS % env
    # garante que a secret_key e uma app já existenete não seja trocada -> destroi users no banco
    generate_secret = True
    if files.exists(opt_django_config_file, use_sudo=True, verbose=False):
        config = _read_config_file()
        if config.has_section('APP'):
            env.secret_key = config.get('APP', 'secret_key')
            generate_secret = False
    else:
        sudo('touch %s' % opt_django_config_file, user=env.django_user)
        config = _read_config_file()

    if generate_secret:
        env.secret_key = _generate_secret_key()

    destination_path = '%(django_user_home)s/configs/apps/%(project)s.conf' % env

    if not config.has_section('APP'):
        config.add_section('APP')
    config.set('APP', 'secret_key', env.secret_key or '')

    _set_manual_config_file(config=config)

    sudo('chmod ug+rw  %s' % destination_path)


def _print_configs(config):
    '''
        imprime um arquivo de configuração '.conf'
    '''
    for section in config.sections():
        puts_red(u"[%s]" % section)
        for option in config.items(section):
            puts_red(u"%s=%s" % option)


def _print_nginx_configs():
    sudo('cat %s' % env.nginx_conf_file)


def _print_supervisor_configs():
    sudo('cat %s' % env.supervisord_conf_file)


def _create_postgre_user():
    puts_blue(u"== Criar um usario no postgreSQL ==")
    db_user = console.prompt(u'Username:', default=env.django_user)
    confirm_pass = False
    while not confirm_pass:
        puts_blue(u"== Digite o password do usuario e a confirmacao ==")
        db_pass = getpass.getpass(u'Password: ')
        db_passc = getpass.getpass(u'cofirmacao: ')
        confirm_pass = db_pass == db_passc
        if not confirm_pass:
            puts_red(u"== Passwords Diferentes ==")

    options = [
        ('SUPERUSER', 'NOSUPERUSER'),
        ('CREATEDB', 'NOCREATEDB'),
        ('CREATEROLE', 'NOCREATEROLE'),
        ('INHERIT', 'NOINHERIT'),
        ('LOGIN', 'NOLOGIN'),
    ]
    confirm_options = []
    for option in options:
        ok = console.confirm(u'%s?' % option[0])
        confirm_options.append(option[int(not ok)])

    confirm_options = ' '.join(confirm_options)

    ddl = "CREATE USER %s WITH %s ENCRYPTED PASSWORD E'%s'" % (db_user, confirm_options, db_pass)
    puts_green('== DDL Gerada ==')
    puts_green(ddl.replace("E'%s'" % db_pass, "E'%s'" % ('*' * len(db_pass))))
    sudo(u'psql -c "%s;"' % ddl, user='postgres', quiet=True)


def _create_postgre_database():
    puts_blue(u"== Criar um database no postgreSQL ==")
    db_user = console.prompt(u'Owner:', default=env.django_user)
    db_name = console.prompt(u'Database Name:', default=env.project)
    db_template = console.confirm(u'use "template_postgis"?')

    if db_template:
        template = u" TEMPLATE template_postgis"
    else:
        template = u''

    ddl = "CREATE DATABASE %s WITH OWNER %s%s" % (db_name, db_user, template)
    sudo(u'psql -c "%s;"' % ddl, user='postgres')


def gen_get_config_or(config):
    def inner(section, option, default=None):
        try:
            return config.get(section, option)
        except:
            return default
    return inner
