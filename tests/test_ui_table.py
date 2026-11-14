"""User simulation tests for the level table: cell boxes, Row % boxes and quick scale boxes."""
from nicegui import ui
import pytest

def _box(user, marker):
    return list(user.find(marker=marker).elements)[0]


def _step(user, marker, direction, shift=False):
    user.find(marker=marker).trigger("step", {"direction": direction, "shiftKey": shift})


def _commit(user, marker, text):
    user.find(marker=marker).clear().type(text).trigger("commit")


async def test_type_value_marks_changed(user):
    await user.open("/")
    user.find("Archers").click()
    _commit(user, "cell-towers.archers.price.1", "7")
    box = _box(user, "cell-towers.archers.price.1")
    assert box.props.get("original") == "70"  # original 70 shown
    assert box.props.get("tone") == "changed"


async def test_bad_text_reverts(user):
    await user.open("/")
    user.find("Archers").click()
    _commit(user, "cell-towers.archers.price.1", "abc")
    await user.should_see("Not a number")
    c = _box(user, "cell-towers.archers.price.1")
    assert c.value == "70"
    assert c.props.get("original") is None
    assert c.props.get("tone") is None


async def test_enum_read_only(user):
    await user.open("/")
    user.find("Enemies").click()
    user.find("Demon lord").click()
    await user.should_see("Physical")
    await user.should_not_see(marker="cell-enemies.demons.demon_lord.basic_attack.damage_type")


async def test_reset_cell_reverts_value(user):
    await user.open("/")
    user.find("Archers").click()
    _commit(user, "cell-towers.archers.price.1", "7")
    assert _box(user, "cell-towers.archers.price.1").props.get("original") == "70"
    # Reset this cell:
    user.find(marker="cell-towers.archers.price.1").trigger("reset")
    box = _box(user, "cell-towers.archers.price.1")
    assert box.props.get("original") is None
    assert box.props.get("tone") is None
    assert box.value == "70"


async def test_warning_shown_for_negative(user):
    await user.open("/")
    user.find("Archers").click()
    _commit(user, "cell-towers.archers.price.1", "-10")
    assert _box(user, "cell-towers.archers.price.1").props.get("warning") == "Negative values can break the game."


async def test_warning_not_duplicated(user):
    await user.open("/")
    user.find("Archers").click()
    _commit(user, "cell-towers.archers.price.1", "-10")
    _commit(user, "cell-towers.archers.price.1", "-20")
    box = _box(user, "cell-towers.archers.price.1")
    assert box.props.get("warning") == "Negative values can break the game."
    assert len(list(box.default_slot.children)) == 0

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
    titles = [e.props.get("title") for e in user._gather_elements(None, ui.label, None, None)]
    assert "skill_c.s_cd_mult" in titles
    assert "skill_c.cd_mult" in titles
    assert "price" in titles

async def test_precision_formatting(user):
    await user.open("/")
    user.find("Heroes").click()
    user.find("Bolin").click()
    # heroes.hero_bolin.skill_c.boss_hp_percentage has original 0.002
    await user.should_see("0.002")
    assert _val(user, "cell-heroes.hero_bolin.skill_c.boss_hp_percentage") == "0.002"


def _val(user, marker):
    return _box(user, marker).value


PRICE1 = "cell-towers.archers.price.1"  # original 70
PRICE2 = "cell-towers.archers.price.2"  # original 100


async def test_step_up_down_saves_and_marks_changed(user):
    await user.open("/")
    user.find("Archers").click()
    _step(user, PRICE1, 1)
    assert _val(user, PRICE1) == "71"
    assert _box(user, PRICE1).props.get("original") == "70"
    _step(user, PRICE1, -1)
    _step(user, PRICE1, -1)
    assert _val(user, PRICE1) == "69"
    _step(user, PRICE1, 1)
    assert _val(user, PRICE1) == "70"
    assert _box(user, PRICE1).props.get("original") is None


async def test_shift_step_is_ten_times(user):
    await user.open("/")
    user.find("Archers").click()
    _step(user, PRICE1, 1, True)
    assert _val(user, PRICE1) == "80"
    _step(user, PRICE1, -1, True)
    _step(user, PRICE1, -1, True)
    assert _val(user, PRICE1) == "60"


async def test_step_uses_smallest_digit_of_original(user):
    await user.open("/")
    user.find("Heroes").click()
    user.find("Bolin").click()
    marker = "cell-heroes.hero_bolin.skill_c.boss_hp_percentage"  # original 0.002
    _step(user, marker, 1)
    assert _val(user, marker) == "0.003"
    _step(user, marker, 1, True)
    assert _val(user, marker) == "0.013"


async def test_step_event_steps_cell(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker=PRICE1).trigger("step", {"direction": 1, "shiftKey": False})
    assert _val(user, PRICE1) == "71"
    user.find(marker=PRICE1).trigger("step", {"direction": -1, "shiftKey": True})
    assert _val(user, PRICE1) == "61"


async def test_step_refreshes_row_pct_and_quick_scale(user):
    await user.open("/")
    user.find("Archers").click()
    _step(user, PRICE1, 1)
    assert _val(user, "row-pct-price") == "mixed"
    assert _val(user, "card-pct-all-costs") == "mixed"
    assert _box(user, "row-pct-price").props.get("tone") == "mixed"
    assert _box(user, "card-pct-all-costs").props.get("tone") == "mixed"
    _step(user, PRICE1, -1)
    assert _val(user, "row-pct-price") == "100%"
    assert _val(user, "card-pct-all-costs") == "100%"
    assert _box(user, "row-pct-price").props.get("tone") is None
    assert _box(user, "card-pct-all-costs").props.get("tone") is None


