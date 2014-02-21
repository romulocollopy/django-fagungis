#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string
import random
import ConfigParser
import logging
import sys  # mostrar mesgs de erro
from StringIO import StringIO

from copy import copy
from datetime import datetime
from os.path import basename, abspath, dirname, isfile, join, expanduser

from fabric.api import get
from fabric.api import env, puts, abort, cd, hide, task
from fabric.operations import sudo, settings, run
from fabric.contrib import console, files
from fabric.contrib.files import upload_template, append, exists
from fabric.colors import green, red, white

base_path = dirname(abspath(__file__))


def _wrap_with(code):
    def inner(text, bold=False, bg=49):  # keep bg default if none
        c = code
        if bold:
            c = "1;%s" % (c)
        c = "%s;%s" % (c, bg)
        return "\033[%sm%s\033[0m" % (c, text)
    return inner

red = _wrap_with('31')
green = _wrap_with('32')
yellow = _wrap_with('33')
blue = _wrap_with('34')
magenta = _wrap_with('35')
cyan = _wrap_with('36')
white = _wrap_with('37')


@task
def setup(dependencies="yes"):
    '''
    SETUP
    fab ehall setup:dependencies=False
    '''
    puts(red(' -------- I N I C I A N D O    S E T U P  ...', bg=104))

    #  test configuration start
    if not test_configuration():
        if not console.confirm("Configuration test %s! Do you want to continue?" % red('failed'), default=False):
            abort("Aborting at user request.")
            #  test configuration end

    # inicio SETUP
    puts(green('Iniciando setup...', bg='107'))
    if env.ask_confirmation:
        if not console.confirm("Are you sure you want to setup %s?" % red(env.project.upper()), default=False):
            abort("Aborting at user request.")

    #Inicia Cronometro
    start_time = datetime.now()
    _verify_sudo()

    # Se a home do user 'django' existe, entende-se que:
    # pacotes do sistema estão indtalados
    # user django  criado
    # todos os diretórios de projeto estão criados
    if not _directories_exist():  # verifica se existe ht_docs
        if dependencies == "yes":
            puts(red('== Instalando pacotes do sistema ...'))
            _install_dependencies()  # nao instala pips soh packs + env.additional_packages
        else:
            puts(red('Pacotes do sistema não serão instalados.'))

        _create_django_user()
        _setup_directories()
    _check_ssh_key()  # verifica / cria chave pública : cadu 10140210

    _git_clone()
    _set_config_file()
    _install_virtualenv()
    _create_virtualenv()
    _install_requirements()
    _install_gunicorn()
    _upload_rungunicorn_script()
    #console.confirm('===========')
    _upload_supervisord_conf()
    #q!console.confirm('===========')
    _upload_nginx_conf()
    _reload_supervisorctl()
    

    end_time = datetime.now()
    finish_message = '[%s] Correctly finished in %i seconds' % \
                     (green(end_time.strftime('%H:%M:%S')), (end_time - start_time).seconds)
    puts(finish_message)


@task
def deploy(new_apps=True, new_app_conf=True):
    #  test configuration start
    puts(green('Iniciando DEPLOY...', bg=107))
    if not test_configuration():
        if not console.confirm("Configuration test %s! Do you want to continue?" % red('failed'), default=False):
            abort("Aborting at user request.")
            #  test configuration end
    _verify_sudo()
    if env.ask_confirmation:
        if not console.confirm("Are you sure you want to deploy in %s?" % red(env.project.upper()), default=False):
            abort("Aborting at user request.")
    puts(green('Start deploy...'))
    start_time = datetime.now()

    if env.repository_type == 'hg':
        hg_pull()
    else:
        git_pull()
    if new_apps:
        _install_requirements()
    if new_app_conf:
        _upload_nginx_conf()
        _upload_rungunicorn_script()
        _upload_supervisord_conf()
    _prepare_django_project()
    _prepare_media_path() # fica porque pode ser alterado em uma review de código
    _supervisor_restart()

    end_time = datetime.now()
    finish_message = '[%s] Correctly deployed in %i seconds' % \
                     (green(end_time.strftime('%H:%M:%S')), (end_time - start_time).seconds)
    puts(finish_message)


