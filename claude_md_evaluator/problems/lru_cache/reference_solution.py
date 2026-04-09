"""Reference solution for the LRU Cache problem."""
from __future__ import annotations

from collections import OrderedDict


class LRUCache:
    """Least Recently Used cache with O(1) get and put operations.

    Uses an OrderedDict to maintain insertion/access order, with the
    least recently used item at the front and most recently used at the back.

    Attributes:
        capacity: Maximum number of items the cache can hold.
    """

    def __init__(self, capacity: int) -> None:
        """Initialize the LRU cache with a positive capacity.

        Args:
            capacity: Maximum number of key-value pairs the cache can hold.

        Raises:
            ValueError: If capacity is less than 1.
        """
        if capacity < 1:
            raise ValueError(f"Capacity must be >= 1, got {capacity}")
        self.capacity = capacity
        self._store: OrderedDict[int, int] = OrderedDict()

    def get(self, key: int) -> int:
        """Return the value for the given key, or -1 if not found.

        Accessing a key marks it as most recently used.

        Args:
            key: The key to look up.

        Returns:
            The value associated with the key, or -1 if the key is not in the cache.
        """
        if key not in self._store:
            return -1
        self._store.move_to_end(key)
        return self._store[key]

    def put(self, key: int, value: int) -> None:
        """Insert or update a key-value pair.

        If the key already exists, update its value and mark it as most recently used.
        If the cache is at capacity, evict the least recently used item before inserting.

        Args:
            key: The key to insert or update.
            value: The value to associate with the key.
        """
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = value
        else:
            if len(self._store) >= self.capacity:
                self._store.popitem(last=False)
            self._store[key] = value

    def __len__(self) -> int:
        """Return the current number of items in the cache."""
        return len(self._store)

    def __contains__(self, key: object) -> bool:
        """Check if a key exists in the cache without affecting usage order.

        Args:
            key: The key to check.

        Returns:
            True if the key exists in the cache.
        """
        return key in self._store
