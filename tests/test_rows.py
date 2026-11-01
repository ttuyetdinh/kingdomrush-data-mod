from krmod.model.grouping import GroupIndex
from krmod.model.rows import build_rows, friendly_label


def _rows(tree, card_id):
    idx = GroupIndex.build(tree)
    card = idx.card(card_id)
    return build_rows(card, idx.paths_of(card.id), tree)


def test_price_row(tree):
    rows = {r.id: r for r in _rows(tree, "towers/archers")}
    price = rows["price"]
    assert price.cells[0] == ("towers", "archers", "price", 1) and price.label == "Price"
    assert price.group == "" and not price.read_only and not price.is_enum
    assert all(c is not None for c in price.cells)
    assert [c[-1] for c in price.cells] == list(range(1, len(price.cells) + 1))


def test_hero_bars_label(tree):
    idx = GroupIndex.build(tree)
    card = idx.card("heroes/hero_bolin")
    assert any(r.group == "Hero screen bars" for r in build_rows(card, idx.paths_of(card.id), tree))


def test_group_sort_and_enum_rows(tree):
    rows = _rows(tree, "towers/archers")
    groups = [r.group for r in rows]
    assert groups == sorted(groups, key=lambda g: (g != "", g))
    enums = [r for r in rows if r.is_enum]
    assert enums and all(r.read_only for r in enums)
    nested = {r.id: r for r in rows}["basic_attack.damage_min"]
    assert nested.group == "basic_attack" and nested.label == "Damage (min)"


def test_every_leaf_in_exactly_one_row(tree):
    idx = GroupIndex.build(tree)
    for card_id in ("towers/archers", "heroes/hero_bolin", "skills/powers/aspect_of_sol",
                    "enemies/demons/demon_lord", "other/Stages", "stages/towers/stage_07_barn"):
        try:
            card = idx.card(card_id)
        except KeyError:
            continue
        paths = idx.paths_of(card_id)
        rows = build_rows(card, paths, tree)
        cells = [c for r in rows for c in r.cells if c is not None]
        assert sorted(cells, key=str) == sorted(paths, key=str)
        assert len({r.id for r in rows}) == len(rows)


def test_foreign_upgrade_paths_get_their_own_group(tree):
    rows = _rows(tree, "skills/powers/aspect_of_sol")
    assert any(r.group.startswith("upgrades") for r in rows)


def test_string_rows_are_read_only(tree):
    idx = GroupIndex.build(tree)
    strs = [p for p, leaf in tree.leaves.items() if leaf.kind != "num"]
    assert strs
    seen = 0
    for p in strs:
        card = idx.placement(p).home
        for r in build_rows(card, idx.paths_of(card.id), tree):
            if p in r.cells:
                assert r.read_only
                seen += 1
    assert seen >= len(strs)


def test_friendly_label():
    assert friendly_label("damage_min") == "Damage (min)" and friendly_label("hp_max") == "HP (max)"
    assert friendly_label("hp") == "HP" and friendly_label("s_damage") == "Damage"
    assert friendly_label("regen_hp") == "Regen HP" and friendly_label("price") == "Price"
    assert friendly_label("min_hp_max") == "Min HP (max)"
