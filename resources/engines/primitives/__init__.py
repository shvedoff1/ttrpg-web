"""
engines/primitives — Atomic building blocks for game engines.

Each primitive does exactly one thing (roll, sample, generate, etc.)
and can be composed into complex engines via CompositeEngine.
"""

from engines.primitives.registry import register, get_primitive, list_primitives


def register_all_primitives() -> None:
    """Register all available primitives. Call at app startup."""
    from engines.primitives.weighted_roll import WeightedRollPrimitive
    from engines.primitives.context_roll import ContextRollPrimitive
    from engines.primitives.weighted_sample import WeightedSamplePrimitive
    from engines.primitives.cascade_roll import CascadeRollPrimitive
    from engines.primitives.filtered_roll import FilteredRollPrimitive
    from engines.primitives.loot_bundle import LootBundlePrimitive
    from engines.primitives.pool_sample import PoolSamplePrimitive
    from engines.primitives.item_generator import ItemGeneratorPrimitive

    for cls in (
        WeightedRollPrimitive,
        ContextRollPrimitive,
        WeightedSamplePrimitive,
        CascadeRollPrimitive,
        FilteredRollPrimitive,
        LootBundlePrimitive,
        PoolSamplePrimitive,
        ItemGeneratorPrimitive,
    ):
        register(cls())
