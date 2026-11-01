# KrGenesis Mod

KrGenesis Mod is a desktop editor and live tuning tool for Kingdom Rush Genesis. It lets you customize unit balance values, tower progression rules, and real-time game multipliers, delivering your custom configurations via a safe Lua mod loader.

## Key Features

- Safe and non-invasive: The application never modifies Kingdom Rush Genesis.exe or any original game file. Launching the game normally always runs the unmodified vanilla game.
- Balance editing: Browse towers, troops, heroes, skills, enemies, items, and stages to adjust stats with automatic rounding and change tracking.
- Progression rules: Optionally unlock all tower upgrade levels from the start.
- Live speed hotkeys: Switch gameplay speed between x1, x2, and x3 using hotkeys F5, F6, and F7. When accelerated speed is active, an on-screen x2 or x3 badge appears during gameplay. Speed hotkeys can be customized in the Rules tab.
- Live unit multipliers: Adjust enemy count and troop count multipliers from 0.5x to 3.0x in 0.25 steps.
- Real-time vs level start timing: Live controls such as game speed, enemy multipliers, and troop multipliers update mid-level during active combat. Stat edits and tower unlock rules take effect at the next level start or stage restart.

## Profiles and Storage

All user configurations are stored locally inside the repository folder:

- Profiles are saved as JSON files in the profiles folder (such as profiles\default.json).
- The active profile is recorded in profiles\_active.json.
- Each profile stores only edited values relative to the original game balance.
- NiceGUI and webview storage are kept inside the cache folder, ensuring nothing is written to AppData or LocalAppData.

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

This compiles the app into dist\KrGenesisMod\KrGenesisMod.exe. The entire dist\KrGenesisMod folder, containing KrGenesisMod.exe alongside _internal and supporting data, must stay together and remain in place inside kingdomrush-data-mod. The executable relies on this relative location to discover the game installation, profiles, and local caches.

## Launching the Modded Game

You can apply changes and launch the game directly from the app interface using Apply mod and run game.

To launch the modded game independently without running the desktop app, execute the generated batch file in the game folder:

```bat
mods\launch_modded.bat
```

This runs Kingdom Rush Genesis with the modded balance override using the most recently applied settings. A standard game launch without this batch script remains completely vanilla.