@task
def remove():
    #  test configuration start
    if not test_configuration():
        if not console.confirm("Configuration test %s! Do you want to continue?" % red('failed'), default=False):
            abort("Aborting at user request.")
            #  test configuration end
    if env.ask_confirmation:
        if not console.confirm("Are you sure you want to remove %s?" % red(env.project.upper()), default=False):
            abort("Aborting at user request.")
    puts(green('Start remove...'))
    start_time = datetime.now()

    _remove_project_files()
    _reload_supervisorctl()
    _reload_nginx()

    end_time = datetime.now()
    finish_message = '[%s] Correctly finished in %i seconds' % \
                     (green(end_time.strftime('%H:%M:%S')), (end_time - start_time).seconds)
    puts(finish_message)


@task
def hg_pull():
    with cd(env.code_root):
        sudo('hg pull -u')


@task
def git_pull():
    puts(blue('== Git Pull  - Baixando aplicação ...', 1, bg=107))
    with cd(env.code_root):
        with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
            res = sudo('git checkout -b %(branch)s' % env, user=env.django_user)
        if 'failed' in res:
            sudo('git checkout %(branch)s' % env, user=env.django_user)
        sudo('git pull origin %(branch)s' % env, user=env.django_user)


@task
def reset_nginx():
    _upload_nginx_conf()
    sudo('sudo service nginx restart')


