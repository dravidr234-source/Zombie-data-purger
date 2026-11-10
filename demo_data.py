import sys
from pathlib import Path
_ROOT_DIR = str(Path(__file__).resolve().parent)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import demo.demo_data
from demo.demo_data import *
from demo.demo_data import create_safe_demo_environment, clean_safe_demo_environment
sys.modules['demo_data'] = demo.demo_data
