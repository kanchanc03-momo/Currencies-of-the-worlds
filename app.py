"""Launch the active Currency Atlas application from final/."""
from pathlib import Path
import runpy
import sys

app_dir = Path(__file__).resolve().parent / "final"
sys.path.insert(0, str(app_dir))
runpy.run_path(str(app_dir / "app.py"), run_name="__main__")
