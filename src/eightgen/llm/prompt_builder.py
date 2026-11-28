"""Constructs structured LLM messages using prompt templates."""

from typing import List, Optional
from eightgen.llm.base import LLMMessage
from eightgen.prompts.loader import get_prompt_loader


class PromptBuilder:
    """Builds prompt message chains for generation, refinement, and debugging."""

    def __init__(self):
        self.loader = get_prompt_loader()

    def design_brief(
        self,
        prompt: str,
        category: Optional[str] = None,
        game_reference: Optional[str] = None,
    ) -> str:
        """Return the curated controls/physics brief for this request."""
        from eightgen.core.engine.design_knowledge import (
            detect_design_spec,
            render_design_brief,
        )

        spec = detect_design_spec(prompt, category, game_reference)
        return render_design_brief(spec)

    def build_generate_messages(
        self,
        prompt: str,
        category: Optional[str] = None,
        game_reference: Optional[str] = None,
        learned_context: str = "",
    ) -> List[LLMMessage]:
        """Construct system and user messages for a new game."""
        from eightgen.core.engine.references import get_reference_spec

        system_content = self.loader.render("system/game_generator.j2", {})
        reference_spec = get_reference_spec(game_reference) if game_reference else None
        design_brief = self.design_brief(prompt, category, game_reference)
        if learned_context:
            design_brief = f"{design_brief.rstrip()}\n\n{learned_context.strip()}"

        skeleton_hint = ""
        if category and not reference_spec:
            cat_clean = category.lower().strip()
            if cat_clean in ["arcade", "shooter", "action"]:
                skeleton_hint = self.loader.render("examples/arcade.j2", {})
            elif cat_clean in ["platformer", "jump", "runner"]:
                skeleton_hint = self.loader.render("examples/platformer.j2", {})
            elif cat_clean in ["puzzle", "grid", "match", "logic"]:
                skeleton_hint = self.loader.render("examples/puzzle.j2", {})

        user_content = self.loader.render(
            "user/generate.j2",
            {
                "prompt": prompt,
                "category": category,
                "skeleton_hint": skeleton_hint,
                "reference_spec": reference_spec,
                "design_brief": design_brief,
            },
        )

        return [
            LLMMessage(role="system", content=system_content),
            LLMMessage(role="user", content=user_content),
        ]

    def build_refine_messages(
        self,
        existing_html: str,
        instruction: str,
        design_brief: str = "",
    ) -> List[LLMMessage]:
        """Construct messages for iterating/improving an existing game."""
        system_content = self.loader.render("system/game_refiner.j2", {})
        user_content = self.loader.render(
            "user/refine.j2",
            {
                "existing_html": existing_html,
                "instruction": instruction,
                "design_brief": design_brief,
            },
        )
        return [
            LLMMessage(role="system", content=system_content),
            LLMMessage(role="user", content=user_content),
        ]

    def build_fix_messages(
        self,
        broken_html: str,
        errors: List[str],
        design_brief: str = "",
    ) -> List[LLMMessage]:
        """Construct messages to debug and repair invalid game code."""
        system_content = self.loader.render("system/game_debugger.j2", {})
        user_content = self.loader.render(
            "user/fix.j2",
            {
                "broken_html": broken_html,
                "errors": errors,
                "design_brief": design_brief,
            },
        )
        return [
            LLMMessage(role="system", content=system_content),
            LLMMessage(role="user", content=user_content),
        ]
