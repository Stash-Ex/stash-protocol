"""Utilities for testing Cairo contracts."""

from starkware.cairo.common.hash_state import compute_hash_on_elements
from starkware.crypto.signature.signature import private_to_stark_key, sign
from starkware.starknet.definitions.error_codes import StarknetErrorCode
from starkware.starkware_utils.error_handling import StarkException
from starkware.starknet.public.abi import get_selector_from_name
from starkware.cairo.common.hash_chain import compute_hash_chain

MAX_UINT256 = (2**128 - 1, 2**128 - 1)


def get_key_hash_chain(keys):
    felt_keys = [str_to_felt(k) for k in keys]
    return compute_hash_chain([len(keys)] + felt_keys)


def str_to_felt(text):
    b_text = bytes(text, 'UTF-8')
    return int.from_bytes(b_text, "big")


def felt_to_str(felt: int) -> bytes:
    return felt.to_bytes((felt.bit_length() + 7) // 8, 'big').decode()


def str_to_chunks(text):
    return [str_to_felt(text[i:i + 31]) for i in range(0, len(text), 31)]


def chunks_to_str(chunks):
    return "".join([felt_to_str(chunk) for chunk in chunks])


def uint(a):
    return(a, 0)


async def assert_revert(fun):
    try:
        await fun
        assert False
    except StarkException as err:
        _, error = err.args
        assert error['code'] == StarknetErrorCode.TRANSACTION_FAILED


class Signer():
    """
    Utility for sending signed transactions to an Account on Starknet.

    Parameters
    ----------

    private_key : int

    Examples
    ---------
    Constructing a Singer object

    >>> signer = Signer(1234)

    Sending a transaction

    >>> await signer.send_transaction(account, 
                                      account.contract_address, 
                                      'set_public_key', 
                                      [other.public_key]
                                     )

    """

    def __init__(self, private_key):
        self.private_key = private_key
        self.public_key = private_to_stark_key(private_key)

    def sign(self, message_hash):
        return sign(msg_hash=message_hash, priv_key=self.private_key)

    async def send_transaction(self, account, to, selector_name, calldata, nonce=None):
        if nonce is None:
            execution_info = await account.get_nonce().call()
            nonce, = execution_info.result

        selector = get_selector_from_name(selector_name)
        message_hash = hash_message(
            account.contract_address, to, selector, calldata, nonce)
        sig_r, sig_s = self.sign(message_hash)

        return await account.execute(to, selector, calldata, nonce).invoke(signature=[sig_r, sig_s])


class Stash():
    def __init__(self, location, token, amount, keys, hint=""):
        self.location = location
        self.token = token
        self.amount = amount
        self.keys = keys
        self.hint = hint

    def get_createStash_calldata(self):
        hint_chunks = str_to_chunks(self.hint)
        return [str_to_felt(self.location), self.token, *(self.amount),
                get_key_hash_chain(self.keys), len(hint_chunks), *hint_chunks]

    def get_keys_as_felt(self):
        return [str_to_felt(k) for k in self.keys]

    def get_key_hash(self):
        return get_key_hash_chain(self.keys)


def hash_message(sender, to, selector, calldata, nonce):
    message = [
        sender,
        to,
        selector,
        compute_hash_on_elements(calldata),
        nonce
    ]
    return compute_hash_on_elements(message)
