"""Tests for the LRU Cache problem."""
from __future__ import annotations

import pytest

from solution import LRUCache


class TestLRUCacheInit:
    """Tests for LRU cache initialization."""

    def test_create_cache_with_valid_capacity(self) -> None:
        cache = LRUCache(3)
        assert cache.capacity == 3
        assert len(cache) == 0

    def test_create_cache_with_capacity_one(self) -> None:
        cache = LRUCache(1)
        assert cache.capacity == 1

    def test_create_cache_with_zero_capacity_raises(self) -> None:
        with pytest.raises(ValueError):
            LRUCache(0)

    def test_create_cache_with_negative_capacity_raises(self) -> None:
        with pytest.raises(ValueError):
            LRUCache(-5)


class TestLRUCacheGetPut:
    """Tests for get and put operations."""

    def test_put_and_get_single_item(self) -> None:
        cache = LRUCache(2)
        cache.put(1, 100)
        assert cache.get(1) == 100

    def test_get_missing_key_returns_negative_one(self) -> None:
        cache = LRUCache(2)
        assert cache.get(99) == -1

    def test_put_updates_existing_key(self) -> None:
        cache = LRUCache(2)
        cache.put(1, 100)
        cache.put(1, 200)
        assert cache.get(1) == 200
        assert len(cache) == 1

    def test_eviction_removes_least_recently_used(self) -> None:
        cache = LRUCache(2)
        cache.put(1, 10)
        cache.put(2, 20)
        cache.put(3, 30)  # Should evict key 1
        assert cache.get(1) == -1
        assert cache.get(2) == 20
        assert cache.get(3) == 30

    def test_get_updates_usage_order(self) -> None:
        cache = LRUCache(2)
        cache.put(1, 10)
        cache.put(2, 20)
        cache.get(1)  # Key 1 is now most recently used
        cache.put(3, 30)  # Should evict key 2, not key 1
        assert cache.get(1) == 10
        assert cache.get(2) == -1
        assert cache.get(3) == 30

    def test_put_existing_key_updates_usage_order(self) -> None:
        cache = LRUCache(2)
        cache.put(1, 10)
        cache.put(2, 20)
        cache.put(1, 100)  # Update key 1 — now most recently used
        cache.put(3, 30)  # Should evict key 2
        assert cache.get(1) == 100
        assert cache.get(2) == -1
        assert cache.get(3) == 30


class TestLRUCacheCapacityOne:
    """Tests for cache with capacity of 1."""

    def test_single_item_operations(self) -> None:
        cache = LRUCache(1)
        cache.put(1, 10)
        assert cache.get(1) == 10
        cache.put(2, 20)  # Evicts key 1
        assert cache.get(1) == -1
        assert cache.get(2) == 20

    def test_overwrite_single_item(self) -> None:
        cache = LRUCache(1)
        cache.put(1, 10)
        cache.put(1, 20)
        assert cache.get(1) == 20
        assert len(cache) == 1


class TestLRUCacheContains:
    """Tests for the __contains__ protocol."""

    def test_contains_existing_key(self) -> None:
        cache = LRUCache(2)
        cache.put(1, 10)
        assert 1 in cache

    def test_contains_missing_key(self) -> None:
        cache = LRUCache(2)
        assert 99 not in cache

    def test_contains_does_not_update_usage_order(self) -> None:
        cache = LRUCache(2)
        cache.put(1, 10)
        cache.put(2, 20)
        _ = 1 in cache  # Should NOT update usage order
        cache.put(3, 30)  # Should evict key 1 (still the LRU)
        assert cache.get(1) == -1
        assert cache.get(2) == 20


class TestLRUCacheLen:
    """Tests for __len__."""

    def test_len_empty_cache(self) -> None:
        cache = LRUCache(5)
        assert len(cache) == 0

    def test_len_after_inserts(self) -> None:
        cache = LRUCache(5)
        cache.put(1, 10)
        cache.put(2, 20)
        assert len(cache) == 2

    def test_len_does_not_exceed_capacity(self) -> None:
        cache = LRUCache(2)
        cache.put(1, 10)
        cache.put(2, 20)
        cache.put(3, 30)
        assert len(cache) == 2
