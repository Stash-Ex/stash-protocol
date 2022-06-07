import pytest
import asyncio
from starkware.starknet.testing.starknet import Starknet
from utils import Signer, chunks_to_str, uint, str_to_felt, MAX_UINT256, assert_revert, Stash, get_key_hash_chain

signer = Signer(123456789987654321)


@pytest.fixture(scope='session')
def event_loop():
    return asyncio.new_event_loop()


@pytest.fixture(scope='session')
async def account_token_factory():
    starknet = await Starknet.empty()
    account = await starknet.deploy(
        "contracts/Account.cairo",
        constructor_calldata=[signer.public_key]
    )

    erc20 = await starknet.deploy(
        "contracts/token/ERC20.cairo",
        constructor_calldata=[
            str_to_felt("Token"),      # name
            str_to_felt("TKN"),        # symbol
            *uint(10000),               # initial_supply
            account.contract_address   # recipient
        ]
    )

    return starknet, erc20, account


@pytest.fixture(scope='function')
async def stash_factory(account_token_factory):
    starknet, _, _ = account_token_factory
    stash = await starknet.deploy(
        "contracts/Stash.cairo",
        constructor_calldata=[]
    )

    return stash


@pytest.mark.asyncio
async def test_erc20_constructor(account_token_factory):
    _, erc20, account = account_token_factory
    execution_info = await erc20.balanceOf(account.contract_address).call()
    assert execution_info.result.balance == uint(10000)

    execution_info = await erc20.totalSupply().call()
    assert execution_info.result.totalSupply == uint(10000)


@pytest.mark.asyncio
async def test_createStashNoHint(account_token_factory, stash_factory):
    _, erc20, account = account_token_factory
    stash = stash_factory

    # approve contract stash contract address for transferFrom
    spender = stash.contract_address
    amount = uint(123)
    return_bool = await signer.send_transaction(account, erc20.contract_address, 'approve', [spender, *amount])
    assert return_bool.result.response == [1]

    # get previous balance to ensure transferFrom was successful
    execution_info = await erc20.balanceOf(stash.contract_address).call()
    previous_balance = execution_info.result.balance

    # createStash
    test_stash = Stash("location", erc20.contract_address,
                       amount, ['key1', 'key2', 'key3'])
    calldata = test_stash.get_createStash_calldata()
    return_bool = await signer.send_transaction(account, stash.contract_address, 'createStash', calldata)
    assert return_bool.result.response == [1]

    # check that transferFrom was successful
    execution_info = await erc20.balanceOf(stash.contract_address).call()
    assert execution_info.result.balance == amount

    # check that stash was created
    execution_info = await stash.getStash(str_to_felt(test_stash.location), 0).call()
    print(execution_info)
    starkStash = execution_info.result.stash
    assert starkStash.token == erc20.contract_address
    assert starkStash.amount == amount
    assert starkStash.key == test_stash.get_key_hash()
    assert starkStash.hint_id == 0
    assert starkStash.owner == account.contract_address
    assert starkStash.claimed == 0


@pytest.mark.asyncio
async def test_createStashWithLongHint(account_token_factory, stash_factory):
    _, erc20, account = account_token_factory
    stash = stash_factory

    # approve contract stash contract address for transferFrom
    spender = stash.contract_address
    amount = uint(123)
    return_bool = await signer.send_transaction(account, erc20.contract_address, 'approve', [spender, *amount])
    assert return_bool.result.response == [1]

    # get previous balance to ensure transferFrom was successful
    execution_info = await erc20.balanceOf(stash.contract_address).call()
    previous_balance = execution_info.result.balance

    # createStash
    hint = "".join(["hello world"]*20)
    test_stash = Stash("location", erc20.contract_address,
                       amount, ['key1', 'key2', 'key3'], hint)
    calldata = test_stash.get_createStash_calldata()
    return_bool = await signer.send_transaction(account, stash.contract_address, 'createStash', calldata)
    assert return_bool.result.response == [1]

    # check that transferFrom was successful
    execution_info = await erc20.balanceOf(stash.contract_address).call()
    assert execution_info.result.balance == amount

    # check that stash was created
    execution_info = await stash.getStash(str_to_felt(test_stash.location), 0).call()
    print(execution_info)
    (starkStash, stark_hint) = execution_info.result
    assert starkStash.token == erc20.contract_address
    assert starkStash.amount == amount
    assert starkStash.key == test_stash.get_key_hash()
    assert starkStash.hint_id == 1
    assert starkStash.owner == account.contract_address
    assert starkStash.claimed == 0
    assert hint == chunks_to_str(stark_hint)


