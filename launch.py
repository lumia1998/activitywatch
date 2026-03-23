import sys
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(base_dir, 'aw-pywebview'))
sys.path.insert(0, os.path.join(base_dir, 'aw-core'))
sys.path.insert(0, os.path.join(base_dir, 'aw-client'))
sys.path.insert(0, os.path.join(base_dir, 'aw-server'))
sys.path.insert(0, os.path.join(base_dir, 'aw-watcher-afk'))
sys.path.insert(0, os.path.join(base_dir, 'aw-watcher-window'))
sys.path.insert(0, os.path.join(base_dir, 'aw-watcher-input'))

from aw_pywebview import main
main()
