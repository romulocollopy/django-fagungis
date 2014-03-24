# coding: utf-8
import logging
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

from .colors import blue, red, green

base_path = dirname(abspath(__file__))


OPT_DJANGO_CONF_APPS = '/opt/django/configs/apps/%(project)s.conf'


def _remote_open(remote_path):
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
    puts(blue("== Verifica / Cria usuário 'django' ...", 1, bg=107))
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = sudo('useradd -d %(django_user_home)s -m -r %(django_user)s -s /bin/bash' % env)
    if 'already exists' in res:
        puts('User \'%(django_user)s\' already exists, will not be changed.' % env)
        return
        #  set password
    sudo('passwd %(django_user)s' % env)


def _verify_sudo():
    ''' we just check if the user is sudoers '''
    puts(blue("== Verificando SUDOER  ...", 1, bg=107))
    sudo('cd .')


def _install_nginx():
    # add nginx stable ppa
    puts(blue("== Instalando NginX ..."))
    sudo("add-apt-repository -y ppa:nginx/stable")
    sudo("apt-get update")
    sudo("apt-get -y install nginx")
    sudo("/etc/init.d/nginx start")


def _install_dependencies():
    ''' Ensure those Debian/Ubuntu packages are installed '''
    puts(blue("== instalando pacotes do sistema  ...", 1, bg=107))
    packages = [
        "python-software-properties",
        "python-dev",
        "build-essential",
        "python-pip",
        "supervisor",
    ]
    sudo("apt-get update")
    sudo("apt-get -y install %s" % " ".join(packages))
    if "additional_packages" in env and env.additional_packages:
        sudo("apt-get -y install %s" % " ".join(env.additional_packages))
    _install_nginx()
    sudo("pip install --upgrade pip")


def _install_requirements():
    puts(blue("== requirements.txt ... instalando pacotes python ...", 1, bg=107))
    ''' you must have a file called requirements.txt in your project root'''
    if 'requirements_file' in env and env.requirements_file:
        _virtenvsudo('pip install -r %s' % env.requirements_file)


def _install_gunicorn():
    """ force gunicorn installation into your virtualenv, even if it's installed globally.
    for more details: https://github.com/benoitc/gunicorn/pull/280 """
    puts(blue("== instalando green unicorn ..."))
    _virtenvsudo('pip install -I gunicorn')


def _install_virtualenv():
    puts(blue("== Instalando virtualenv ..."))
    sudo('pip install virtualenv')


def _create_virtualenv():
    puts(blue("== cria virtualenv ..."))
    sudo('virtualenv --%s %s' % (' --'.join(env.virtenv_options), env.virtenv))


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
    puts(blue("== Criando árvore de diretórios do user django ...", 1, bg=107))

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
    return exists(dirname(env.nginx_htdocs), use_sudo=True)


def _remove_project_files():
    sudo('rm -rf %s' % env.virtenv)
    sudo('rm -rf %s' % env.code_root)
    sudo('rm -rf %s' % env.gunicorn_logfile)
    sudo('rm -rf %s' % env.supervisor_stdout_logfile)
    # remove nginx conf
    sudo('rm -rf %s' % env.nginx_conf_file)
    sudo('rm -rf /etc/nginx/sites-enabled/%s' % basename(env.nginx_conf_file))
    # remove supervisord conf
    sudo('rm -rf %s' % env.supervisord_conf_file)
    sudo('rm -rf /etc/supervisor/conf.d/%s' % basename(env.supervisord_conf_file))
    # remove rungunicorn script
    sudo('rm -rf %s' % env.rungunicorn_script)


def _virtenvrun(command):
    activate = 'source %s/bin/activate' % env.virtenv
    run(activate + ' && ' + command, )


def _virtenvsudo(command):
    activate = 'source %s/bin/activate' % env.virtenv
    sudo(activate + ' && ' + command)  # , user=env.django_user)


def _git_clone():
    puts(blue("== CLONE do repositório ...", 1, bg=107))
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        with cd(env.code_root):
            res = sudo('git pull origin %(branch)s' % env, user=env.django_user)
    logging.error('code root not exists: %s' % res)
    if 'No such file or directory' in res:
        sudo('git clone %(repository)s %(code_root)s' % env, user=env.django_user)
    #with cd(env.code_root):
    #    sudo('git config --global user.email you@example.com', user=env.django_user)
    #    sudo('git config --global user.name foo', user=env.django_user)


def _test_nginx_conf():
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = sudo('nginx -t -c /etc/nginx/nginx.conf')
    if 'test failed' in res:
        abort(red('NGINX configuration test failed! Please review your parameters.'))


def _reload_nginx():
    sudo('nginx -s reload')


def _upload_nginx_conf():
    ''' upload nginx conf '''
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
    #sudo('%(supervisorctl)s reread' % env)
    sudo('%(supervisorctl)s update' % env)
    #sudo('%(supervisorctl)s restart %(supervisor_program_name)s' % env)
    #sudo('%(supervisorctl)s reload' % env) # desnecessario reload, e leva mais tempo


def _upload_supervisord_conf():
    ''' upload supervisor conf '''
    if isfile('conf/supervisord.conf'):
        ''' we use user defined supervisord.conf template '''
        template = 'conf/supervisord.conf'
    else:
        template = '%s/conf/supervisord.conf' % base_path
    upload_template(template, env.supervisord_conf_file,
                    context=env, backup=False, use_sudo=True)
    sudo('ln -sf %s /etc/supervisor/conf.d/%s' % (env.supervisord_conf_file, basename(env.supervisord_conf_file)))
    _reload_supervisorctl()