@pytest.mark.asyncio
async def test_createMultipleStashesGetHint(account_token_factory, stash_factory):
    _, erc20, account = account_token_factory
    stash = stash_factory

    # approve contract stash contract address for transferFrom
    spender = stash.contract_address
    total_amount = uint(1000)
    return_bool = await signer.send_transaction(account, erc20.contract_address, 'approve', [spender, *total_amount])
    assert return_bool.result.response == [1]

    # get previous balance to ensure transferFrom was successful
    execution_info = await erc20.balanceOf(stash.contract_address).call()
    previous_balance = execution_info.result.balance

    amount = uint(100)
    keys = ['key1', 'key2', 'key3']
    for i in range(1, 11):
        # createStash
        hint = f"Stash #{i}"
        test_stash = Stash(f"location{i}", erc20.contract_address,
                           amount, keys, hint)
        calldata = test_stash.get_createStash_calldata()
        return_bool = await signer.send_transaction(account, stash.contract_address, 'createStash', calldata)
        assert return_bool.result.response == [1]

    # check that transferFrom was successful
    execution_info = await erc20.balanceOf(stash.contract_address).call()
    assert execution_info.result.balance == total_amount

    for i in range(1, 11):
        # check that stash was created
        execution_info = await stash.getStash(str_to_felt(f"location{i}"), 0).call()
        print(execution_info)
        (starkStash, stark_hint) = execution_info.result
        assert starkStash.token == erc20.contract_address
        assert starkStash.amount == amount
        assert starkStash.key == get_key_hash_chain(keys)
        assert starkStash.hint_id == i
        assert starkStash.owner == account.contract_address
        assert starkStash.claimed == 0
        assert chunks_to_str(stark_hint) == f"Stash #{i}"


@pytest.mark.asyncio
async def test_createStash_fail_no_approval(account_token_factory, stash_factory):
    _, erc20, account = account_token_factory
    stash = stash_factory

    amount = uint(123)
    # get previous balance to ensure transferFrom was successful
    execution_info = await erc20.balanceOf(stash.contract_address).call()
    previous_balance = execution_info.result.balance

    # createStash
    test_stash = Stash("location", erc20.contract_address,
                       amount, ['hello', 'world'])
    assert_revert(lambda: signer.send_transaction(account, stash.contract_address, 'createStash',
                                                  test_stash.get_createStash_calldata()))

    # check that no transfer of funds occurred
    execution_info = await erc20.balanceOf(stash.contract_address).call()
    assert execution_info.result.balance == uint(0)


@pytest.mark.asyncio
async def test_claimStash(account_token_factory, stash_factory):
    starknet, erc20, account = account_token_factory
    stash = stash_factory

    # approve stash contract address for transferFrom
    spender = stash.contract_address
    amount = uint(123)
    return_bool = await signer.send_transaction(account, erc20.contract_address, 'approve', [spender, *amount])
    assert return_bool.result.response == [1]

    # createStash
    keys = ['key1', 'key2', 'key3']
    test_stash = Stash("claimStashLocation",
                       erc20.contract_address, amount, keys)
    return_bool = await signer.send_transaction(account, stash.contract_address, 'createStash',
                                                test_stash.get_createStash_calldata())
    assert return_bool.result.response == [1]

    # test claimStash by another account
    signer2 = Signer(987654321123456789)
    account2 = await starknet.deploy(
        "contracts/Account.cairo",
        constructor_calldata=[signer2.public_key]
    )
    # get previous balance to ensure transferFrom was successful
    execution_info = await erc20.balanceOf(account2.contract_address).call()
    previous_balance = execution_info.result.balance

    claim_calldata = [str_to_felt(test_stash.location), 0,
                      len(keys), *test_stash.get_keys_as_felt()]
    return_bool = await signer2.send_transaction(account2, stash.contract_address,
                                                 'claimStash', claim_calldata)
    assert return_bool.result.response == [1]

    # confirm stash prize was transferred to claimer account
    execution_info = await erc20.balanceOf(account2.contract_address).call()
    assert execution_info.result.balance > previous_balance

    # check that stash is marked as claimed
    execution_info = await stash.getStash(str_to_felt(test_stash.location), 0).call()
    assert execution_info.result.stash.claimed == 1


@pytest.mark.asyncio
async def test_claimStash_fail_wrong_keys(account_token_factory, stash_factory):
    starknet, erc20, account = account_token_factory
    stash = stash_factory

    # approve stash contract address for transferFrom
    spender = stash.contract_address
    amount = uint(123)
    return_bool = await signer.send_transaction(account, erc20.contract_address, 'approve', [spender, *amount])
    assert return_bool.result.response == [1]

    # createStash
    keys = ['key1', 'key2', 'key3']
    test_stash = Stash("claimStashLocation",
                       erc20.contract_address, amount, keys)
    return_bool = await signer.send_transaction(account, stash.contract_address, 'createStash',
                                                test_stash.get_createStash_calldata())
    assert return_bool.result.response == [1]

    # test claimStash by another account
    signer2 = Signer(987654321123456789)
    account2 = await starknet.deploy(
        "contracts/Account.cairo",
        constructor_calldata=[signer2.public_key]
    )
    # get previous balance to ensure transferFrom was successful
    execution_info = await erc20.balanceOf(account2.contract_address).call()
    previous_balance = execution_info.result.balance

    claim_calldata = [str_to_felt(test_stash.location), 0,
                      1, str_to_felt('wrong key')]
    # attempt to claim stash with wrong key
    assert_revert(lambda: signer.send_transaction(account2, stash.contract_address,
                                                  'claimStash', claim_calldata))

    # make sure no funds were transferred
    execution_info = await erc20.balanceOf(account2.contract_address).call()
    assert execution_info.result.balance == previous_balance
