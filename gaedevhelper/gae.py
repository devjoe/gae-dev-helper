import sys
import os
import time
import shlex
import urllib
import urllib2
from urllib2 import URLError
import re
from functools import partial
if os.name == 'posix' and sys.version_info[0] < 3:
    import subprocess32 as subprocess
else:
    import subprocess
from multiprocessing import Process


import click
from daemonize import Daemonize
from pygments import highlight
from pygments.lexers import PythonLexer, HttpLexer
from pygments.lexers.special import TextLexer
from pygments.formatters import TerminalFormatter


SH_CHECK_DEV = "ps -eo pid,command | grep 'python dev_appserver.py' | grep -v grep | awk '{print $1}'"
SH_KILL_DEV = SH_CHECK_DEV + " | xargs kill"
SH_KILL_SELF = "ps -eo pid,command | grep 'python ' | grep 'gae.py' | grep -v grep | grep -v stop | grep -v py.test | awk '{print $1}' | xargs kill"

EMPTY_CONFIG = """# ===== GAE dev_appserver.py settings =====
# [Required]
gae_sdk_path = ""


# [Optional]
project_id = ""
project_path = ""
datastore_path = ""
port = ""
remote_api_path = ""


# ===== GAE Helper settings =====
# [Request Filter]
filetype_ignore_filter = []"""

def is_dev_server_running():
    out = subprocess.check_output(SH_CHECK_DEV, shell=True)
    if out:
        return True
    else:
        return False


def delay_to_show_server_status():
    time.sleep(2)
    click.echo("")
    subprocess.call("python gae.py status", shell=True)
    click.echo("\nPress <Enter> to continue ...")


def stop_dev_server():
    try:
        subprocess.check_call(SH_KILL_DEV, shell=True)
        subprocess.call(SH_KILL_SELF, shell=True)
        click.secho("[Done]", fg="green")
    except subprocess.CalledProcessError as e:
        click.secho("[Failed]", fg="red")


def load_config_file(config_path):
    try:
        if not config_path:
            config_path = click.get_app_dir("Gae Helper", force_posix=True)
            sys.path.insert(0, config_path)
            import config as cfg
        else:
            sys.path.insert(0, os.path.dirname(config_path))
            fn = os.path.basename(config_path)
            cfg = __import__(fn[:-3], globals(), locals())
        return cfg
    except ImportError as e:
        click.echo("[Error] Can not import Python config file:\n" + str(e))
        return


def get_request_filetype(line):
    regex = r".*module\.py\:\d+\].*\.(.*) HTTP/1\.1"
    matches = re.findall(regex, line)
    if not matches:
        return ""
    return matches[0]


def is_http_request_log(line):
    regex = r".*module\.py\:\d+\].*?\".*?\" \d+.*"
    matches = re.findall(regex, line)
    return True if matches else False


def is_server_status_log(line):
    regex = r".*(admin_server|dispatcher|api_server)\.py\:\d+\] ((?!HTTP/1\.1).)*$"
    matches = re.findall(regex, line)
    return True if matches else False


def is_user_custom_log(line):
    regex = r".*\.py\:\d+\] ((?!HTTP/1\.1).)*$"
    matches = re.findall(regex, line)
    return True if matches else False


def filter_output(line, cfg):
    if hasattr(cfg, "filetype_ignore_filter") and cfg.filetype_ignore_filter:
        ft = get_request_filetype(line)
        if ft in cfg.filetype_ignore_filter:
            return ""
    return line.strip()


def print_server_status_log(line, cfg):
    h_line = highlight_log(line, TextLexer(), cfg)
    click.secho(h_line, nl=False, fg="green")


def print_http_request_log(line, cfg):
    header, body = line.split("]", 1)
    h_header = highlight_log(header, TextLexer(), cfg).strip() + "] "
    h_body = highlight_log(body, HttpLexer(), cfg)
    click.echo(h_header, nl=False)
    click.echo(h_body, nl=False)


def print_user_custom_log(line, cfg):
    header, body = line.split("]", 1)
    h_header = highlight_log(header, TextLexer(), cfg).strip() + "] "
    h_body = highlight_log(body, TextLexer(), cfg)
    click.echo(h_header, nl=False)
    click.secho(h_body, nl=False, bold=True)


def print_python_code(line, cfg):
    h_string = highlight_log(line, PythonLexer(), cfg)
    click.echo(h_string, nl=False)


def highlight_log(string, lexer, cfg):
    return highlight(string, lexer, TerminalFormatter(bg="dark"))


