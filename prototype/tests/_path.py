"""테스트에서 상위 폴더 모듈을 import하기 위한 경로 설정."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
