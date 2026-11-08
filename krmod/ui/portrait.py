"""Portrait images served from one static route per portrait folder."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from nicegui import app, ui

_SERVED: dict[Path, str] = {}


def portrait_src(path: Path) -> str:
    """URL of a portrait file; each portrait folder gets one static route the first time.

    ui.image with a local path registers a new file route per call, so every tab switch and
    card open churned routes and re-downloaded the images.
    """
    folder = path.parent.resolve()
    url = _SERVED.get(folder)
    if url is None:
        url = f"/kr-portraits/{len(_SERVED)}"
        app.add_static_files(url, folder)
        _SERVED[folder] = url
    return f"{url}/{quote(path.name)}"


def portrait_img(path: Path, classes: str, *, lazy: bool = False) -> ui.element:
    """A plain <img> for a portrait file (lighter than a Quasar image)."""
    img = ui.element("img").classes(classes)
    img._props.update({"src": portrait_src(path), "alt": ""})
    if lazy:
        img._props["loading"] = "lazy"
    return img
