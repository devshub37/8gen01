"""Unit tests for HTML game validator."""

from eightgen.core.validator import GameValidator
from tests.conftest import SAMPLE_VALID_GAME


def test_validator_valid_game():
    result = GameValidator.validate(SAMPLE_VALID_GAME)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validator_missing_script():
    invalid_html = """<!DOCTYPE html><html><body><canvas id="c"></canvas></body></html>"""
    result = GameValidator.validate(invalid_html)
    assert result.is_valid is False
    assert any("Missing <script>" in err for err in result.errors)


def test_validator_unclosed_html():
    invalid_html = """<!DOCTYPE html><html><body><canvas id="c"></canvas><script>let x = 1;</script>"""
    result = GameValidator.validate(invalid_html)
    assert result.is_valid is False
    assert any("Unclosed <html>" in err for err in result.errors)


def test_validator_empty():
    result = GameValidator.validate("")
    assert result.is_valid is False
    assert "Empty" in result.errors[0]


def test_validator_quality_warnings():
    bare_game = """<!DOCTYPE html>
<html><body>
<canvas id="c" width="400" height="300"></canvas>
<script>
const c = document.getElementById('c');
window.addEventListener('keydown', (e) => {
  localStorage.setItem('k', '1');
});
function loop() {
  requestAnimationFrame(loop);
}
loop();
</script>
</body></html>"""
    result = GameValidator.validate(bare_game, check_js=False)
    assert result.is_valid is True
    joined = " | ".join(result.warnings).lower()
    assert "touch/pointer" in joined
    assert "preventdefault" in joined
    assert "restart/reset" in joined
    assert "delta/fixed timestep" in joined
    assert "localstorage" in joined
