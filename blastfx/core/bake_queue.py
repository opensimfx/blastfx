"""Pure FIFO queue for sequential batch bakes.

Kept bpy-free so it can be unit-tested outside Blender; bake_job owns the
instance and drives it from the single-bake machinery.
"""


class BakeQueue:
    """Ordered, de-duplicated blast ids waiting for a bake."""

    def __init__(self):
        self._ids = []

    def enqueue(self, blast_id):
        if not blast_id or blast_id in self._ids:
            return False
        self._ids.append(blast_id)
        return True

    def dequeue(self):
        return self._ids.pop(0) if self._ids else None

    def clear(self):
        count = len(self._ids)
        self._ids.clear()
        return count

    def pending(self):
        return tuple(self._ids)

    def position(self, blast_id):
        """1-based queue position, None if not queued."""
        try:
            return self._ids.index(blast_id) + 1
        except ValueError:
            return None

    def __len__(self):
        return len(self._ids)
