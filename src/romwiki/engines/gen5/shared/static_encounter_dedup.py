from __future__ import annotations

from romwiki.engines.gen5.shared.script_disassembler import Gen5Instruction

# Shared by BW and B2W2's own `discover_static_encounters`. A static-encounter
# "fact" is a plain `(species_id, level, is_egg)` tuple, paired with the
# script member and the literal instruction that produced it.
#
# Deduplication must key on (fact, member), not on the fact alone: the same
# species+level combination is a real, coincidental collision between two
# genuinely distinct encounters in more than one place in these games (found
# and verified against real ROM data -- BW1's own N's Castle story
# confrontation and Dragonspiral Tower's actual legendary catch both call
# `CallWildBattle` with the *same* species and level, at two different script
# members owned by two different map headers). A fact-only dedup silently
# drops every occurrence after the first one found, which is exactly why B2W2
# was already written with the member-aware version below; BW1 previously had
# its own, simpler fact-only dedup that this module replaces.

_Fact = tuple[int, int | None, bool]
_Candidate = tuple[_Fact, int, Gen5Instruction]


def deduplicate_wild_paths(candidates: list[_Candidate]) -> list[_Candidate]:
    """Collapse lifecycle alternatives without losing distinct encounters."""
    by_species_and_member: dict[tuple[int, int], list[_Candidate]] = {}
    for candidate in candidates:
        by_species_and_member.setdefault((candidate[0][0], candidate[1]), []).append(
            candidate
        )

    initial_paths = []
    for paths in by_species_and_member.values():
        # A one-time legendary can have initial and postgame levels in the same
        # script. They are mutually exclusive lifecycle paths, not two catches.
        initial_paths.append(min(paths, key=lambda value: value[0][1] or 0))
    return deduplicate_exact_paths(initial_paths)


def deduplicate_exact_paths(candidates: list[_Candidate]) -> list[_Candidate]:
    kept = []
    seen_member_facts: set[tuple[_Fact, int]] = set()
    seen_command_paths: set[tuple[_Fact, int, str, tuple[int, ...]]] = set()
    for candidate in candidates:
        fact, member, instruction = candidate
        member_fact = fact, member
        command_path = fact, instruction.offset, instruction.name, instruction.params
        if (
            member_fact not in seen_member_facts
            and command_path not in seen_command_paths
        ):
            kept.append(candidate)
            seen_member_facts.add(member_fact)
            seen_command_paths.add(command_path)
    return kept


__all__ = ["deduplicate_exact_paths", "deduplicate_wild_paths"]
