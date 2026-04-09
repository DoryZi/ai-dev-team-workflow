# LRU Cache

## Task

Implement a Least Recently Used (LRU) Cache class that supports `get` and `put` operations with O(1) average time complexity.

## Requirements

Create a file named `solution.py` containing a class `LRUCache` with the following interface:

```python
class LRUCache:
    def __init__(self, capacity: int) -> None:
        """Initialize the LRU cache with a positive capacity.

        Args:
            capacity: Maximum number of key-value pairs the cache can hold.

        Raises:
            ValueError: If capacity is less than 1.
        """

    def get(self, key: int) -> int:
        """Return the value for the given key, or -1 if not found.

        Accessing a key marks it as most recently used.

        Args:
            key: The key to look up.

        Returns:
            The value associated with the key, or -1 if the key is not in the cache.
        """

    def put(self, key: int, value: int) -> None:
        """Insert or update a key-value pair.

        If the key already exists, update its value and mark it as most recently used.
        If the cache is at capacity, evict the least recently used item before inserting.

        Args:
            key: The key to insert or update.
            value: The value to associate with the key.
        """

    def __len__(self) -> int:
        """Return the current number of items in the cache."""

    def __contains__(self, key: int) -> bool:
        """Check if a key exists in the cache without affecting usage order."""
```

## Constraints

- Capacity must be a positive integer (>= 1).
- Keys and values are integers.
- `get` and `put` should run in O(1) average time.
- The cache must correctly track usage order: `get` and `put` both count as "using" a key.
- `__contains__` must NOT update the usage order.

## Edge Cases

- Cache with capacity 1.
- Updating an existing key's value.
- Eviction when cache is full.
- Getting a key that does not exist.
- Putting the same key multiple times.
