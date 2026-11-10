"""エージェントの配線テスト。

TestModel は実際のLLMを呼ばない偽モデルで、登録されたツールを全部呼んでから
ダミーの回答を返す。APIキーも利用枠も使わずに、
「ツールが登録され、呼ばれ、結果がモデルに戻るか」を確かめられる。
"""

from pydantic_ai import DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel

from app.agent import agent, confirm_tool_approvals, main
from app import tools

BASE_TOOLS = {"search_glossary", "get_lecture_summary"}


def _parts(result, kind):
    return [p for m in result.all_messages() for p in m.parts if isinstance(p, kind)]


def test_base_tools_are_registered_and_called():
    model = TestModel()
    with agent.override(model=model):
        result = agent.run_sync("LoRAとは？")

    offered = {t.name for t in model.last_model_request_parameters.function_tools}
    assert BASE_TOOLS <= offered  # 演習でツールを足しても壊れないよう「含む」で判定

    called = {p.tool_name for p in _parts(result, ToolCallPart)}
    assert BASE_TOOLS <= called
    # 承認が必要なツール（requires_approval=True）は、実行されずに承認待ちになるので戻り値が無い
    waiting = len(result.output.approvals) if isinstance(result.output, DeferredToolRequests) else 0
    assert len(_parts(result, ToolReturnPart)) + waiting == len(_parts(result, ToolCallPart))
    assert result.output


def test_glossary_result_reaches_the_model():
    model = TestModel(call_tools=["search_glossary"])
    with agent.override(model=model):
        result = agent.run_sync("RAGとは？")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "search_glossary"


def test_learning_log_is_saved_only_after_approval(tmp_path, monkeypatch):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    model = TestModel(call_tools=["save_learning_log"])
    with agent.override(model=model):
        pending = agent.run_sync("この内容を学習記録に保存して")

    assert isinstance(pending.output, DeferredToolRequests)
    assert not log_dir.exists()

    request = pending.output.approvals[0]
    with agent.override(model=TestModel(call_tools=[])):
        agent.run_sync(
            None,
            message_history=pending.all_messages(),
            deferred_tool_results=DeferredToolResults(
                approvals={request.tool_call_id: True}
            ),
        )

    files = list(log_dir.glob("*.md"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8").strip()


def test_learning_log_is_not_saved_when_approval_is_denied(tmp_path, monkeypatch):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    with agent.override(model=TestModel(call_tools=["save_learning_log"])):
        pending = agent.run_sync("この内容を学習記録に保存して")

    assert isinstance(pending.output, DeferredToolRequests)
    request = pending.output.approvals[0]
    with agent.override(model=TestModel(call_tools=[])):
        agent.run_sync(
            None,
            message_history=pending.all_messages(),
            deferred_tool_results=DeferredToolResults(
                approvals={request.tool_call_id: False}
            ),
        )

    assert not log_dir.exists()


def test_confirmation_prompt_returns_approval_for_requested_tool(monkeypatch):
    with agent.override(model=TestModel(call_tools=["save_learning_log"])):
        pending = agent.run_sync("この内容を学習記録に保存して")
    request = pending.output.approvals[0]
    monkeypatch.setattr("builtins.input", lambda _: "y")

    decisions = confirm_tool_approvals(pending.output)

    assert decisions.approvals == {request.tool_call_id: True}


def test_interactive_cli_reuses_message_history(monkeypatch):
    calls = []

    class Result:
        output = "回答"

        def __init__(self, messages):
            self.messages = messages

        def all_messages(self):
            return self.messages

    def run_sync(question, *, message_history=None, **kwargs):
        calls.append((question, message_history))
        return Result([*(message_history or []), question])

    prompts = iter(["2つ目の質問", ""])
    monkeypatch.setattr(agent, "run_sync", run_sync)
    monkeypatch.setattr("app.agent.build_model", lambda: object())
    monkeypatch.setattr("sys.argv", ["app.agent", "--interactive", "最初の質問"])
    monkeypatch.setattr("builtins.input", lambda _: next(prompts))

    main()

    assert calls == [
        ("最初の質問", None),
        ("2つ目の質問", ["最初の質問"]),
    ]
