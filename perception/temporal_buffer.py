from collections import defaultdict, deque
from typing import List

class TemporalTextBuffer:
    def __init__(self, window_size: int = 3):
        self.window_size = window_size
        self.frames = deque(maxlen=window_size)

    def add_frame(self, lines: List[str]):
        """Add a frame of detected text lines."""
        # Clean lines to ensure better matching? User said "Feed it only viewport-isolated OCR text".
        # Assuming lines are raw OCR lines from the viewport.
        # We store as set to ignore duplicates within the same frame (spatial redundancy)
        # though duplicates in one frame are rare for OCR unless same text appears twice.
        self.frames.append(set(lines))

    def get_stable_text(self, min_persistence: int = 2) -> List[str]:
        """Get text lines that appear in at least min_persistence frames."""
        frequency = defaultdict(int)

        for frame in self.frames:
            for line in frame:
                frequency[line] += 1

        # User requirement: "Return [line for line, count in frequency.items() if count >= min_persistence]"
        # We should preserve some order if possible, but sets destroy order.
        # However, the user provided exact implementation using dictionary iteration order (Python 3.7+ preserves insertion).
        # But 'frequency' is built from iterating frames. Order depends on the first frame where line appeared.
        return [
            line for line, count in frequency.items()
            if count >= min_persistence
        ]
