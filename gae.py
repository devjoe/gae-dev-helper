import urllib
import urllib2
from urllib2 import URLError
import re

import click


@click.group()
def gae():
    # before hook
    pass



@gae.command()
@click.option('-c', '--code', 'code', nargs=1, type=click.STRING)
@click.option('-f', '--file', 'f', nargs=1, type=click.File('rb'))
def interactive(code, f):
    """Run code in dev server's interactive console"""
    if not code and not f:
        click.echo("[Error] Use --code or --file\n")
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
        rpc_code = rpc_code + "\n" + code

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