def run_dev_server(cmd, cfg):
    os.environ['SERVER_SOFTWARE'] = 'Development (devshell remote-api)/1.0'
    os.environ['HTTP_HOST'] = 'localhost'
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, universal_newlines=True)
    while True:
        line = ""
        is_pdb = False
        while True:
            ch = process.stdout.read(1)
            if ch != "\n":
                line += ch
            else:
                break
            if line.startswith('(Pdb) '):
                is_pdb = True
                break

        line = filter_output(line, cfg)
        if line:
            if is_pdb:
                click.echo("(Pdb) ", nl=False)
            elif is_server_status_log(line):
                print_server_status_log(line, cfg)
            elif is_http_request_log(line):
                print_http_request_log(line, cfg)
            elif is_user_custom_log(line):
                print_user_custom_log(line, cfg)
            else:
                print_python_code(line, cfg)
        sys.stdout.flush()
        if line == '' and process.poll() is not None:
            break
    return process.poll()


def construct_run_server_cmd(cfg, dev_appserver_options):
    if hasattr(cfg, "gae_sdk_path") and cfg.gae_sdk_path:
        cmd = "cd " + cfg.gae_sdk_path
    else:
        cmd = "cd /usr/local/google_appengine"
    cmd += " && python dev_appserver.py "
    if hasattr(cfg, "project_path") and cfg.project_path:
        cmd += cfg.project_path
    if hasattr(cfg, "datastore_path") and cfg.datastore_path:
        cmd += " --datastore_path=" + cfg.datastore_path
    cmd += " " + " ".join(dev_appserver_options) + " 2>&1"
    return cmd


def connect_to_dev_server_by_remote_api(cfg, shell):
    if hasattr(cfg, "gae_sdk_path") and cfg.gae_sdk_path:
        sdk_path = cfg.gae_sdk_path
    else:
        sdk_path = "/usr/local/google_appengine"

    # For transaction
    os.environ['SERVER_SOFTWARE'] = 'Development (devshell remote-api)/1.0'
    # For TaskQueue
    os.environ['HTTP_HOST'] = 'localhost'

    sys.path.append(sdk_path)
    import dev_appserver
    dev_appserver.fix_sys_path()

    if hasattr(cfg, "project_path") and cfg.project_path:
        path = os.path.abspath(os.path.expanduser(cfg.project_path))
        sys.path.insert(0, path)
    if hasattr(cfg, "remote_api_path") and cfg.remote_api_path:
        remote_entry = cfg.remote_api_path
    else:
        remote_entry = "/_ah/remote_api"
    if hasattr(cfg, "port") and cfg.port:
        port = cfg.port
    else:
        port = "8080"

    from google.appengine.ext.remote_api import remote_api_stub
    remote_api_stub.ConfigureRemoteApiForOAuth("localhost:" + port, remote_entry, secure=False)

    start_shell(shell, globals(), locals())


def connect_to_pro_server_by_remote_api(cfg, shell):
    if hasattr(cfg, "project_id") and cfg.project_id:
        project_id = cfg.project_id
    else:
        click.echo("[Error] Please set project_id in your config file")
        return
    if hasattr(cfg, "gae_sdk_path") and cfg.gae_sdk_path:
        sdk_path = cfg.gae_sdk_path
    else:
        sdk_path = "/usr/local/google_appengine"

    os.environ['SERVER_SOFTWARE'] = 'Development (devshell remote-api)/1.0'
    os.environ['HTTP_HOST'] = 'localhost'
    os.environ['GAE_SDK_ROOT'] = sdk_path
    python_path = subprocess.check_output("which python", shell=True)
    os.environ['PYTHONPATH'] = os.environ["GAE_SDK_ROOT"] + ':' + python_path

    try:
        import dev_appserver
        dev_appserver.fix_sys_path()
    except ImportError:
        click.echo('Please make sure the App Engine SDK is in your PYTHONPATH.')
        raise

    if hasattr(cfg, "project_path") and cfg.project_path:
        path = os.path.abspath(os.path.expanduser(cfg.project_path))
        sys.path.insert(0, path)
    if hasattr(cfg, "remote_api_path") and cfg.remote_api_path:
        remote_entry = cfg.remote_api_path
    else:
        remote_entry = "/_ah/remote_api"

    from google.appengine.ext.remote_api import remote_api_stub
    remote_api_stub.ConfigureRemoteApiForOAuth( '{}.appspot.com'.format(project_id), remote_entry)

    click.secho("\nYou are connecting to the production server, be careful!\n", bold=True, fg="red")
    start_shell(shell, globals(), locals())


def start_shell(shell, g_vars, l_vars):
    try:
        if shell and shell.lower() == "ptpython":
            from ptpython.repl import embed
            embed(g_vars, l_vars)
        else:
            import IPython
            IPython.embed()
    except ImportError:
        click.secho("\nInstall ipython or ptpython to have better life!\n", bold=True, fg="green")
        import code
        code.interact(local=l_vars)


@click.group()
def gae():
    # before hook
    pass


@gae.command()
@click.confirmation_option(help='Are you sure you want to initialize the config file?')
def init():
    """Do initialization and create an config file"""
    config_path = click.get_app_dir("Gae Helper", force_posix=True)
    try:
        os.mkdir(config_path)
    except OSError as e:
        pass

    config_file = os.path.join(config_path, "config.py")
    with open(config_file, 'w') as f:
        f.write(EMPTY_CONFIG)

    init_file = os.path.join(config_path, "__init__.py")
    with open(init_file, 'a'):
        os.utime(init_file, None)
    click.echo("[Done] Your config file is at {}. Remember to edit it.".format(config_file))


