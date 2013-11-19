#!/usr/bin/env python
# -*- coding: utf-8 -*-

from copy import copy
from datetime import datetime
from os.path import basename, abspath, dirname, isfile, join, expanduser
from fabric.api import env, puts, abort, cd, hide, task
from fabric.operations import sudo, settings, run
from fabric.contrib import console
from fabric.contrib.files import upload_template, append, exists

from fabric.colors import _wrap_with, green

green_bg = _wrap_with('42')
red_bg = _wrap_with('41')
fagungis_path = dirname(abspath(__file__))


@task
def setup(new_server=True):
    '''
    SETUP
    '''
    #  test configuration start
    if not test_configuration():
        if not console.confirm("Configuration test %s! Do you want to continue?" % red_bg('failed'), default=False):
            abort("Aborting at user request.")
            #  test configuration end
    if env.ask_confirmation:
        if not console.confirm("Are you sure you want to setup %s?" % red_bg(env.project.upper()), default=False):
            abort("Aborting at user request.")
    puts(green_bg('Start setup...'))
    start_time = datetime.now()

    if not _directories_exist():
        _push_key()
        _verify_sudo()
        if new_server:
            puts(green_bg('Dependecies'))
            _install_dependencies()  # nao instala so packs

            _create_django_user()
            puts(green_bg('Django user created'))
            _setup_directories()

    _setup_project_directories()
    if env.repository_type == 'hg':
        _hg_clone()
    else:
        _git_clone()
    _install_virtualenv()
    _create_virtualenv()
    _install_gunicorn()
    _install_requirements()
    _upload_rungunicorn_script()
    _upload_supervisord_conf()
    _upload_nginx_conf()

    end_time = datetime.now()
    finish_message = '[%s] Correctly finished in %i seconds' % \
                     (green_bg(end_time.strftime('%H:%M:%S')), (end_time - start_time).seconds)
    puts(finish_message)


@task
def deploy(new_apps=True, new_server_conf=True):
    #  test configuration start
    if not test_configuration():
        if not console.confirm("Configuration test %s! Do you want to continue?" % red_bg('failed'), default=False):
            abort("Aborting at user request.")
            #  test configuration end
    _verify_sudo()
    if env.ask_confirmation:
        if not console.confirm("Are you sure you want to deploy in %s?" % red_bg(env.project.upper()), default=False):
            abort("Aborting at user request.")
    puts(green_bg('Start deploy...'))
    start_time = datetime.now()

    if env.repository_type == 'hg':
        hg_pull()
    else:
        git_pull()
    if new_apps:
        _install_requirements()
    if new_server_conf:
        _upload_nginx_conf()
        _upload_rungunicorn_script()
        _upload_supervisord_conf()
    _prepare_django_project()
    _prepare_media_path() # fica porque pode ser alterado em uma review de código
    _supervisor_restart()

    end_time = datetime.now()
    finish_message = '[%s] Correctly deployed in %i seconds' % \
                     (green_bg(end_time.strftime('%H:%M:%S')), (end_time - start_time).seconds)
    puts(finish_message)


@task
def remove():
    #  test configuration start
    if not test_configuration():
        if not console.confirm("Configuration test %s! Do you want to continue?" % red_bg('failed'), default=False):
            abort("Aborting at user request.")
            #  test configuration end
    if env.ask_confirmation:
        if not console.confirm("Are you sure you want to remove %s?" % red_bg(env.project.upper()), default=False):
            abort("Aborting at user request.")
    puts(green_bg('Start remove...'))
    start_time = datetime.now()

    _remove_project_files()
    _reload_supervisorctl()
    _reload_nginx()

    end_time = datetime.now()
    finish_message = '[%s] Correctly finished in %i seconds' % \
                     (green_bg(end_time.strftime('%H:%M:%S')), (end_time - start_time).seconds)
    puts(finish_message)


@task
def hg_pull():
    with cd(env.code_root):
        sudo('hg pull -u')


@task
def git_pull():
    with cd(env.code_root):
        branch = env.get('branch', 'master')
        with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
            res = sudo('git checkout -b %(branch)s' % {'branch': branch}, user=env.django_user)
        if 'failed' in res:
            sudo('git checkout %(branch)s' % {'branch': branch}, user=env.django_user)
        sudo('git pull origin %(branch)s'% {'branch': branch}, user=env.django_user)


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
    if 'gunicorn_logfile' not in env or not env.gunicorn_logfile:
        errors.append('"gunicorn_logfile" configuration missing')
    elif verbose:
        parameters_info.append(('gunicorn_logfile', env.gunicorn_logfile))
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
    if 'supervisor_stdout_logfile' not in env or not env.supervisor_stdout_logfile:
        errors.append('"supervisor_stdout_logfile" configuration missing')
    elif verbose:
        parameters_info.append(('supervisor_stdout_logfile', env.supervisor_stdout_logfile))
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


########################
## END Fagungis tasks ##
########################


def _create_django_user():
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = sudo('useradd -d %(django_user_home)s -m -r %(django_user)s -s /bin/bash' % env)
    if 'already exists' in res:
        puts('User \'%(django_user)s\' already exists, will not be changed.' % env)
        return
        #  set password
    sudo('passwd %(django_user)s' % env)


def _verify_sudo():
    ''' we just check if the user is sudoers '''
    sudo('cd .')


def _install_nginx():
    # add nginx stable ppa
    sudo("add-apt-repository -y ppa:nginx/stable")
    sudo("apt-get update")
    sudo("apt-get -y install nginx")
    sudo("/etc/init.d/nginx start")


