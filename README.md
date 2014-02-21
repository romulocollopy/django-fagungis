## Uso 


### configure o arquivo settings.ini no mesmo path que o arquivo fabfile.py



    
    [DEPLOY]
    project_name=NOME_APP
    repositorio = git@bitbucket.org:znc/e-hall.git
    repository_type = git
    deploy_hosts = ubuntu@107.22.193.179:29992
    arquivo_config = /opt/django/configs/apps/NOME_APP.conf
    
    gunicorn_bind = "127.0.0.1:8032"  # ip e porta 
    
    [APP]
    settings_file = NOME_APP.settings.prod
    debug=False
    
    [EMAIL]
    default_from_email =
    email_host =
    email_host_password =
    email_host_user =
    email_port =
    email_use_tls =
    email_use_ssl =
    
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