def _prepare_django_project():
    with cd(env.django_project_root):
        _virtenvrun('python manage.py syncdb --noinput --verbosity=1 --settings=%(django_project_settings)s' % env)
        if env.south_used:
            _virtenvrun('python manage.py migrate --noinput --verbosity=1 --settings=%(django_project_settings)s' % env)
        _virtenvsudo('python manage.py collectstatic --noinput --settings=%(django_project_settings)s' % env)


def _prepare_media_path():
    path = env.django_media_path.rstrip('/')
    sudo('mkdir -p %s' % path)
    sudo('chmod -R 775 %s' % path)
    sudo('chown -R %s %s' % (env.django_user, path))


def _upload_rungunicorn_script():
    ''' upload rungunicorn conf '''
    if isfile('scripts/rungunicorn.sh'):
        ''' we use user defined rungunicorn file '''
        template = 'scripts/rungunicorn.sh'
    else:
        template = '%s/scripts/rungunicorn.sh' % base_path
    upload_template(template, env.rungunicorn_script,
                    context=env, backup=False, use_sudo=True)
    sudo('chmod +x %s' % env.rungunicorn_script)


def _supervisor_restart():
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = sudo('%(supervisorctl)s restart %(supervisor_program_name)s' % env)
    if 'ERROR' in res:

        print red("%s NOT STARTED!" % env.supervisor_program_name)
    else:
        print green("%s correctly started!" % env.supervisor_program_name)


def _check_ssh_key():
    '''
    Verifica/cria arquivo de chave SSH
    e mostra conteúdo para adicionar ao serviço de repo.
    '''
    puts(blue("== Verifica chave SSH de acesso ao repo ...", 1, bg=107))
    res = files.exists("/opt/django/.ssh/id_rsa.pub", use_sudo=True, verbose=False)
    if not res:

        puts(red("chave pública do user django não encontrada em /opt/django/.ssh/id_rsa.pub"))
        res = console.confirm("Criar chave agora ?", default=True)
        if res:
            res = sudo('chown django -R /opt/django')
            sudo('ssh-keygen', user=env.django_user)
    puts(red(" ==================[ L E I A  ]===================="))
    puts(red(" !!!!!!!!!!!!!!! Chave pública utilizada !!!!!!!!!!"))
    puts(red(" essa chave será utilizada para acessar o repositório."))
    sudo('cat /opt/django/.ssh/id_rsa.pub', user=env.django_user)
    res = console.confirm("Chave de deploy incluida no repo ?", default=True)


def _read_config_file():
    '''
    tenta ler arquivo de configuração
    Return: objeto do tipo ConfigParser
    '''

    OPT_DJANGO_CONF_APP = OPT_DJANGO_CONF_APPS % env
    config = ConfigParser()
    config_file = _remote_open(OPT_DJANGO_CONF_APP)
    config.readfp(config_file)
    return config


def _generate_secret_key():
    secret_key = ''.join([random.SystemRandom().choice(string.printable[:-15]) for i in range(100)]).replace(' ', '')
    return secret_key


def _set_manual_config_file(config=None):
    # path de destino
    destination_path = '%(django_user_home)s/configs/apps/%(project)s.conf' % env

    # lê arquivo de configuração
    if not config:
        config = _read_config_file()
    # imprime help do JSON
    puts(blue(u"== Setar variaveis sensiveis =="))
    puts(blue(u"== Entre com um JSON no formato =="))
    puts(blue(u'{'))
    puts(blue(u'    "Section": {'))
    puts(blue(u'        "key": "value",'))
    puts(blue(u'        "key2": "value"'))
    puts(blue(u'    },'))
    puts(blue(u'    "Section2": {'))
    puts(blue(u'        "key": "value",'))
    puts(blue(u'        "key2": "value"'))
    puts(blue(u'    }'))
    puts(blue(u'}'))
    confirma = False
    # espera confirmação de arquivo de config valido
    while not confirma:
        json_valido = False
        # espera um json válido
        while not json_valido:
            # lê o json do prompt
            json_string = console.prompt(u'Entre com o JSON:')
            try:
                # verifica se o json é válido
                json_dict = loads(json_string)
                json_valido = True
            except:
                puts(red(u'== JSON Invalido =='))
        # escreve seções
        for section, dic in json_dict.items():
            try:
                config.add_section(section)
            except DuplicateSectionError:
                # Não faz nada se a section já existir
                pass
            for key, value in dic.items():
                config.set(section, key, value)
        puts(blue(u"== Configuracao Final =="))
        # imprime as configs
        _print_configs(config)

        confirma = console.confirm(u'O arquivo de configuracao esta correto?')

    fd = StringIO()
    fd.name = '%(project)s.conf' % env
    config.write(fd)
    put(fd, destination_path)


def _set_config_file():
    '''
    faz upload do arquivo de config
    baseado no template "config_template.conf"
    e seta a secret_key
    '''
    OPT_DJANGO_CONF_APP = OPT_DJANGO_CONF_APPS % env
    # garante que a secret_key e uma app já existenete não seja trocada -> destroi users no banco
    generate_secret = True
    if files.exists(OPT_DJANGO_CONF_APP, use_sudo=True, verbose=False):
        config = _read_config_file()
        if config.has_section('APP'):
            env.secret_key = config.get('APP', 'secret_key')
            generate_secret = False
    if generate_secret:
        env.secret_key = _generate_secret_key()

    destination_path = '%(django_user_home)s/configs/apps/%(project)s.conf' % env

    config.add_section('APP')
    config.set('APP', 'secret_key', env.secret_key or '')

    _set_manual_config_file(config=config)

    sudo('chmod ug+rw  %s' % destination_path)


def _print_configs(config):
    for section in config.sections():
        puts(red(u"[%s]" % section))
        for option in config.items(section):
            puts(red(u"%s=%s" % option))
