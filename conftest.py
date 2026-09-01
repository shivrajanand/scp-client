import sys
from pathlib import Path

# Ensure the project root is on sys.path so `import app...` works
# regardless of the directory pytest is invoked from.
sys.path.insert(0, str(Path(__file__).parent))
