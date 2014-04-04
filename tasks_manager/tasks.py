#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ConfigParser import ConfigParser
from datetime import datetime
from random import randint

from os.path import abspath, dirname, join

from fabric.api import abort, cd, env, hide, puts, task
from fabric.contrib import console
from fabric.operations import settings, sudo, put


from .colors import blue, bold, green, red
from .utils import (
    _check_ssh_key,
    _collect_static,
    _create_django_user,
    _create_postgre_database,
    _create_postgre_user,
    _create_virtualenv,
    _deploy_django_project,
    _directories_exist,
    _git_clone,
    _install_dependencies,
    _install_gunicorn,
    _install_requirements,
    _install_virtualenv,
    _prepare_media_path,
    _print_configs,
    _reload_nginx,
    _reload_supervisorctl,
    _remote_open,
    _remove_project_files,
    _set_config_file,
    _set_manual_config_file,
    _setup_directories,
    _setup_django_project,
    _supervisor_restart,
    _upload_nginx_conf,
    _upload_rungunicorn_script,
    _upload_supervisord_conf,
    _verify_sudo,
    _virtenvrun,
)


base_path = dirname(abspath(__file__))


OPT_DJANGO_CONF_APPS = '/opt/django/configs/apps/%(project)s.conf'


@task
def setup(dependencies="yes"):
    '''
    SETUP
    fab preject_name setup:dependencies=False
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

    _setup_django_project()
    _collect_static()

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

    _deploy_django_project()
    _collect_static()

    _prepare_media_path()  # fica porque pode ser alterado em uma review de código
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
    sudo('service nginx restart')


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


@task
def print_configs():
    OPT_DJANGO_CONF_APP = OPT_DJANGO_CONF_APPS % env
    fd = _remote_open(OPT_DJANGO_CONF_APP)

    config = ConfigParser()
    config.readfp(fd)

    _print_configs(config)


@task
def manage(*args):
    with cd(env.django_project_root):
        params = {'args': " ".join(args)}
        params.update(env)
        _virtenvrun('python manage.py %(args)s --settings=%(django_project_settings)s' % params)


@task
def upload(*args):
    if len(args) < 2:
        path_local = console.prompt(u'Entre com o path local: ')
        path_remote = console.prompt(u'Entre com o path remoto: ')
    else:
        path_local = args[0]
        path_remote = args[1]

    if len(args) > 2:
        mode = int(args[2])
    else:
        puts(blue(u'Entre com um inteiro para o modo ex.:0755'))
        path_remote = console.prompt(u'>> ', default=None)

    with cd('/tmp'):
        put(path_local, path_remote, mode=mode)


@task
def restart():
    _supervisor_restart()


@task
def set_manual_config_file():
    _set_manual_config_file()


@task
def create_postgre_database():
    _create_postgre_database()


@task
def create_postgre_user():
    _create_postgre_user()


@task
def check_port():
    '''
        Task que sugere uma porta para ser utilizada na aplicação
    '''
    chosen_port = randint(8000, 9001)
    output = sudo("netstat -tlnp | grep 127.0.0.1 | awk '{print $4}' | cut -d : -f 2 | sort -k1 -n")
    ports = []

    for port in output.split(r'\n'):
        try:
            ports.append(int(port))
        except:
            pass

    # variável que controla
    # se o usuário já escolheu uma porta sugerida
    chose = False
    while not chose:
        # variável que controla se
        # a porta sorteada está livre
        open_port = chosen_port in ports
        # laço que sorteia uma nova
        # porta caso a sorteada não estiver livre
        while not open_port:
            chosen_port = randint(8000, 9001)
            open_port = not chosen_port in ports
        # confirma se o usuário quer
        # sortear outra porta
        chose = not console.confirm(
            green(
                "porta livre: %s%s" % (bold(chosen_port), green('; sortear outra porta'))),
            default=True
        )
    # imprime a porta escolhida
    puts(green("porta escolhida %s" % bold(chosen_port)))
