import time
import subprocess
import urllib2
from urllib2 import URLError

import click
from click.testing import CliRunner
import pytest

import gaedevhelper.gae
from gaedevhelper.gae import gae, is_dev_server_running, filter_output, stop_dev_server


@pytest.fixture
def setup_and_teardown_dev_server():
    assert is_dev_server_running() is False
    subprocess.call("python gaedevhelper/gae.py daemon --config tests/custom_config.py", shell=True)
    time.sleep(3)
    yield
    stop_dev_server()
    time.sleep(3)


@pytest.fixture
def teardown_dev_server():
    assert is_dev_server_running() is False
    yield
    stop_dev_server()
    time.sleep(3)


def test_interactive(setup_and_teardown_dev_server):
    runner = CliRunner()

    result = runner.invoke(gae, ['interactive', '--code', 'print("\'hello code\'")'])
    assert result.exit_code == 0
    assert "[Error]" not in result.output
    assert "'hello code'" in result.output

    result = runner.invoke(gae, ['interactive', '--file', 'tests/sample.py'])
    assert result.exit_code == 0
    assert "'hello file'" in result.output

    result = runner.invoke(gae, ['interactive', '--stream'], input='print("\'hello stream\'")')
    assert result.exit_code == 0
    assert "'hello stream'" in result.output

    result = runner.invoke(gae, ['interactive', '--file', 'tests/sample.py',
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
    subprocess.call("python gaedevhelper/gae.py daemon -- --port=8080", shell=True)
    time.sleep(2)
    assert is_dev_server_running()


def test_daemon_run_by_wrong_args(teardown_dev_server):
    subprocess.call("python gaedevhelper/gae.py daemon -- -ooxx", shell=True)
    time.sleep(2)
    assert is_dev_server_running() is False


def test_daemon_run_by_config(teardown_dev_server):
    subprocess.call("python gaedevhelper/gae.py daemon --config tests/custom_config.py", shell=True)
    time.sleep(2)
    assert is_dev_server_running()


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


def test_filter_output():
    line = 'INFO     2016-11-19 16:24:45,908 module.py:787] default: "GET /javascript/bootstrap3-package/carousel.js HTTP/1.1" 304 -'
    class Config(object):
        filetype_ignore_filter = ['js']
    cfg = Config()
    assert filter_output(line, cfg) == ""
