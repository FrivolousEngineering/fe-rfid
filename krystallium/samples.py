from enum import IntEnum, auto
import dataclasses
from typing import Self


class Action(IntEnum):
    Creating = auto()
    Destroying = auto()
    Increasing = auto()
    Decreasing = auto()
    Expanding = auto()
    Contracting = auto()
    Conducting = auto()
    Insulating = auto()
    Fortifying = auto()
    Deteriorating = auto()
    Absorbing = auto()
    Releasing = auto()
    Heating = auto()
    Cooling = auto()
    Lightening = auto()
    Encumbering = auto()
    Solidifying = auto()

    @classmethod
    def is_opposing(cls, first, second) -> bool:
        opposing = (
            (cls.Creating, cls.Destroying),
            (cls.Increasing, cls.Decreasing),
            (cls.Expanding, cls.Contracting),
            (cls.Conducting, cls.Insulating),
            (cls.Fortifying, cls.Deteriorating),
            (cls.Absorbing, cls.Releasing),
            (cls.Heating, cls.Cooling),
            (cls.Lightening, cls.Encumbering),
        )

        check_pair = (first, second)
        swapped_pair = (second, first)
        return any((i == check_pair or i == swapped_pair) for i in opposing)


class Target(IntEnum):
    Solid = auto()
    Liquid = auto()
    Gas = auto()
    Krystal = auto()
    Plant = auto()
    Energy = auto()
    Light = auto()
    Sound = auto()
    Flesh = auto()
    Mind = auto()

    @classmethod
    def is_opposing(cls, first, second) -> bool:
        opposing = (
            (Target.Mind, Target.Flesh),
            (Target.Flesh, Target.Plant),
            (Target.Gas, Target.Solid),
            (Target.Gas, Target.Liquid),
            (Target.Liquid, Target.Gas),
            (Target.Krystal, Target.Energy),
        )

        check_pair = (first, second)
        swapped_pair = (second, first)
        return any((i == check_pair or i == swapped_pair) for i in opposing)


class Vulgarity(IntEnum):
    Vulgar = auto()
    LowMundane = auto()
    HighMundane = auto()
    LowSemiPrecious = auto()
    HighSemiPrecious = auto()
    Precious = auto()

    @staticmethod
    def from_raw(positive_action: Action, positive_target: Target, negative_action: Action, negative_target: Target) -> Self:
        action_invariant = positive_action == negative_action
        target_invariant = positive_target == negative_target

        if action_invariant and target_invariant:
            return Vulgarity.Precious

        action_opposing = Action.is_opposing(positive_action, negative_action)
        target_opposing = Target.is_opposing(positive_target, negative_target)

        if action_invariant or target_invariant:
            if action_invariant:
                return Vulgarity.HighSemiPrecious if target_opposing else Vulgarity.LowSemiPrecious
            else:
                return Vulgarity.HighSemiPrecious if action_opposing else Vulgarity.LowSemiPrecious

        if action_opposing and target_opposing:
            return Vulgarity.HighMundane

        if action_opposing or target_opposing:
            return Vulgarity.LowMundane

        return Vulgarity.Vulgar


class Purity(IntEnum):
    Polluted = auto()
    Tarnished = auto()
    Dirty = auto()
    Blemished = auto()
    Impure = auto()
    Unblemished = auto()
    Lucid = auto()
    Stainless = auto()
    Pristine = auto()
    Immaculate = auto()
    Perfect = auto()


class Strength(IntEnum):
    Nothing = 0
    Weak = auto()
    Medium = auto()
    Strong = auto()
    Overbearing = auto()


@dataclasses.dataclass(kw_only = True, frozen = True)
class RawSample:
    positive_action: Action
    positive_target: Target
    negative_action: Action
    negative_target: Target
    vulgarity: Vulgarity
    origin: str = ""
    rarity: float = 0.0
    depleted: bool = False

    def __str__(self) -> str:
        return """Positive Action: {}
Positive Target: {}
Negative Action: {}
Negative Target: {}
Vulgarity: {}
Origin: {}
Rarity: {:.1f}
Depleted: {}""".format(
            self.positive_action.name,
            self.positive_target.name,
            self.negative_action.name,
            self.negative_target.name,
            f"{self.vulgarity.name} ({self.vulgarity.value})",
            self.origin,
            self.rarity,
            self.depleted
        )


@dataclasses.dataclass(kw_only = True, frozen = True)
class RefinedSample:
    primary_action: Action
    primary_target: Target
    secondary_action: Action
    secondary_target: Target
    purity: Purity
    origin: str = ""
    rarity: float = 0.0
    depleted: bool = False

    def __str__(self) -> str:
        return """Primary Action: {}
Primary Target: {}
Secondary Action: {}
Secondary Target: {}
Purity: {}
Origin: {}
Rarity: {:.1f}
Depleted: {}""".format(
            self.primary_action.name,
            self.primary_target.name,
            self.secondary_action.name,
            self.secondary_target.name,
            f"{self.purity.name} ({self.purity.value})",
            self.origin,
            self.rarity,
            self.depleted
        )

    @classmethod
    def from_raw(cls, first: RawSample, second: RawSample) -> Self:
        return RefinedSample(
            primary_action = second.positive_action,
            primary_target = first.positive_target,
            secondary_action = second.negative_action,
            secondary_target = first.negative_target,
            purity = Purity(first.vulgarity + second.vulgarity),
            origin = f"{first.origin} {second.origin}",
            rarity = (first.rarity + second.rarity) / 2.0,
        )


@dataclasses.dataclass(kw_only = True, frozen = True)
class BloodSample:
    action: Action
    target: Target
    strength: Strength
    origin: str

    def __str__(self):
        return """Action: {}
Target: {}
Strength: {}
Origin: {}""".format(
            self.action.name,
            self.target.name,
            f"{self.strength.name} ({self.strength.value})",
            self.origin,
        )
