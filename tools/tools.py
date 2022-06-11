from typing import List
import click


from starkware.cairo.lang.vm.crypto import pedersen_hash
from starkware.cairo.common.hash_chain import compute_hash_chain


def str_to_felt(text):
    if len(text) > 31:
        raise Exception("string cannot be longer than 31 characters!")

    b_text = bytes(text, 'UTF-8')
    return int.from_bytes(b_text, "big")


@click.command()
@click.argument('keys', nargs=-1)
def calc_key_hash(keys):
    felt_keys = [str_to_felt(k) for k in keys]
    click.echo(compute_hash_chain([len(keys)] + felt_keys))


@click.command()
@click.argument('text', nargs=1)
def to_felt(text):
    click.echo(str_to_felt(text))


@click.command()
@click.argument('text', nargs=1)
def make_hint(text):
    chunks = [str(str_to_felt(text[i:i + 31]))
              for i in range(0, len(text), 31)]
    click.echo(" ".join(chunks))


@click.group()
def cli():
    """ CLI """
    pass


if __name__ == "__main__":
    cli.add_command(calc_key_hash)
    cli.add_command(to_felt)
    cli.add_command(make_hint)
    cli()

    # nile invoke cache createCache 1 999 999 [HASH_CHAIN] [FELT_HINT]
    # nile invoke cache claimCache 1 0 3 [FELT_KEYS]