@task
def test_configuration(verbose=True):
    errors = []
    parameters_info = []
    if 'project' not in env or not env.project:
        errors.append('Project name missing')
    elif verbose:
        parameters_info.append(('Project name', env.project))
    if 'repository' not in env or not env.repository:
        errors.append('Repository url missing')
    elif verbose:
        parameters_info.append(('Repository url', env.repository))
    if 'branch' in env:
        parameters_info.append(('Project Branch', env.branch))
    if 'hosts' not in env or not env.hosts:
        errors.append('Hosts configuration missing')
    elif verbose:
        parameters_info.append(('Hosts', env.hosts))
    if 'django_user' not in env or not env.django_user:
        errors.append('Django user missing')
    elif verbose:
        parameters_info.append(('Django user', env.django_user))
    if 'django_user_group' not in env or not env.django_user_group:
        errors.append('Django user group missing')
    elif verbose:
        parameters_info.append(('Django user group', env.django_user_group))
    if 'django_user_home' not in env or not env.django_user_home:
        errors.append('Django user home dir missing')
    elif verbose:
        parameters_info.append(('Django user home dir', env.django_user_home))
    if 'projects_path' not in env or not env.projects_path:
        errors.append('Projects path configuration missing')
    elif verbose:
        parameters_info.append(('Projects path', env.projects_path))
    if 'code_root' not in env or not env.code_root:
        errors.append('Code root configuration missing')
    elif verbose:
        parameters_info.append(('Code root', env.code_root))
    if 'django_project_root' not in env or not env.django_project_root:
        errors.append('Django project root configuration missing')
    elif verbose:
        parameters_info.append(('Django project root', env.django_project_root))
    if 'django_project_settings' not in env or not env.django_project_settings:
        env.django_project_settings = 'settings'
    if verbose:
        parameters_info.append(('django_project_settings', env.django_project_settings))
    if 'django_media_path' not in env or not env.django_media_path:
        errors.append('Django media path configuration missing')
    elif verbose:
        parameters_info.append(('Django media path', env.django_media_path))
    if 'django_static_path' not in env or not env.django_static_path:
        errors.append('Django static path configuration missing')
    elif verbose:
        parameters_info.append(('Django static path', env.django_static_path))
    if 'south_used' not in env:
        errors.append('"south_used" configuration missing')
    elif verbose:
        parameters_info.append(('south_used', env.south_used))
    if 'virtenv' not in env or not env.virtenv:
        errors.append('virtenv configuration missing')
    elif verbose:
        parameters_info.append(('virtenv', env.virtenv))
    if 'virtenv_options' not in env or not env.virtenv_options:
        errors.append('"virtenv_options" configuration missing, you must have at least one option')
    elif verbose:
        parameters_info.append(('virtenv_options', env.virtenv_options))
    if 'requirements_file' not in env or not env.requirements_file:
        env.requirements_file = join(env.code_root, 'requirements.txt')
    if verbose:
        parameters_info.append(('requirements_file', env.requirements_file))
    if 'ask_confirmation' not in env:
        errors.append('"ask_confirmation" configuration missing')
    elif verbose:
        parameters_info.append(('ask_confirmation', env.ask_confirmation))
    if 'gunicorn_bind' not in env or not env.gunicorn_bind:
        errors.append('"gunicorn_bind" configuration missing')
    elif verbose:
        parameters_info.append(('gunicorn_bind', env.gunicorn_bind))
    # if 'gunicorn_logfile' not in env or not env.gunicorn_logfile:
    #     errors.append('"gunicorn_logfile" configuration missing')
    # elif verbose:
    #     parameters_info.append(('gunicorn_logfile', env.gunicorn_logfile))
    if 'rungunicorn_script' not in env or not env.rungunicorn_script:
        errors.append('"rungunicorn_script" configuration missing')
    elif verbose:
        parameters_info.append(('rungunicorn_script', env.rungunicorn_script))
    if 'gunicorn_workers' not in env or not env.gunicorn_workers:
        errors.append('"gunicorn_workers" configuration missing, you must have at least one worker')
    elif verbose:
        parameters_info.append(('gunicorn_workers', env.gunicorn_workers))
    if 'gunicorn_worker_class' not in env or not env.gunicorn_worker_class:
        errors.append('"gunicorn_worker_class" configuration missing')
    elif verbose:
        parameters_info.append(('gunicorn_worker_class', env.gunicorn_worker_class))
    if 'gunicorn_loglevel' not in env or not env.gunicorn_loglevel:
        errors.append('"gunicorn_loglevel" configuration missing')
    elif verbose:
        parameters_info.append(('gunicorn_loglevel', env.gunicorn_loglevel))
    if 'nginx_server_name' not in env or not env.nginx_server_name:
        errors.append('"nginx_server_name" configuration missing')
    elif verbose:
        parameters_info.append(('nginx_server_name', env.nginx_server_name))
    if 'nginx_conf_file' not in env or not env.nginx_conf_file:
        errors.append('"nginx_conf_file" configuration missing')
    elif verbose:
        parameters_info.append(('nginx_conf_file', env.nginx_conf_file))
    if 'nginx_client_max_body_size' not in env or not env.nginx_client_max_body_size:
        env.nginx_client_max_body_size = 10
    elif not isinstance(env.nginx_client_max_body_size, int):
        errors.append('"nginx_client_max_body_size" must be an integer value')
    if verbose:
        parameters_info.append(('nginx_client_max_body_size', env.nginx_client_max_body_size))
    if 'nginx_htdocs' not in env or not env.nginx_htdocs:
        errors.append('"nginx_htdocs" configuration missing')
    elif verbose:
        parameters_info.append(('nginx_htdocs', env.nginx_htdocs))

    if 'nginx_https' not in env:
        env.nginx_https = False
    elif not isinstance(env.nginx_https, bool):
        errors.append('"nginx_https" must be a boolean value')
    elif verbose:
        parameters_info.append(('nginx_https', env.nginx_https))

    if 'supervisor_program_name' not in env or not env.supervisor_program_name:
        env.supervisor_program_name = env.project
    if verbose:
        parameters_info.append(('supervisor_program_name', env.supervisor_program_name))
    if 'supervisorctl' not in env or not env.supervisorctl:
        errors.append('"supervisorctl" configuration missing')
    elif verbose:
        parameters_info.append(('supervisorctl', env.supervisorctl))
    if 'supervisor_autostart' not in env or not env.supervisor_autostart:
        errors.append('"supervisor_autostart" configuration missing')
    elif verbose:
        parameters_info.append(('supervisor_autostart', env.supervisor_autostart))
    if 'supervisor_autorestart' not in env or not env.supervisor_autorestart:
        errors.append('"supervisor_autorestart" configuration missing')
    elif verbose:
        parameters_info.append(('supervisor_autorestart', env.supervisor_autorestart))
    if 'supervisor_redirect_stderr' not in env or not env.supervisor_redirect_stderr:
        errors.append('"supervisor_redirect_stderr" configuration missing')
    elif verbose:
        parameters_info.append(('supervisor_redirect_stderr', env.supervisor_redirect_stderr))
    # if 'supervisor_stdout_logfile' not in env or not env.supervisor_stdout_logfile:
    #     errors.append('"supervisor_stdout_logfile" configuration missing')
    # elif verbose:
    #     parameters_info.append(('supervisor_stdout_logfile', env.supervisor_stdout_logfile))
    if 'supervisord_conf_file' not in env or not env.supervisord_conf_file:
        errors.append('"supervisord_conf_file" configuration missing')
    elif verbose:
        parameters_info.append(('supervisord_conf_file', env.supervisord_conf_file))

    if errors:
        if len(errors) == 29:
            ''' all configuration missing '''
            puts('Configuration missing! Please read README.rst first or go ahead at your own risk.')
        else:
            puts('Configuration test revealed %i errors:' % len(errors))
            puts('%s\n\n* %s\n' % ('-' * 37, '\n* '.join(errors)))
            puts('-' * 40)
            puts('Please fix them or go ahead at your own risk.')
        return False
    elif verbose:
        for parameter in parameters_info:
            parameter_formatting = "'%s'" if isinstance(parameter[1], str) else "%s"
            parameter_value = parameter_formatting % parameter[1]
            puts('%s %s' % (parameter[0].ljust(27), green(parameter_value)))
    puts('Configuration tests passed!')
    return True


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
        virtenvsudo('pip install -r %s' % env.requirements_file)


