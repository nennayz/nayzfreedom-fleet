import json
from unittest.mock import MagicMock, patch
from orchestrator import Orchestrator
from tests.test_mia import make_config, make_job
from models.content_job import JobStatus


def _make_tool_use_block(name, tool_id="t1", input_data=None):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = input_data or {}
    return block


def _make_end_turn_response():
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [MagicMock(type="text", text="All done!")]
    return resp


def test_orchestrator_dry_run_completes(mocker, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()

    # Robin calls agents in sequence then end_turn
    tool_sequence = [
        [_make_tool_use_block("run_mia", "t1")],
        [_make_tool_use_block("run_zoe", "t2")],
        [_make_tool_use_block("request_checkpoint", "t3",
            {"stage": "idea_selection", "summary": "Pick an idea", "options": ["1. Lip Hack"]})],
        [_make_tool_use_block("run_bella", "t4")],
        [_make_tool_use_block("run_lila", "t5")],
        [_make_tool_use_block("request_checkpoint", "t6",
            {"stage": "content_review", "summary": "Review script"})],
        [_make_tool_use_block("run_nora", "t7")],
        [_make_tool_use_block("request_checkpoint", "t8",
            {"stage": "qa_review", "summary": "QA passed"})],
        [_make_tool_use_block("run_roxy", "t9")],
        [_make_tool_use_block("run_emma", "t10")],
        [_make_tool_use_block("request_checkpoint", "t11",
            {"stage": "final_approval", "summary": "Ready to publish?"})],
    ]

    call_count = [0]
    def mock_create(**kwargs):
        i = call_count[0]
        call_count[0] += 1
        if i < len(tool_sequence):
            resp = MagicMock()
            resp.stop_reason = "tool_use"
            resp.content = tool_sequence[i]
            return resp
        return _make_end_turn_response()

    mocker.patch("orchestrator.anthropic.Anthropic").return_value.messages.create.side_effect = mock_create
    mocker.patch("builtins.input", return_value="1")

    orch = Orchestrator(make_config())
    job = make_job(dry_run=True)
    result = orch.run(job)

    assert result.status == JobStatus.COMPLETED
    assert result.trend_data is not None
    assert result.ideas is not None
    assert result.script is not None
    assert len(result.checkpoint_log) == 4
