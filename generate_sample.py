import dataclasses
import random

import click

from krystallium.samples import Action, Target, Vulgarity, Strength, RawSample, RefinedSample, BloodSample

weights = {
    "common": 1.0,
    "uncommon": 0.25,
    "rare": 0.05,
}

raw_data = {
    "1": {
        "actions": {
            "common": [
                Action.Creating,
                Action.Encumbering,
            ],
            "uncommon": [
                Action.Heating,
                Action.Insulating,
                Action.Solidifying,
            ],
            "rare": [
                # Action.Increasing,
                # Action.Decreasing,
                # Action.Absorbing,
                # Action.Releasing,
            ],
            # "never": [
            #     Action.Destroying,
            #     Action.Conducting,
            # ]
        },
        "targets": {
            "common": [
                Target.Krystal
            ],
            "uncommon": [
                Target.Energy,
                Target.Solid,
            ],
            "rare": [
                # Target.Flesh,
                # Target.Mind,
            ]
        }
    },
    "2": {},
    "3": {},
    "4": {},
    "5": {
        "actions": {
            "common": [
                Action.Contracting,
            ],
            "uncommon": [
                Action.Fortifying,
                Action.Lightening,
            ],
            "rare": [
            ],
        },
        "targets": {
            "common": [
                Target.Liquid,
            ],
            "uncommon": [
                Target.Light,
            ],
            "rare": [
            ],
        }
    },
}


blood_data = {
    "water": {
        "actions": {
            "common": [
                Action.Increasing,
            ],
            "uncommon": [],
            "rare": [],
        },
        "targets": {
            "common": [
                Target.Krystal,
            ],
            "uncommon": [],
            "rare": [],
        }
    },
    "mountain": {

    },
    "forest": {
    },
    "plains": {
    }
}


@dataclasses.dataclass(kw_only = True, frozen = True)
class GenerateResult:
    action: Action
    target: Target
    rarity: float


def generate(origin):
    actions = []
    action_weights = []
    targets = []
    target_weights = []
    for rarity in ("common", "uncommon", "rare"):
        for action in origin["actions"][rarity]:
            actions.append(action)
            action_weights.append(weights[rarity])

        for target in origin["targets"][rarity]:
            targets.append(target)
            target_weights.append(weights[rarity])

    action = random.choices(actions, action_weights)[0]
    target = random.choices(targets, target_weights)[0]
    return GenerateResult(
        action = action,
        target = target,
        rarity = 2 / (action_weights[actions.index(action)] + target_weights[targets.index(target)])
    )


def generate_raw(origin):
    positive = generate(raw_data[origin.lower()])
    negative = generate(raw_data[origin.lower()])

    return RawSample(
        positive_action=positive.action,
        positive_target=positive.target,
        negative_action=negative.action,
        negative_target=negative.target,
        vulgarity=Vulgarity.from_raw(positive.action, positive.target, negative.action, negative.target),
        origin = origin,
        rarity = (positive.rarity + negative.rarity) / 2.0,
    )

@click.group()
def cli():
    pass


@cli.command(short_help = "Generate a raw sample")
@click.argument("origin", nargs = 1, required = True)
def raw(origin):
    sample = generate_raw(origin)
    print(str(sample))


@cli.command(short_help = "Generate a refined sample")
@click.argument("origins", nargs = 2, required = True)
def refined(origins):
    sample = RefinedSample.from_raw(generate_raw(origins[0]), generate_raw(origins[1]))
    print(str(sample))


@cli.command(short_help = "Generate a blood sample")
@click.argument("origin", nargs = 1, required = True)
def blood(origin):
    pair = generate(blood_data[origin.lower()])
    sample = BloodSample(
        action = pair.action,
        target = pair.target,
        strength = Strength(random.randint(1, 4)),
        origin = origin
    )
    print(str(sample))


if __name__ == "__main__":
    cli()