def _install_gunicorn():
    """ force gunicorn installation into your virtualenv, even if it's installed globally.
    for more details: https://github.com/benoitc/gunicorn/pull/280 """
    puts(blue("== instalando green unicorn ..."))
    virtenvsudo('pip install -I gunicorn')


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


def virtenvrun(command):
    activate = 'source %s/bin/activate' % env.virtenv
    run(activate + ' && ' + command, )


def virtenvsudo(command):
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
        virtenvrun('python manage.py syncdb --noinput --verbosity=1 --settings=%(django_project_settings)s'%env)
        if env.south_used:
            virtenvrun('python manage.py migrate --noinput --verbosity=1 --settings=%(django_project_settings)s'%env)
        virtenvsudo('python manage.py collectstatic --noinput --settings=%(django_project_settings)s'%env)


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
    config = ConfigParser.ConfigParser()
    config_file = None
    try:
        config_file = open('/opt/django/configs/apps/ehall.conf')
    except IOError as e:
        print "I/O error({0}): {1} - Possível arquivo inexistente.".format(e.errno, e.strerror)
        config_file = None
    except:
        print "Erro não esperado:", sys.exc_info()[0]
        raise

    if config_file is not None:
        config.readfp(config_file)
    else:
        config = None

    return config


def _generate_secret_key():
    secret_key = ''.join([random.SystemRandom().choice(string.printable[:-15]) for i in range(100)]).replace(' ', '')
    return secret_key


def _set_config_file():
    '''
    faz upload do arquivo de config
    baseado no template "config_template.conf"
    e seta a secret_key
    '''
    # garante que a secret_key e uma app já existenete não seja trocada -> destroi users no banco
    if files.exists("/opt/django/configs/apps/ehall.conf", use_sudo=True, verbose=False):
        config = _red_config_file()
        env.secret_key = config('APP', 'secret_key')
    else:
        env.secret_key = _generate_secret_key()

    context = {
        'secret_key': env.secret_key,
        'default_from_email': '',
        'email_host': '',
        'email_host_password': '',
        'email_host_user': '',
        'email_port': '',
        'email_use_tls': '',
        'email_use_ssl': '',
    }
    template = '%s/conf/config_template.conf' % base_path
    destination_path = '%(django_user_home)s/configs/apps/%(project)s.conf' % env

    upload_template(
        template,
        destination_path,
        context=context,
        use_sudo=True,
        backup=True,
        mirror_local_mode=False,
    )

    sudo('chmod ug+rw  %s' % destination_path)


@task
def print_configs():
    import ConfigParser
    fd = StringIO()
    try:
        # trocar por vars
        get('/opt/django/configs/apps/ehall.conf', fd)  # fd)

    except:
        puts(red('Arquivo de configuração não emcontrado em %s' % ('/opt/django/configs/apps/ehall.conf'), bg=104))  # trocar por vars
        print "Unexpected error:", sys.exc_info()[0]

    #s = fd.getvalue()  # por que não consegui passar direto o fd pro copnfig parser.
    config = ConfigParser.ConfigParser()
    print ">>>",fd.getvalue()
    config.readfp(fd)
    print config.sections()

