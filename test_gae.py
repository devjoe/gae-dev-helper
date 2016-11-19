import time
import subprocess
import urllib2
from urllib2 import URLError

import click
from click.testing import CliRunner
import pytest

from gae import gae


@pytest.fixture
def setup_and_teardown_dev_server():
    url = "http://localhost:8000/"
    try:
        urllib2.urlopen(url)
    except URLError as e:
        subprocess.call("python gae.py daemon --config custom_config.py", shell=True)
        time.sleep(2)
    yield
    subprocess.call("ps -eo pid,command | grep 'python dev_appserver.py' | grep -v grep | grep -v '/bin/sh -c cd' | awk '{print $1}' | xargs kill", shell=True)
    time.sleep(2)


@pytest.fixture
def teardown_dev_server():
    url = "http://localhost:8000/"
    with pytest.raises(URLError):
        urllib2.urlopen(url)
    yield
    subprocess.call("ps -eo pid,command | grep 'python dev_appserver.py' | grep -v grep | grep -v '/bin/sh -c cd' | awk '{print $1}' | xargs kill", shell=True)
    time.sleep(2)


def test_interactive(setup_and_teardown_dev_server):
    runner = CliRunner()

    result = runner.invoke(gae, ['interactive', '--code', 'print("\'hello code\'")'])
    assert result.exit_code == 0
    assert "[Error]" not in result.output
    assert "'hello code'" in result.output

    result = runner.invoke(gae, ['interactive', '--file', 'sample.py'])
    assert result.exit_code == 0
    assert "'hello file'" in result.output

    result = runner.invoke(gae, ['interactive', '--stream'], input='print("\'hello stream\'")')
    assert result.exit_code == 0
    assert "'hello stream'" in result.output

    result = runner.invoke(gae, ['interactive', '--file', 'sample.py',
                                                '--code', 'print("\'hello world\'")',
                                                '--stream'],
                                input='print("\'hello stream\'")')
    assert result.exit_code == 0
    assert "'hello file'" in result.output
    assert "'hello world'" in result.output
    assert "'hello stream'" in result.output


def test_interactive_not_enough_parameters():
    runner = CliRunner()
    result = runner.invoke(gae, ['interactive'])
    assert result.exit_code == 0
    assert "[Error]" in result.output


def test_admin(mocker):
    mocked_launch = mocker.patch("click.launch")
    mocked_launch.return_value = True
    runner = CliRunner()
    result = runner.invoke(gae, ['admin'])
    assert result.exit_code == 0
    assert "[Error]" not in result.output


def test_daemon_run_by_args(teardown_dev_server):
    subprocess.call("python gae.py daemon -- --port=8080", shell=True)
    time.sleep(2)
    url = "http://localhost:8000/"
    urllib2.urlopen(url)


def test_daemon_run_by_wrong_args(teardown_dev_server):
    subprocess.call("python gae.py daemon -- -ooxx", shell=True)
    time.sleep(2)
    url = "http://localhost:8000/"
    with pytest.raises(URLError):
        urllib2.urlopen(url)


def test_daemon_run_by_config(teardown_dev_server):
    subprocess.call("python gae.py daemon --config custom_config.py", shell=True)
    time.sleep(2)
    url = "http://localhost:8000/"
    urllib2.urlopen(url)


def test_daemon_no_gae_sdk_path_in_config(mocker):
    runner = CliRunner()
    mocked_get_app_dir = mocker.patch("click.get_app_dir")
    mocked_get_app_dir.return_value = 'wrong_path_ljdsiew'
    result = runner.invoke(gae, ['daemon'])
    assert result.exit_code == 0


def test_daemon_can_not_load_config_file(mocker):
    runner = CliRunner()
    mocked_get_app_dir = mocker.patch("click.get_app_dir")
    mocked_get_app_dir.return_value = 'wrong_path_ljdsiew'
    result = runner.invoke(gae, ['daemon'])
    assert "[Error]" in result.output


def test_daemon_fail_to_start():
    runner = CliRunner()
    result = runner.invoke(gae, ['daemon', '--config', 'broken_config.py'])
    assert "[Error]" in result.output

