@echo off
cd /d "%~dp0.."
set "PATH=%CD%\.venv\Scripts;%PATH%"
.venv\Scripts\nicegui-pack --noconfirm --windowed --name KrGenesisMod --add-data "mod_template;mod_template" krmod\__main__.py
