"""CLI tests (Typer's CliRunner, no subprocess and no network)."""

from __future__ import annotations

import json

import pytest
from ned.app.cli import app
from ned.app.version import __version__
from typer.testing import CliRunner

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Nov1ce Evidence Denier" in result.stdout
    assert __version__ in result.stdout


def test_help_lists_the_documented_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("analyze", "asymmetry", "fnbp", "demo", "examples", "serve", "version"):
        assert command in result.stdout


def test_analyze_json_output_is_the_api_contract() -> None:
    result = runner.invoke(app, ["analyze", "她对我说“我想你了”", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["input"] == "她对我说“我想你了”"
    assert payload["mode"] == "normal"
    assert payload["signal_type"] == "missing_you"
    assert payload["verdict"]["text"]
    assert payload["alternative_explanations"]


def test_analyze_renders_a_report_by_default() -> None:
    result = runner.invoke(app, ["analyze", "她对我说“我想你了”"])
    assert result.exit_code == 0
    assert "Final Verdict" in result.stdout
    assert "Alternative Hypotheses" in result.stdout
    assert "Reality Check" in result.stdout


@pytest.mark.parametrize("mode", ["normal", "scientific", "extreme"])
def test_analyze_modes(mode: str) -> None:
    result = runner.invoke(app, ["analyze", "她对我说“我想你了”", "--mode", mode, "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["mode"] == mode


def test_analyze_extreme_marriage() -> None:
    result = runner.invoke(app, ["analyze", "我想和你结婚", "--mode", "extreme", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "extreme"
    assert payload["signal_type"] == "marriage"


def test_analyze_rejects_an_unknown_mode() -> None:
    result = runner.invoke(app, ["analyze", "她对我说“我想你了”", "--mode", "chaos"])
    assert result.exit_code == 2
    assert "Unknown mode" in result.stdout


def test_analyze_reaching_report_includes_personality_copy() -> None:
    result = runner.invoke(
        app,
        [
            "analyze",
            "marry me",
            "--mode",
            "extreme",
            "--history",
            "I love you",
            "--history",
            "be my partner",
            "--history",
            "let us get married",
        ],
    )
    assert result.exit_code == 0
    assert "NED is currently reaching." in result.stdout
    # the panel wraps long lines, so assert the stable prefix
    assert "Technical: NED" in result.stdout


def test_analyze_accepts_history_for_escalation() -> None:
    result = runner.invoke(
        app,
        [
            "analyze",
            "我们已经结婚了",
            "--mode",
            "extreme",
            "--json",
            "--history",
            "我喜欢你",
            "--history",
            "我想和你谈恋爱",
            "--history",
            "做我男朋友吧",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["verdict"]["code"] == "ned.capacity_exhausted"
    assert payload["ned_reaching_level"] == 100.0


def test_asymmetry_command() -> None:
    result = runner.invoke(
        app,
        [
            "asymmetry",
            "--positive",
            "她主动找我聊了两个小时",
            "--negative",
            "五分钟没回复",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["positive_threshold"] == "EXTREMELY HIGH"
    assert payload["negative_threshold"] == "EXTREMELY LOW"
    assert payload["asymmetry_score"] >= 75


def test_asymmetry_command_renders_panel() -> None:
    result = runner.invoke(
        app, ["asymmetry", "--positive", "她主动找我聊了两个小时", "--negative", "五分钟没回复"]
    )
    assert result.exit_code == 0
    assert "Evidence Comparison" in result.stdout
    assert "Evidence Profile" in result.stdout
    assert "NED Treatment" in result.stdout
    assert "Your Reading" in result.stdout
    assert "不评估你的证据标准" in result.stdout
    assert "Admission" not in result.stdout


def test_asymmetry_command_requires_input() -> None:
    result = runner.invoke(app, ["asymmetry"])
    assert result.exit_code == 2
    assert "cannot compare evidence" in result.stdout


def test_asymmetry_command_accepts_free_text() -> None:
    result = runner.invoke(
        app, ["asymmetry", "--text", "她主动找我聊了两个小时，但五分钟没回复", "--json"]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["asymmetry_score"] > 0


def test_fnbp_command() -> None:
    result = runner.invoke(app, ["fnbp", "--count", "3", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["notifications"] == 3
    assert payload["verdict"]["text"] == "怎么又不是她效应"


def test_fnbp_command_renders_pipeline_log() -> None:
    result = runner.invoke(app, ["fnbp", "--count", "2"])
    assert result.exit_code == 0
    assert "怎么又不是她效应" in result.stdout
    assert "NED 提醒：" in result.stdout
    assert "预测不是事实。期待也不是证据。🤠" in result.stdout
    assert "Prediction is not reality. Expectation is not evidence." in result.stdout
    assert "PIPELINE FLUSHED" in result.stdout
    assert "Fuyuki Notification Branch Predictor" in result.stdout


def test_fnbp_command_personalizes_a_successful_prediction() -> None:
    result = runner.invoke(
        app,
        ["fnbp", "--expected", "Fuyuki", "--actual", "Fuyuki", "--count", "2"],
    )
    assert result.exit_code == 0
    assert "🎯 命中了。" in result.stdout
    assert "一次预测成功，不等于发现了规律。🤠" in result.stdout
    assert "One successful prediction does not mean a pattern has been discovered." in result.stdout


def test_demo_runs_every_example_case() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "case.miss-you" in result.stdout
    assert "verdict:" in result.stdout


def test_demo_json_output() -> None:
    result = runner.invoke(app, ["demo", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload) >= 8
    assert all(item["verdict"]["text"] for item in payload)


def test_examples_command() -> None:
    result = runner.invoke(app, ["examples"])
    assert result.exit_code == 0
    assert "case.marriage" in result.stdout


def test_examples_json_output() -> None:
    result = runner.invoke(app, ["examples", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload and all("text" in case for case in payload)


def test_json_output_is_really_json() -> None:
    """Every --json command must be machine-parseable, with no banner text."""

    for args in (
        ["analyze", "她对我说“我想你了”", "--json"],
        [
            "asymmetry",
            "--positive",
            "她主动找我聊了两个小时",
            "--negative",
            "五分钟没回复",
            "--json",
        ],
        ["fnbp", "--json"],
        ["demo", "--json"],
        ["examples", "--json"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, args
        json.loads(result.stdout.strip())


def test_cli_needs_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard rail: the CLI must work with sockets disabled."""

    import socket

    def _no_socket(*args: object, **kwargs: object) -> None:
        raise AssertionError("the CLI must never open a socket")

    monkeypatch.setattr(socket, "socket", _no_socket)
    result = runner.invoke(app, ["analyze", "她对我说“我想你了”", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["signal_type"] == "missing_you"


def test_analyze_frames_the_amplified_reading() -> None:
    """The CLI NEA panel must say the inflated reading is not NED's conclusion."""

    result = runner.invoke(app, ["analyze", "他让我滚出去别烦他了"])
    assert result.exit_code == 0
    out = result.stdout
    assert "Negative Evidence Amplifier" in out
    assert "我是不是开始觉得" in out
    assert "这是 NED 正在检查的夸大解读，不是 NED 的结论。" in out
    assert "ned.direct_rejection" in out
