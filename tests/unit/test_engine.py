"""Unit tests for core game engine and guaranteed archetypes."""

from eightgen.core.engine.archetypes import (
    build_space_shooter_game,
    build_brick_breaker_game,
    build_cyber_snake_game,
    build_flappy_drone_game,
    build_smart_archetype,
)
from eightgen.core.engine.references import (
    REFERENCE_GAMES,
    get_reference_spec,
    build_simple_reference_game,
)
from eightgen.core.validator import GameValidator


def test_space_shooter_archetype():
    html = build_space_shooter_game("Galactic Blast")
    assert "<!DOCTYPE html>" in html
    assert "Galactic Blast" in html
    val = GameValidator.validate(html)
    assert val.is_valid, f"Validation errors: {val.errors}"


def test_brick_breaker_archetype():
    html = build_brick_breaker_game("Laser Arkanoid")
    assert "<!DOCTYPE html>" in html
    assert "Laser Arkanoid" in html
    val = GameValidator.validate(html)
    assert val.is_valid, f"Validation errors: {val.errors}"


def test_cyber_snake_archetype():
    html = build_cyber_snake_game("Retro Snake")
    assert "<!DOCTYPE html>" in html
    assert "Retro Snake" in html
    val = GameValidator.validate(html)
    assert val.is_valid, f"Validation errors: {val.errors}"


def test_flappy_drone_archetype():
    html = build_flappy_drone_game("Neon Flappy")
    assert "<!DOCTYPE html>" in html
    assert "Neon Flappy" in html
    val = GameValidator.validate(html)
    assert val.is_valid, f"Validation errors: {val.errors}"


def test_smart_archetype_dispatcher():
    # Snake matching
    snake_html = build_smart_archetype("Make a neon snake game with fruits")
    assert "Snake" in snake_html
    assert GameValidator.validate(snake_html).is_valid

    # Brick breaker matching
    brick_html = build_smart_archetype("Destructible breakout wall with paddle")
    assert "Breakout" in brick_html or "Brick" in brick_html
    assert GameValidator.validate(brick_html).is_valid

    # Drone flight matching
    drone_html = build_smart_archetype("Flappy drone flying through electric obstacles")
    assert "Drone" in drone_html or "Odyssey" in drone_html
    assert GameValidator.validate(drone_html).is_valid

    # Default shooter
    shooter_html = build_smart_archetype("Alien galaxy invader defense")
    assert "Defender" in shooter_html or "Space" in shooter_html
    assert GameValidator.validate(shooter_html).is_valid


def test_simple_reference_games_all_build_and_validate():
    assert len(REFERENCE_GAMES) >= 8
    for spec in REFERENCE_GAMES:
        assert get_reference_spec(spec.id) == spec
        html = build_simple_reference_game(spec.id)
        assert html is not None
        assert "<!DOCTYPE html>" in html
        val = GameValidator.validate(html)
        assert val.is_valid, f"Reference game '{spec.id}' failed validation: {val.errors}"

    assert get_reference_spec("unknown-ref") is None
    assert build_simple_reference_game("unknown-ref") is None
