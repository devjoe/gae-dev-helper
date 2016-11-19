import sys
import os
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

import click
from daemonize import Daemonize



def is_dev_server_running():
    out = subprocess.check_output("ps -eo pid,command | grep 'python dev_appserver.py' | grep -v grep | grep -v '/bin/sh -c cd' | awk '{print $1}'", shell=True)
    if out:
        click.echo("[Error] Your local dev server is already running")
        return True
    else:
        return False


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


def run_dev_server(cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            click.echo(output.strip())
            sys.stdout.flush()
    return process.poll()


def construct_run_server_cmd(cfg, dev_appserver_options):
    if hasattr(cfg, "gae_sdk_path") and cfg.gae_sdk_path:
        cmd = "cd " + cfg.gae_sdk_path + " && python dev_appserver.py "
    else:
        cmd = "cd /usr/local/google_appengine && python dev_appserver.py "
    if hasattr(cfg, "project_path") and cfg.project_path:
        cmd += cfg.project_path
    if hasattr(cfg, "datastore_path") and cfg.datastore_path:
        cmd += " --datastore_path=" + cfg.datastore_path
    cmd += " " + " ".join(dev_appserver_options)
    return cmd


@click.group()
def gae():
    # before hook
    pass


@gae.command()
def status():
    """Check whether your local dev server is running or not"""
    if is_dev_server_running():
        click.secho("Dev Server is running", fg="green")
    else:
        click.secho("Dev Server is stopped", fg="red")


@gae.command()
@click.option('-p', '--page', 'page', default="",
              help='e.g. --page console')
def admin(page):
    """Launch your GAE admin page in the default browser"""
    click.launch('http://localhost:8000/' + page)


@gae.command()
@click.option('-c', '--config', 'config_path', nargs=1, type=click.Path(exists=True),
              help='e.g. --config config.py')
@click.argument('dev_appserver_options', nargs=-1)
def daemon(config_path, dev_appserver_options):
    """Start your GAE local dev server as a daemon"""
    if is_dev_server_running():
        return

    cfg = load_config_file(config_path)
    if not cfg:
        return

    cmd = construct_run_server_cmd(cfg, dev_appserver_options)

    daemon = Daemonize(app="gae_helper", pid="/tmp/gae_helper.pid", action=partial(run_dev_server, cmd))
    daemon.start()


@gae.command()
@click.option('-c', '--code', 'code', nargs=1, type=click.STRING,
              help='e.g. --code print("Hello World")')
@click.option('-f', '--file', 'f', nargs=1, type=click.File('rb'),
              help='e.g. --file sample.py')
@click.option('-s', '--stream', is_flag=True,
              help='e.g. cat sample.py | python gae.py interactive --stream')
def interactive(code, f, stream):
    """Run your code in dev server's interactive console"""
    if not code and not f and not stream:
        click.echo("[Error] Use --code or --file or --stream\n")
        return
    url = "http://localhost:8000/console"
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
