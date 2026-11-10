import sys
from pathlib import Path
_ROOT_DIR = str(Path(__file__).resolve().parent)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import demo.demo_worker
from demo.demo_worker import *
sys.modules['demo_worker'] = demo.demo_worker
if __name__ == '__main__':
    demo.demo_worker.main()
