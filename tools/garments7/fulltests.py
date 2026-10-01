"""the full test suite in this tree (for a box: `remote run script tools/garments7/fulltests.py`)."""
import subprocess, sys
sys.exit(subprocess.call([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'charkit/tests']))