@gae.command()
def status():
    """Show running status"""
    if is_dev_server_running():
        click.secho("Dev server is running", fg="green")
    else:
        click.secho("Dev server is stopped", fg="red")


@gae.command()
def stop():
    """Stop your local dev server"""
    stop_dev_server()


@gae.command()
@click.option('-p', '--page', 'page', default="",
              help='e.g. --page console')
@click.option('-a', '--admin-port', 'admin_port', nargs=1, type=click.STRING, default="8000",
              help='e.g. --admin-port 1234')
def admin(page, admin_port):
    """Launch your GAE admin page in the browser"""
    click.launch('http://localhost:{0}/{1}'.format(admin_port, page))


@gae.command()
@click.option('-c', '--config', 'config_path', nargs=1, type=click.Path(exists=True),
              help='e.g. --config config.py')
@click.argument('dev_appserver_options', nargs=-1)
def run(config_path, dev_appserver_options):
    """Run your GAE local dev server"""
    if is_dev_server_running():
        click.echo("[Error] Your local dev server is already running")
        return

    cfg = load_config_file(config_path)
    if not cfg:
        return

    cmd = construct_run_server_cmd(cfg, dev_appserver_options)
    run_dev_server(cmd, cfg)


@gae.command()
@click.option('-c', '--config', 'config_path', nargs=1, type=click.Path(exists=True),
              help='e.g. --config config.py')
@click.argument('dev_appserver_options', nargs=-1)
def daemon(config_path, dev_appserver_options):
    """Run your GAE local dev server as a daemon"""
    if is_dev_server_running():
        click.echo("[Error] Your local dev server is already running")
        return

    cfg = load_config_file(config_path)
    if not cfg:
        return

    cmd = construct_run_server_cmd(cfg, dev_appserver_options)
    p = Process(target=delay_to_show_server_status, args=())
    p.start()
    daemon = Daemonize(app="gae_dev_helper", pid="/tmp/gae_dev_helper.pid", action=partial(run_dev_server, cmd, cfg))
    daemon.start()


@gae.command()
@click.option('-c', '--config', 'config_path', nargs=1, type=click.Path(exists=True),
              help='e.g. --config config.py')
@click.option('-d', '--dev', 'dev', is_flag=True,
              help='e.g. --dev')
@click.option('-p', '--pro', 'pro', is_flag=True,
              help='e.g. --pro')
@click.option('-s', '--shell', 'shell', nargs=1, type=click.STRING, default="ipython",
              help='e.g. --shell ptpython \n# default: ipython')
def remote_api(config_path, dev, pro, shell):
    """Connect to your GAE dev/pro server"""
    cfg = load_config_file(config_path)
    if not cfg:
        return

    if dev:
        if not is_dev_server_running():
            click.echo("[Error] Your local dev server is not running")
            return
        connect_to_dev_server_by_remote_api(cfg, shell)
    elif pro:
        connect_to_pro_server_by_remote_api(cfg, shell)
    else:
        click.echo("[Error] Use --dev or --pro to specify the server you want to connect")


@gae.command()
@click.option('-c', '--code', 'code', nargs=1, type=click.STRING,
              help='e.g. --code print("Hello World")')
@click.option('-f', '--file', 'f', nargs=1, type=click.File('rb'),
              help='e.g. --file sample.py')
@click.option('-s', '--stream', 'stream', is_flag=True,
              help='e.g. cat sample.py | python gae.py interactive --stream')
@click.option('-a', '--admin-port', 'admin_port', nargs=1, type=click.STRING, default="8000",
              help='e.g. --admin-port 1234')
def interactive(code, f, stream, admin_port):
    """Run your code in interactive console"""
    if not code and not f and not stream:
        click.echo("[Error] Use --code or --file or --stream\n")
        return
    url = "http://localhost:{}/console".format(admin_port)
    try:
        response = urllib2.urlopen(url)
    except URLError as e:
        click.echo("[Error] Can not connect to url:\n" + str(e))
        return

    regex = r"'xsrf_token': '(\w*)'"
    matches = re.findall(regex, response.read())
    if not matches:
        click.echo("[Error] Can not find XSRF Token to run your interactive command")
        return

    rpc_code = ""
    if f:
        rpc_code = f.read()
    if code:
        rpc_code += "\n" + code
    if stream:
        rpc_code += "\n" + click.get_text_stream('stdin').read()

    query_args = {'module_name': 'default',
                  'code'       : rpc_code,
                  'xsrf_token' : matches[0]}
    data = urllib.urlencode(query_args)
    request = urllib2.Request(url, data)
    response = urllib2.urlopen(request)
    html = response.read()

    click.echo(html)



if __name__ == '__main__':
    gae()
