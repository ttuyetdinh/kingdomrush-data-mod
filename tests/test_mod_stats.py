BAL = "BAL = { towers = { archers = { price = { 70, 110 } } } }"


def test_patch_then_restore(harness):
    harness.lua(BAL)
    harness.write_data([(("towers", "archers", "price", 1), 7)])
    harness.run_level()
    assert harness.lua("return BAL.towers.archers.price[1]") == "7"
    assert "applied 1 changes" in harness.log()
    assert harness.lua('return tostring(package.loaded["data.balance.balance"] == BAL)') == "true"
    harness.write_data([])
    harness.run_level()
    assert harness.lua("return BAL.towers.archers.price[1]") == "70"


def test_missing_path_logged_not_created(harness):
    harness.lua(BAL)
    harness.write_data([(("towers", "nope", "price", 1), 7)])
    harness.run_level()
    assert "missing towers.nope.price.1" in harness.log()
    assert harness.lua("return tostring(BAL.towers.nope)") == "nil"


def test_no_balance_local_is_safe(harness):
    harness.lua(BAL)
    harness.write_data([])
    harness.run_level("nil")
    assert "error balance local not found" in harness.log()
    assert harness.lua("return tostring(RESULT)") == "true"


def test_bad_data_file_is_safe(harness):
    harness.lua(BAL)
    harness.write_raw("kr_mod_data.lua", "return {")
    harness.run_level()
    assert "error data" in harness.log()
    assert harness.lua("return tostring(RESULT)") == "true"


def test_log_truncated_at_each_level_start(harness):
    harness.lua(BAL)
    harness.write_data([(("towers", "archers", "price", 1), 7)])
    harness.run_level()
    harness.run_level()
    assert harness.log().count("applied 1 changes") == 1


def test_non_numeric_target_not_overwritten(harness):
    harness.lua('BAL = { towers = { name = "x", t = { 1 } } }')
    harness.write_data([(("towers", "name"), 5), (("towers", "t"), 5)])
    harness.run_level()
    assert harness.lua("return BAL.towers.name") == "x"
    assert harness.lua("return type(BAL.towers.t)") == "table"
    assert "missing towers.name" in harness.log() and "missing towers.t" in harness.log()
    assert "applied 0 changes" in harness.log()


def test_originals_recorded_once_across_repeated_changes(harness):
    harness.lua(BAL)
    harness.write_data([(("towers", "archers", "price", 1), 7), (("towers", "archers", "price", 1), 9)])
    harness.run_level()
    harness.write_data([])
    harness.run_level()
    assert harness.lua("return BAL.towers.archers.price[1]") == "70"
