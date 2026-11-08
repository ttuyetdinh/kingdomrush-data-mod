from krmod.app import LEAN_WEBVIEW_FLAGS, lean_webview_args


def test_lean_webview_args_keep_existing_arguments_once():
    debug = "--remote-debugging-port=9333"
    merged = lean_webview_args(debug)
    assert merged.split() == [debug, *LEAN_WEBVIEW_FLAGS]
    assert lean_webview_args(merged) == merged
    assert lean_webview_args("").split() == list(LEAN_WEBVIEW_FLAGS)
