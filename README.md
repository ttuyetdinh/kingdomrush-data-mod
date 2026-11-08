# KrGenesis Mod

KrGenesis Mod is a desktop editor and live tuning tool for Kingdom Rush Genesis. It lets you customize unit balance values, tower progression rules, and real-time game multipliers, delivering your custom configurations via a safe Lua mod loader.

## Key Features

- Safe and non-invasive: The application never modifies Kingdom Rush Genesis.exe or any original game file. Launching the game normally always runs the unmodified vanilla game.
- Balance editing: Browse towers, troops, heroes, skills, enemies, items, and stages. Type a value or use the up and down arrows (one step is the smallest digit of the game's value, Shift for ten steps). Row % and Quick scale boxes set a whole row or group to a percentage of the game's values (0% to 500%).
- Progression rules: Optionally unlock all tower upgrade levels from the start.
- Live speed hotkeys: Switch gameplay speed between x1, x2, and x3 using hotkeys F5, F6, and F7. When accelerated speed is active, an on-screen x2 or x3 badge appears during gameplay. Speed hotkeys can be customized in the Rules tab.
- Live enemy and troop counts: Enemies multiplies regular enemies (0.25 for a quarter, or 1 to 10; bosses always spawn). Troops adds or removes soldiers per barracks (-10 to +10; 0 is the default, and a large minus can leave a barracks empty).
- Real-time vs level start timing: Live controls such as game speed, enemy count, and troop count update mid-level during active combat. Stat edits and tower unlock rules take effect at the next level start or stage restart.
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

## Launching the Modded Game

You can apply changes and launch the game directly from the app interface using Apply mod and run game.

To launch the modded game independently without running the desktop app, execute the generated batch file in the game folder:

```bat
mods\launch_modded.bat
```

This runs Kingdom Rush Genesis with the modded balance override using the most recently applied settings. A standard game launch without this batch script remains completely vanilla.
