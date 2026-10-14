from __future__ import annotations

from dataclasses import dataclass

from romwiki.engines.gen5.shared.script_disassembler import disassemble_function


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


_SHOP_SELECTOR_VARIABLE = 0x8000
_SHOP_MODE_VARIABLE = 0x8001
_SHOP_GLOBAL_SCRIPT_ID = 10110
STANDARD_SHOP_SELECTOR = 255


@dataclass(frozen=True, slots=True)
class Gen5ShopDispatch:
    selector_id: int
    mode: int
    command_offset: int


def parse_shop_dispatch(script: bytes, function_offset: int) -> Gen5ShopDispatch | None:
    """Decode a local function that invokes the global shop dispatcher."""
    selector_id = None
    mode = None
    for instruction in sorted(
        disassemble_function(script, function_offset).values(),
        key=lambda value: value.offset,
    ):
        if instruction.name in {"WorkSet", "WorkSetConst"}:
            variable, value = instruction.params
            if variable == _SHOP_SELECTOR_VARIABLE:
                selector_id = value
            elif variable == _SHOP_MODE_VARIABLE:
                mode = value
        elif (
            instruction.name == "RTCallGlobal"
            and instruction.params == (_SHOP_GLOBAL_SCRIPT_ID,)
            and selector_id is not None
            and mode is not None
        ):
            return Gen5ShopDispatch(
                selector_id=selector_id,
                mode=mode,
                command_offset=instruction.offset,
            )
    return None
