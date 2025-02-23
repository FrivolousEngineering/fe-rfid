import time

import click

import rfid


def on_card_detected(name: str, card_id: str):
    pass


def on_card_lost(name: str, card_id: str):
    pass


def on_traits_detected(name: str, traits: list[str]):
    pass


def create_rfid(baud_rate: int, device_name: str):
    if device_name:
        device = rfid.RFIDDevice(
            port = device_name,
            baud_rate = baud_rate,
            on_card_detected_callback = on_card_detected,
            on_card_lost_callback = on_card_lost,
            traits_detected_callback = on_traits_detected,
        )
    else:
        controller = rfid.RFIDController()
        print("TODO")
        exit(1)

    return device


def write_traits(device: rfid.RFIDDevice, type: str, traits: list[str], timeout):
    while not device.ready:
        time.sleep(0.1)

    device.writeSample(type, traits)

    start = time.perf_counter()
    while device.writing and time.perf_counter() - start < timeout:
        time.sleep(0.1)


@click.group()
@click.option("--baud-rate", default = 115200, help ri= "The baud rate to use for communicating.")
@click.option("--device", default = "", help = "The device to communicate with. If unset, will scan for a device.")
@click.option("--timeout", default = 2, help = "Time to wait for device.")
@click.pass_context
def cli(context, baud_rate: int, device: str, timeout: float):
    context.ensure_object(dict)
    context.obj["baud_rate"] = baud_rate
    context.obj["device"] = device
    context.obj["timeout"] = timeout


@cli.command()
@click.pass_context
def read(context):
    device = create_rfid(context.obj.get("baud_rate"), context.obj.get("device"))

    while not device.ready:
        time.sleep(0.1)

    print("Waiting for tag on device", device.name)

    while device.card_id is None:
        time.sleep(0.1)

    print("Detected card", device.card_id)

    start = time.perf_counter()
    while device.traits is None and time.perf_counter() - start < context.obj["timeout"]:
        time.sleep(0.1)

    if device.traits:
        print("Read traits:")
        for trait in device.traits:
            print(f"- {trait}")
    else:
        print("No traits found. Tag empty?")


@cli.group()
def write():
    pass


@write.command()
@click.argument("positive_action", nargs = 1, required = True)
@click.argument("positive_target", nargs = 1, required = True)
@click.argument("negative_action", nargs = 1, required = True)
@click.argument("negative_target", nargs = 1, required = True)
@click.option("--depleted", default = False, help = "Whether the Raw sample should be marked as depleted.")
@click.pass_context
def raw(context, positive_action, positive_target, negative_action, negative_target, depleted):
    device = create_rfid(context.obj.get("baud_rate"), context.obj.get("device"))

    traits = [positive_action, positive_target, negative_action, negative_target]
    if depleted:
        traits.append("depleted")
    else:
        traits.append("active")

    write_traits(device, "raw", traits, context.obj["timeout"])


@write.command()
@click.argument("primary_action", nargs = 1, required = True)
@click.argument("primary_target", nargs = 1, required = True)
@click.argument("secondary_action", nargs = 1, required = True)
@click.argument("secondary_target", nargs = 1, required = True)
@click.argument("purity", nargs = 1, required = True)
@click.pass_context
def refined(context, primary_action, primary_target, secondary_action, secondary_target, purity):
    device = create_rfid(context.obj.get("baud_rate"), context.obj.get("device"))

    traits = [primary_action, primary_target, secondary_action, secondary_target, purity]

    write_traits(device, "refined", traits, context.obj["timeout"])


@write.command()
@click.argument("action", nargs = 1, required = True)
@click.argument("target", nargs = 1, required = True)
@click.argument("purity", nargs = 1, required = True)
@click.pass_context
def blood(context, action, target, purity):
    device = create_rfid(context.obj.get("baud_rate"), context.obj.get("device"))

    traits = [action, target, purity]

    write_traits(device, "blood", traits, context.obj["timeout"])


@cli.command()
@click.option("--set", default = "", help = "Set the name of the RFID reader to this value instead of reading it.")
@click.pass_context
def name(context, set: str):
    device = create_rfid(context.obj.get("baud_rate"), context.obj.get("device"))

    if not set:
        while not device.ready:
            time.sleep(0.1)
        print("Device name:", device.name)
    else:
        while not device.ready:
            time.sleep(0.1)
        device.set_name(set)


if __name__ == "__main__":
    cli()
