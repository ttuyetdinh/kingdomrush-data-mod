# KrGenesis Mod

KrGenesis Mod is a desktop editor and live tuning tool for Kingdom Rush Genesis. It lets you customize unit balance values, tower progression rules, and real-time game multipliers, delivering your custom configurations via a safe Lua mod loader.

> **Disclaimer:** This is an unofficial fan project made for personal fun and single-player play only. It is not affiliated with, endorsed by, or supported by Ironhide Game Studio, the makers of Kingdom Rush. Kingdom Rush and all game content belong to their owners. This repository contains no game files, art, or game code; you need your own copy of the game. Use it at your own risk: back up your save before trying it.

## Key Features

- Safe and non-invasive: The application never modifies Kingdom Rush Genesis.exe or any original game file. Launching the game normally always runs the unmodified vanilla game.
- Balance editing: Browse towers, troops, heroes, spells, enemies, items, and stages. Each value appears in one place: a tower's or hero's skills are part of its own card, below its own stats, under a Skills heading. Click a section title to fold or unfold its rows (the Skills heading folds all skill sections); folds are kept until the app closes. Type a value or use the up and down arrows (one step is the smallest digit of the game's value, Shift for ten steps). Row % and Quick scale boxes set a whole row or group to a percentage of the game's values (0% to 500%). When a row differs from the game, the struck 100% under its Row % box puts the whole row back.
- Game names and pictures: Cards use the names the game shows (Archer Garrison, Gemina, Gnome's Shop, J.T.), read from the game's own English text, and skill sections add the skill's name (Skill a: Spot Weakness). Search finds a card by its game name or its data name (archers). Pictures come from the game's own art for the same unit. Units the game gives no single name keep a plain description.
- All enemies: The first card in the Enemies tab scales every enemy and boss at once with All damage, All range, All cooldowns, All HP and All moving speed boxes. A box sets that kind of value on every enemy to a percentage of the game's value, replacing earlier edits of that kind; "mixed" means the enemies differ. All moving speed is also on every single unit card (enemies, heroes and soldiers). Under every Quick scale box, a struck 100% puts that group back to the game's values.
- Progression rules: Optionally unlock all tower upgrade levels inside every stage, and unlock all heroes, tower types and spells without collecting stars. Extra hero skill points, extra spell skill points and extra skill tree points (0 to 999) are added on top of the game's own points for every hero, every spell and the skill tree, so hero levels, spell levels and finished stages still count; the skill tree (Upgrades) costs 80 points in total, so 80 extra buys all of it from the start. The mod writes no progress, points or unlocks to your save: set a rule back and the game's own numbers return. (The game itself still clears the "new" badge of a hero, tower or spell you view.)
- Both skill paths: Optionally allow buying both sides wherever a hero, tower, spell or Upgrades skill tree splits in two, each side at its normal cost. Bought skills are saved by the game like any purchase: turning the rule off keeps them, and each tree's reset button clears them. Where the game itself treats a pair as one or the other, only one of them may work in a level.
- Live speed hotkeys: Switch gameplay speed between x1, x2, and x3 using hotkeys F5, F6, and F7. When accelerated speed is active, an on-screen x2 or x3 badge appears during gameplay. Speed hotkeys can be customized in the Rules tab.
- Live enemy and troop counts: Enemies multiplies regular enemies (0.25 for a quarter, or 1 to 100; Shift with the arrows jumps by tens; bosses always spawn). The extra copies of each enemy walk beside it in rows that fill every lane of the road (3 lanes on every KR6 road), one row every quarter of a second, so x30 adds about 2.5 seconds per enemy; high values still make long, crowded waves and can slow the game down. Troops adds or removes soldiers per barracks (-10 to +10; 0 is the default, and a large minus can leave a barracks empty).
- Real-time vs level start timing: Live controls such as game speed, enemy count, and troop count update mid-level during active combat. Stat edits and tower level unlocks take effect at the next level start or stage restart. Hero, tower and spell unlocks and extra points show the next time the map screen opens.
- Half-screen friendly: Below 1280 px wide the top bar uses two rows, and the card list can be folded to give the stat table more room.

## Profiles and Storage

All user configurations are stored locally inside the repository folder:

- Profiles are saved as JSON files in the profiles folder (such as profiles\default.json).
- The active profile is recorded in profiles\_active.json.
- Each profile stores only edited values relative to the original game balance.
- NiceGUI and webview storage are kept inside the cache folder, ensuring nothing is written to AppData or LocalAppData.

## Choosing the Game Folder

By default the app looks for the game in the folder that contains the app folder: the kingdomrush-data-mod folder when run from source, or the folder that holds KrGenesisMod.exe. To use another folder, click the folder icon in the top bar (the tooltip shows the current folder) and choose the folder that contains Kingdom Rush Genesis.exe and lua51.dll. If the game is not found at startup, the error page offers the same choice. Your profiles and changes are kept when you switch.

The choice is saved in settings.json inside the app folder, never in AppData. The game folder is picked in this order: the KRMOD_GAME_DIR environment variable (for development and tests), then the saved choice, then the default above. Delete settings.json to go back to the default. Only the mods folder of the chosen game folder is ever written.

Portrait images are cached per game folder under cache\portraits.

## First-Time Setup

To set up the development environment, create a virtual environment using 64-bit Python 3.12 and install the package with development dependencies in editable mode:

```bat
py -3.12-64 -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

## Running from Source

To run the application from source using the shared virtual environment:

```bat
.venv\Scripts\python.exe -m krmod
```

Alternatively, activate the environment first:

```bat
.venv\Scripts\activate
python -m krmod
```

## Packaging the Application

To build the standalone Windows executable:

```bat
scripts\build.bat
```

This builds one file, dist\KrGenesisMod.exe, with Python, the window library and the mod template inside it. To use it on any machine:

1. Make a folder inside the game folder, for example <game folder>\KrGenesisMod.
2. Copy KrGenesisMod.exe into it and double-click it.
3. To keep your edits, also copy your profiles folder next to the exe.

The exe keeps everything beside itself: profiles\, settings.json and cache\ (portraits, app.log, window storage). Each start it unpacks itself into a runtime\ folder in the folder it is started from (double-click or a shortcut: the exe's own folder), which takes a few seconds, and removes that copy when the window closes; a copy left in the exe's folder by a crash is removed at the next start. If the exe is not inside the game folder, choose the game folder with the folder icon.

The only other thing the machine needs is the Microsoft Edge WebView2 Runtime, which draws the window. It comes with Windows 11 and most Windows 10 installs; without it the window does not open (install it from Microsoft's WebView2 download page). Keep the exe in its own folder rather than directly in the game folder: the app writes its profiles, cache and runtime folders beside the exe, and the game folder itself should only ever get the mods folder.

## Launching the Modded Game

You can apply changes and launch the game directly from the app interface using Apply mod and run game.

To launch the modded game independently without running the desktop app, execute the generated batch file in the game folder:

```bat
mods\launch_modded.bat
```

This runs Kingdom Rush Genesis with the modded balance override using the most recently applied settings. A standard game launch without this batch script remains completely vanilla.

## License

The code in this repository is released under the MIT License below. The license covers only this project's own code; it grants no rights to Kingdom Rush or any of its content.

```text
MIT License

Copyright (c) 2026 ttuyetdinh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
