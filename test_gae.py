from click.testing import CliRunner

from gae import gae


def test_interactive():
    runner = CliRunner()
    result = runner.invoke(gae, ['interactive'])
    assert result.exit_code == 0
    assert "[Error]" not in result.output
    import pdb; pdb.set_trace();

