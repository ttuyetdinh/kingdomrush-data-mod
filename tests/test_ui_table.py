"""User simulation tests for the level table: cell boxes, Row % boxes and quick scale boxes."""
from nicegui import ui
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
    c = list(user.find(marker="cell-towers.archers.price.1").elements)[0]
    assert c.value == "70"
    await user.should_not_see(marker="orig-towers.archers.price.1")


async def test_enum_read_only(user):
    await user.open("/")
    user.find("Enemies").click()
    user.find("Demon lord").click()
    await user.should_see("Physical")
    await user.should_not_see(marker="cell-enemies.demons.demon_lord.basic_attack.damage_type")


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


async def test_warning_tooltip_not_duplicated(user):
    await user.open("/")
    user.find("Archers").click()
    cell = user.find(marker="cell-towers.archers.price.1")
    cell.clear().type("-10").trigger("keydown.enter")
    cell.clear().type("-20").trigger("keydown.enter")
    icon = list(user.find(marker="warn-towers.archers.price.1").elements)[0]
    tooltips = [c for c in icon.default_slot.children if type(c).__name__ == "Tooltip"]
    assert len(tooltips) == 1


async def test_headers_and_groups_rendered(user):
    await user.open("/")
    user.find("Archers").click()
    await user.should_see("Level 1")
    await user.should_see("Level 4")
    await user.should_see("Row %")
    await user.should_see("Skill a")


async def test_missing_levels_blank(user):
    await user.open("/")
    user.find("Knights").click()
    # Missing levels must be blank, without placeholder '-' labels:
    labels = [e for e in user._gather_elements(None, ui.label, None, None) if e.text == "-"]
    assert len(labels) == 0


async def test_row_label_tooltips_show_raw_id(user):
    await user.open("/")
    user.find("Knights").click()
    await user.should_see("Cd mult (info text)")
    tooltips = [e.text for e in user._gather_elements(None, ui.tooltip, None, None)]
    assert "skill_c.s_cd_mult" in tooltips
    assert "skill_c.cd_mult" in tooltips
    assert "price" in tooltips

async def test_precision_formatting(user):
    await user.open("/")
    user.find("Heroes").click()
    user.find("Bolin").click()
    # heroes.hero_bolin.skill_c.boss_hp_percentage has original 0.002
    await user.should_see("0.002")
    assert _val(user, "cell-heroes.hero_bolin.skill_c.boss_hp_percentage") == "0.002"


def _val(user, marker):
    return list(user.find(marker=marker).elements)[0].value


PRICE1 = "cell-towers.archers.price.1"  # original 70
PRICE2 = "cell-towers.archers.price.2"  # original 100


async def test_step_up_down_saves_and_marks_changed(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker=f"{PRICE1}-up").click()
    assert _val(user, PRICE1) == "71"
    await user.should_see(marker="orig-towers.archers.price.1")
    user.find(marker=f"{PRICE1}-down").click()
    user.find(marker=f"{PRICE1}-down").click()
    assert _val(user, PRICE1) == "69"
    user.find(marker=f"{PRICE1}-up").click()
    assert _val(user, PRICE1) == "70"
    await user.should_not_see(marker="orig-towers.archers.price.1")


async def test_shift_step_is_ten_times(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker=f"{PRICE1}-up").trigger("click", {"shiftKey": True})
    assert _val(user, PRICE1) == "80"
    user.find(marker=f"{PRICE1}-down").trigger("click", {"shiftKey": True})
    user.find(marker=f"{PRICE1}-down").trigger("click", {"shiftKey": True})
    assert _val(user, PRICE1) == "60"


async def test_step_uses_smallest_digit_of_original(user):
    await user.open("/")
    user.find("Heroes").click()
    user.find("Bolin").click()
    marker = "cell-heroes.hero_bolin.skill_c.boss_hp_percentage"  # original 0.002
    user.find(marker=f"{marker}-up").click()
    assert _val(user, marker) == "0.003"
    user.find(marker=f"{marker}-up").trigger("click", {"shiftKey": True})
    assert _val(user, marker) == "0.013"


async def test_arrow_keys_step_cell(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker=PRICE1).trigger("keydown.up.prevent", {"shiftKey": False})
    assert _val(user, PRICE1) == "71"
    user.find(marker=PRICE1).trigger("keydown.down.prevent", {"shiftKey": True})
    assert _val(user, PRICE1) == "61"


