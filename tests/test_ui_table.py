"""User simulation tests for level table and sliders (Task 12)."""
import pytest


async def test_type_value_marks_changed(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="cell-towers.archers.price.1").clear().type("7").trigger("keydown.enter")
    await user.should_see(marker="orig-towers.archers.price.1")  # original 70 shown


async def test_bad_text_reverts(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="cell-towers.archers.price.1").clear().type("abc").trigger("keydown.enter")
    await user.should_see("Not a number")


async def test_enum_read_only(user):
    await user.open("/")
    user.find("Enemies").click()
    user.find("Demon lord").click()
    await user.should_see("Physical")


async def test_reset_cell_reverts_value(user):
    await user.open("/")
    user.find("Archers").click()
    cell = user.find(marker="cell-towers.archers.price.1")
    cell.clear().type("7").trigger("keydown.enter")
    await user.should_see(marker="orig-towers.archers.price.1")
    # Click reset button for this cell:
    user.find(marker="reset-towers.archers.price.1").click()
    await user.should_not_see(marker="orig-towers.archers.price.1")


async def test_warning_shown_for_negative(user):
    await user.open("/")
    user.find("Archers").click()
    cell = user.find(marker="cell-towers.archers.price.1")
    cell.clear().type("-10").trigger("keydown.enter")
    await user.should_see("Negative values can break the game.")


async def test_c2_panel_toggle(user):
    await user.open("/")
    user.find("Archers").click()
    # Click on the row label or expand button for Price:
    user.find(marker="row-expand-price").click()
    # Should see C2 panel with lock and level slider:
    await user.should_see(marker="c2-lock-price")
    await user.should_see(marker="c2-bar-orig-towers.archers.price.1")
    await user.should_see(marker="c2-bar-curr-towers.archers.price.1")


async def test_card_c1_slider_halves_prices(user):
    await user.open("/")
    user.find("Knights").click()
    slider = user.find(marker="card-slider-all-costs")
    # 0.0 track maps to 50%:
    slider.trigger("change", 0.0)
    await user.should_see("50%")
    c1 = list(user.find(marker="cell-towers.knights.price.1").elements)[0]
    c2 = list(user.find(marker="cell-towers.knights.price.2").elements)[0]
    c3 = list(user.find(marker="cell-towers.knights.price.3").elements)[0]
    c4 = list(user.find(marker="cell-towers.knights.price.4").elements)[0]
    assert c1.value == "35"
    assert c2.value == "55"
    assert c3.value == "80"
    assert c4.value == "110"


async def test_row_c1_slider_and_mixed_label(user):
    await user.open("/")
    user.find("Archers").click()
    sl = user.find(marker="row-slider-price")
    # 0.0 track maps to 50%:
    sl.trigger("change", 0.0)
    c1 = list(user.find(marker="cell-towers.archers.price.1").elements)[0]
    c2 = list(user.find(marker="cell-towers.archers.price.2").elements)[0]
    assert c1.value == "35"
    assert c2.value == "50"
    row_val = list(user.find(marker="row-val-price").elements)[0]
    assert row_val.text == "50%"

    # Edit one cell to create mixed ratio:
    user.find(marker="cell-towers.archers.price.1").clear().type("99").trigger("keydown.enter")
    row_val = list(user.find(marker="row-val-price").elements)[0]
    assert row_val.text == "mixed"


async def test_c2_lock_moves_all_levels(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="row-expand-price").click()
    # Turn on lock:
    user.find(marker="c2-lock-price").click()
    # Move Level 1 from 70 to 140 (200%):
    user.find(marker="c2-slider-towers.archers.price.1").trigger("change", 140.0)
    c2 = list(user.find(marker="cell-towers.archers.price.2").elements)[0]
    # Original was 100, so 200% scales to 200:
    assert c2.value == "200"


async def test_c2_unlocked_moves_single_level(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="row-expand-price").click()
    # Move Level 1 without lock:
    user.find(marker="c2-slider-towers.archers.price.1").trigger("change", 140.0)
    c1 = list(user.find(marker="cell-towers.archers.price.1").elements)[0]
    c2 = list(user.find(marker="cell-towers.archers.price.2").elements)[0]
    assert c1.value == "140"
    assert c2.value == "100"


async def test_zero_original_leaves_at_zero(user):
    await user.open("/")
    user.find("Alchemist").click()
    p_str = "towers.alchemist.ultimate.gold_pig.armor"
    cell = list(user.find(marker=f"cell-{p_str}").elements)[0]
    assert cell.value == "0"
    # Move row slider to 300% (track 1.0):
    user.find(marker="row-slider-ultimate-gold_pig-armor").trigger("change", 1.0)
    cell = list(user.find(marker=f"cell-{p_str}").elements)[0]
    assert cell.value == "0"
