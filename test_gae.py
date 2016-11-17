from click.testing import CliRunner

from gae import gae


def test_interactive():
    runner = CliRunner()

    result = runner.invoke(gae, ['interactive'])
    assert result.exit_code == 0
    assert "[Error]" in result.output

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


def test_admin():
    runner = CliRunner()
    result = runner.invoke(gae, ['admin'])
    assert result.exit_code == 0
    assert "[Error]" not in result.output