def _install_dependencies():
    ''' Ensure those Debian/Ubuntu packages are installed '''
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
    ''' you must have a file called requirements.txt in your project root'''
    if 'requirements_file' in env and env.requirements_file:
        virtenvsudo('pip install -r %s' % env.requirements_file)


def _install_gunicorn():
    """ force gunicorn installation into your virtualenv, even if it's installed globally.
    for more details: https://github.com/benoitc/gunicorn/pull/280 """
    virtenvsudo('pip install -I gunicorn')


def _install_virtualenv():
    sudo('pip install virtualenv')


def _create_virtualenv():
    sudo('virtualenv --%s %s' % (' --'.join(env.virtenv_options), env.virtenv))


def _setup_directories():
    sudo('mkdir -p %(projects_path)s' % env)
    sudo('chown -R %(django_user_home)s ' % env)
    #sudo('mkdir -p %(django_user_home)s/logs/nginx' % env)  # Not used
    # prepare gunicorn_logfile directory
    sudo('mkdir -p %s' % dirname(env.gunicorn_logfile))
    sudo('chown %s %s' % (env.django_user, dirname(env.gunicorn_logfile)))
    sudo('chmod -R 775 %s' % dirname(env.gunicorn_logfile))
    # prepare supervisor_stdout_logfile directory
    sudo('mkdir -p %s' % dirname(env.supervisor_stdout_logfile))
    sudo('chown %s %s' % (env.django_user, dirname(env.supervisor_stdout_logfile)))
    sudo('chmod -R 775 %s' % dirname(env.supervisor_stdout_logfile))
    sudo('mkdir -p %s' % dirname(env.nginx_conf_file))
    sudo('mkdir -p %s' % dirname(env.supervisord_conf_file))
    sudo('mkdir -p %s' % dirname(env.rungunicorn_script))
    sudo('mkdir -p %(django_user_home)s/tmp' % env)
    sudo('mkdir -p %(nginx_htdocs)s' % env)
    sudo('echo "<html><body>nothing here</body></html> " > %(nginx_htdocs)s/index.html' % env)


def _directories_exist():
    return exists(dirname(env.nginx_htdocs), use_sudo=True)


def _setup_project_directories():
    sudo('mkdir -p %(virtenv)s' % env)
    # prepare gunicorn_logfile
    sudo('touch %s' % env.gunicorn_logfile)
    sudo('chown %s %s' % (env.django_user, env.gunicorn_logfile))
    # prepare supervisor_stdout_logfile
    sudo('touch %s' % env.supervisor_stdout_logfile)
    sudo('chown %s %s' % (env.django_user, env.supervisor_stdout_logfile))


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


def _hg_clone():
    sudo('hg clone %s %s' % (env.repository, env.code_root))


def _git_clone():
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        with cd(env.code_root):
            res = sudo('git pull' % env, user=env.django_user)
    if 'failed' in res:
        sudo('git clone %(repository)s %(code_root)s' % env, user=env.django_user)


def _test_nginx_conf():
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = sudo('nginx -t -c /etc/nginx/nginx.conf')
    if 'test failed' in res:
        abort(red_bg('NGINX configuration test failed! Please review your parameters.'))


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
        template = '%s/conf/%s' % (fagungis_path, local_nginx_conf_file)
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
    #sudo('%(supervisorctl)s reload' % env) # desnecessario reload, e leva mais tempo


def _upload_supervisord_conf():
    ''' upload supervisor conf '''
    if isfile('conf/supervisord.conf'):
        ''' we use user defined supervisord.conf template '''
        template = 'conf/supervisord.conf'
    else:
        template = '%s/conf/supervisord.conf' % fagungis_path
    upload_template(template, env.supervisord_conf_file,
                    context=env, backup=False, use_sudo=True)
    sudo('ln -sf %s /etc/supervisor/conf.d/%s' % (env.supervisord_conf_file, basename(env.supervisord_conf_file)))
    _reload_supervisorctl()


def _prepare_django_project():
    with cd(env.django_project_root):
        virtenvrun('python manage.py syncdb --noinput --verbosity=1')
        if env.south_used:
            virtenvrun('python manage.py migrate --noinput --verbosity=1')
        virtenvsudo('python manage.py collectstatic --noinput')


def _prepare_media_path():
    path = env.django_media_path.rstrip('/')
    sudo('mkdir -p %s' % path)
    sudo('chmod -R 775 %s' % path)


def _upload_rungunicorn_script():
    ''' upload rungunicorn conf '''
    if isfile('scripts/rungunicorn.sh'):
        ''' we use user defined rungunicorn file '''
        template = 'scripts/rungunicorn.sh'
    else:
        template = '%s/scripts/rungunicorn.sh' % fagungis_path
    upload_template(template, env.rungunicorn_script,
                    context=env, backup=False, use_sudo=True)
    sudo('chmod +x %s' % env.rungunicorn_script)


def _supervisor_restart():
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        res = sudo('%(supervisorctl)s restart %(supervisor_program_name)s' % env)
    if 'ERROR' in res:
        print red_bg("%s NOT STARTED!" % env.supervisor_program_name)
    else:
        print green_bg("%s correctly started!" % env.supervisor_program_name)


def _read_key_file(key_file):
    key_file = expanduser(key_file)
    if not key_file.endswith('pub'):
        raise RuntimeWarning('Trying to push non-public part of key pair')
    with open(key_file) as f:
        return f.read()


def _push_key(key_file='~/.ssh/id_rsa.pub'):
    key_text = _read_key_file(key_file)
    append('~/.ssh/authorized_keys', key_text)