async def test_step_refreshes_row_pct_and_quick_scale(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker=f"{PRICE1}-up").click()
    assert _val(user, "row-pct-price") == "mixed"
    assert _val(user, "card-pct-all-costs") == "mixed"
    user.find(marker=f"{PRICE1}-down").click()
    assert _val(user, "row-pct-price") == "100%"
    assert _val(user, "card-pct-all-costs") == "100%"


async def test_step_stops_at_zero(user):
    await user.open("/")
    user.find("Alchemist").click()
    marker = "cell-towers.alchemist.ultimate.gold_pig.armor"  # original 0
    user.find(marker=f"{marker}-down").click()
    assert _val(user, marker) == "0"
    user.find(marker=f"{marker}-up").click()
    assert _val(user, marker) == "1"


async def test_step_commits_typed_text_first(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker=PRICE1).clear().type("200")
    user.find(marker=f"{PRICE1}-up").click()
    assert _val(user, PRICE1) == "201"


async def test_row_pct_typed_scales_row(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="row-pct-price").clear().type("50").trigger("keydown.enter")
    assert _val(user, PRICE1) == "35"
    assert _val(user, PRICE2) == "50"
    assert _val(user, "row-pct-price") == "50%"
    user.find(marker="row-pct-price").clear().type("150%").trigger("keydown.enter")
    assert _val(user, PRICE1) == "105"
    assert _val(user, "row-pct-price") == "150%"


async def test_row_pct_bad_text_reverts(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="row-pct-price").clear().type("abc").trigger("keydown.enter")
    await user.should_see("Not a number")
    assert _val(user, "row-pct-price") == "100%"
    assert _val(user, PRICE1) == "70"


async def test_row_pct_typed_value_clamps(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="row-pct-price").clear().type("900").trigger("keydown.enter")
    assert _val(user, "row-pct-price") == "500%"
    assert _val(user, PRICE1) == "350"


async def test_row_pct_steps_one_and_ten(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="row-pct-price-up").click()
    assert _val(user, "row-pct-price") == "101%"
    user.find(marker="row-pct-price-up").trigger("click", {"shiftKey": True})
    assert _val(user, "row-pct-price") == "111%"
    user.find(marker="row-pct-price-down").click()
    assert _val(user, "row-pct-price") == "110%"
    assert _val(user, PRICE1) == "77"


async def test_row_pct_mixed_steps_from_100(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker=PRICE1).clear().type("99").trigger("keydown.enter")
    assert _val(user, "row-pct-price") == "mixed"
    user.find(marker="row-pct-price-down").click()
    assert _val(user, "row-pct-price") != "mixed"
    assert _val(user, PRICE1) == "69"


async def test_quick_scale_box_typed_and_stepped(user):
    await user.open("/")
    user.find("Knights").click()
    user.find(marker="card-pct-all-costs").clear().type("50").trigger("keydown.enter")
    assert _val(user, "card-pct-all-costs") == "50%"
    assert [_val(user, f"cell-towers.knights.price.{i}") for i in (1, 2, 3, 4)] == ["35", "55", "80", "110"]
    user.find(marker="card-pct-all-costs-up").click()
    assert _val(user, "card-pct-all-costs") == "51%"
    assert _val(user, "row-pct-price") == "51%"
    user.find(marker="card-pct-all-costs").clear().type("0").trigger("keydown.enter")
    assert _val(user, "cell-towers.knights.price.1") == "0"
    user.find(marker="card-pct-all-costs").clear().type("500").trigger("keydown.enter")
    assert _val(user, "cell-towers.knights.price.1") == "350"


async def test_zero_original_leaves_at_zero(user):
    await user.open("/")
    user.find("Alchemist").click()
    p_str = "towers.alchemist.ultimate.gold_pig.armor"
    assert _val(user, f"cell-{p_str}") == "0"
    user.find(marker="row-pct-ultimate-gold_pig-armor").clear().type("500").trigger("keydown.enter")
    assert _val(user, f"cell-{p_str}") == "0"


async def test_sniper_card_opens_without_error(user):
    await user.open("/")
    user.find("Sniper").click()
    await user.should_see("Sniper")
    await user.should_see("Max range")
