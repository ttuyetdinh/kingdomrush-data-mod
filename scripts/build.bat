@echo off
rem Builds dist\KrGenesisMod.exe: one file that carries Python, NiceGUI and the mod template.
rem At start it unpacks itself into a "runtime" folder next to the exe (never into AppData)
rem and removes that copy again when it closes.
cd /d "%~dp0.."
set "PATH=%CD%\.venv\Scripts;%PATH%"
for /f "delims=" %%i in ('.venv\Scripts\python.exe -c "import nicegui, os; print(os.path.dirname(nicegui.__file__))"') do set "NICEGUI_DIR=%%i"
.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name KrGenesisMod ^
  --runtime-tmpdir runtime ^
  --add-data "%NICEGUI_DIR%;nicegui" ^
  --add-data "mod_template;mod_template" ^
  --add-data "krmod\ui\spinbox.js;krmod\ui" ^
  krmod\__main__.py
