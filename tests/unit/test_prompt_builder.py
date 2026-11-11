"""Unit tests for prompt builder."""

from eightgen.llm.prompt_builder import PromptBuilder


def test_build_generate_messages():
    builder = PromptBuilder()
    messages = builder.build_generate_messages("Space invaders", category="arcade")
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert "game developer" in messages[0].content.lower()
    assert messages[1].role == "user"
    assert "Space invaders" in messages[1].content
    assert "Arcade" in messages[1].content


def test_build_refine_messages():
    builder = PromptBuilder()
    messages = builder.build_refine_messages("<html><body>old</body></html>", "add sound effects")
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert "modifying and improving" in messages[0].content.lower()
    assert "add sound effects" in messages[1].content


def test_build_fix_messages():
    builder = PromptBuilder()
    messages = builder.build_fix_messages("<html>bad code", ["Missing </html> tag."])
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert "debugger" in messages[0].content.lower()
    assert "Missing </html> tag." in messages[1].content


def test_build_generate_messages_with_reference():
    builder = PromptBuilder()
    messages = builder.build_generate_messages(
        "Classic simple Pong game",
        category="arcade",
        game_reference="pong",
    )
    assert len(messages) == 2
    user_prompt = messages[1].content
    assert "Game Reference Mode" in user_prompt
    assert "Pong (Classic Paddle)" in user_prompt
    assert "Simple Controls" in user_prompt
    assert "Simple Game Logic" in user_prompt
    assert "Architecture Advice" not in user_prompt