async def test_step_stops_at_zero(user):
    await user.open("/")
    user.find("Alchemist").click()
    marker = "cell-towers.alchemist.ultimate.gold_pig.armor"  # original 0
    _step(user, marker, -1)
    assert _val(user, marker) == "0"
    _step(user, marker, 1)
    assert _val(user, marker) == "1"


async def test_step_commits_typed_text_first(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker=PRICE1).clear().type("200")
    _step(user, PRICE1, 1)
    assert _val(user, PRICE1) == "201"


async def test_row_pct_typed_scales_row(user):
    await user.open("/")
    user.find("Archers").click()
    _commit(user, "row-pct-price", "50")
    assert _val(user, PRICE1) == "35"
    assert _val(user, PRICE2) == "50"
    assert _val(user, "row-pct-price") == "50%"
    assert _box(user, "row-pct-price").props.get("tone") == "pct-changed"
    _commit(user, "row-pct-price", "150%")
    assert _val(user, PRICE1) == "105"
    assert _val(user, "row-pct-price") == "150%"


async def test_row_pct_bad_text_reverts(user):
    await user.open("/")
    user.find("Archers").click()
    _commit(user, "row-pct-price", "abc")
    await user.should_see("Not a number")
    assert _val(user, "row-pct-price") == "100%"
    assert _val(user, PRICE1) == "70"


async def test_row_pct_typed_value_clamps(user):
    await user.open("/")
    user.find("Archers").click()
    _commit(user, "row-pct-price", "900")
    assert _val(user, "row-pct-price") == "500%"
    assert _val(user, PRICE1) == "350"


async def test_row_pct_steps_one_and_ten(user):
    await user.open("/")
    user.find("Archers").click()
    _step(user, "row-pct-price", 1)
    assert _val(user, "row-pct-price") == "101%"
    _step(user, "row-pct-price", 1, True)
    assert _val(user, "row-pct-price") == "111%"
    _step(user, "row-pct-price", -1)
    assert _val(user, "row-pct-price") == "110%"
    assert _val(user, PRICE1) == "77"


async def test_row_pct_mixed_steps_from_100(user):
    await user.open("/")
    user.find("Archers").click()
    _commit(user, PRICE1, "99")
    assert _val(user, "row-pct-price") == "mixed"
    _step(user, "row-pct-price", -1)
    assert _val(user, "row-pct-price") != "mixed"
    assert _val(user, PRICE1) == "69"


async def test_quick_scale_box_typed_and_stepped(user):
    await user.open("/")
    user.find("Knights").click()
    _commit(user, "card-pct-all-costs", "50")
    assert _val(user, "card-pct-all-costs") == "50%"
    assert [_val(user, f"cell-towers.knights.price.{i}") for i in (1, 2, 3, 4)] == ["35", "55", "80", "110"]
    _step(user, "card-pct-all-costs", 1)
    assert _val(user, "card-pct-all-costs") == "51%"
    assert _val(user, "row-pct-price") == "51%"
    _commit(user, "card-pct-all-costs", "0")
    assert _val(user, "cell-towers.knights.price.1") == "0"
    _commit(user, "card-pct-all-costs", "500")
    assert _val(user, "cell-towers.knights.price.1") == "350"


async def test_row_without_nonzero_originals_has_no_pct_box(user):
    await user.open("/")
    user.find("Alchemist").click()
    assert _val(user, "cell-towers.alchemist.ultimate.gold_pig.armor") == "0"
    await user.should_not_see(marker="row-pct-ultimate-gold_pig-armor")


async def test_sniper_card_opens_without_error(user):
    await user.open("/")
    user.find("Sniper").click()
    await user.should_see("Sniper")
    await user.should_see("Max range")


BASIC = "cell-towers.archers.basic_attack.cooldown.1"
SKILL = "cell-towers.archers.skill_a.damage_max.1"


async def test_row_pct_undo_restores_the_whole_row(user):
    await user.open("/")
    user.find("Archers").click()
    assert _box(user, "row-pct-price").props.get("original") is None
    _commit(user, PRICE2, "5")  # one typed cell is enough to offer the undo
    assert _box(user, "row-pct-price").props.get("original") == "100%"
    _commit(user, "row-pct-price", "50")
    user.find(marker="row-pct-price").trigger("reset")
    assert (_val(user, PRICE1), _val(user, PRICE2)) == ("70", "100")
    assert _box(user, PRICE2).props.get("original") is None
    pct = _box(user, "row-pct-price")
    assert (pct.value, pct.props.get("original"), pct.props.get("tone")) == ("100%", None, None)


async def test_section_title_folds_its_rows(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="section-basic_attack").click()
    await user.should_not_see(marker=BASIC)
    await user.should_see(marker=SKILL)
    await user.should_see(marker=PRICE1)  # rows without a section stay
    user.find(marker="section-basic_attack").click()
    await user.should_see(marker=BASIC)


async def test_skills_heading_folds_every_skill_section(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="skills-heading").click()
    await user.should_not_see(marker=SKILL)
    await user.should_not_see(marker="section-skill_a")
    await user.should_see(marker=BASIC)
    user.find(marker="skills-heading").click()
    await user.should_see(marker=SKILL)


async def test_folds_are_kept_when_switching_cards(user):
    await user.open("/")
    user.find("Archers").click()
    user.find(marker="section-basic_attack").click()
    user.find("Knights").click()
    await user.should_see(marker="cell-towers.knights.price.1")
    user.find("Archers").click()
    await user.should_not_see(marker=BASIC)
