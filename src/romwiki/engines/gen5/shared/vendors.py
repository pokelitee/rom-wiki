from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Gen5SpecialVendorItem:
    """An item whose price and optional availability come from an engine rule."""

    item_id: int
    price: int
    availability: str | None = None


@dataclass(frozen=True, slots=True)
class Gen5SpecialVendor:
    """A non-mart vendor selected by the shared Gen V shop dispatcher."""

    selector_id: int | None
    name: str
    kind: str
    currency: str
    items: tuple[Gen5SpecialVendorItem, ...] = ()
    dynamic: bool = False
    availability: str | None = None
    is_main_game: bool | None = None
    vendor_id: str | None = None
    selector_ids: tuple[int, ...] = ()


def fixed_vendor_items(
    items: tuple[tuple[int, int], ...],
) -> tuple[Gen5SpecialVendorItem, ...]:
    return tuple(
        Gen5SpecialVendorItem(item_id=item_id, price=price) for item_id, price in items
    )
