from __future__ import print_function
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
from subprocess import CalledProcessError
from multiprocessing import Process


import click
from daemonize import Daemonize
from pygments import highlight
from pygments.lexers import BashLexer, PythonLexer
from pygments.formatters import Terminal256Formatter, TerminalFormatter


CHECK_SCRIPT = "ps -eo pid,command | grep 'python dev_appserver.py' | grep -v grep | grep -v '/bin/sh -c cd' | awk '{print $1}'"
KILL_SCRIPT = CHECK_SCRIPT + " | xargs kill"


def is_dev_server_running():
    out = subprocess.check_output(CHECK_SCRIPT, shell=True)
    if out:
        return True
    else:
        return False


def delay_to_show_server_status():
    time.sleep(2)
    click.echo("")
    subprocess.call("python gae.py status", shell=True)
    click.echo("\nPress <Enter> to continue ...")


def stop_dev_server(kill):
    try:
        subprocess.check_call(KILL_SCRIPT + "" if not kill else " -9", shell=True)
        click.secho("[Done]", fg="green")
    except CalledProcessError as e:
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


def run_dev_server(cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, universal_newlines=True)
    while True:
        line = ""
        is_pdb = False
        while True:
            output = process.stdout.read(1)
            if output != "\n":
                line += output
            else:
                break
            if line.startswith('(Pdb) '):
                is_pdb = True
                break
        if line:
            highlight_output = highlight(line.strip(), PythonLexer(), TerminalFormatter(bg="dark"))
            if is_pdb:
                print("(Pdb) ", end='')
            else:
                click.echo(highlight_output, nl=False)
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
    cmd += " " + " ".join(dev_appserver_options)
    return cmd


@click.group()
def gae():
    # before hook
    pass


@gae.command()
def status():
    """Show running status"""
    if is_dev_server_running():
        click.secho("Dev server is running", fg="green")
    else:
        click.secho("Dev server is stopped", fg="red")


@gae.command()
@click.option('-k', '--kill', 'kill', is_flag=True,
              help='e.g. --kill')
def stop(kill):
    """Stop your local dev server"""
    stop_dev_server(kill)


@gae.command()
@click.option('-p', '--page', 'page', default="",
              help='e.g. --page console')
def admin(page):
    """Launch your GAE admin page in the browser"""
    click.launch('http://localhost:8000/' + page)


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
    run_dev_server(cmd)


@gae.command()
@click.option('-c', '--config', 'config_path', nargs=1, type=click.Path(exists=True),
              help='e.g. --config config.py')
@click.argument('dev_appserver_options', nargs=-1)
def daemon(config_path, dev_appserver_options):
    """Start your GAE local dev server as a daemon"""
    if is_dev_server_running():
        click.echo("[Error] Your local dev server is already running")
        return

    cfg = load_config_file(config_path)
    if not cfg:
        return

    cmd = construct_run_server_cmd(cfg, dev_appserver_options)

    p = Process(target=delay_to_show_server_status, args=())
    p.start()

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
    """Run your code in interactive console"""
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
