pyinstaller --noconfirm --onefile --windowed --name "Fractal Explorer" --clean --add-data "../shaders;shaders/" --paths "../venv/Lib/site-packages" --hidden-import "glcontext"  "../main.py"