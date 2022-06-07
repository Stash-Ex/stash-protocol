%lang starknet
%builtins pedersen range_check

from starkware.starknet.common.syscalls import get_caller_address, get_contract_address
from starkware.cairo.common.alloc import alloc
from starkware.cairo.common.cairo_builtins import HashBuiltin, SignatureBuiltin
from starkware.cairo.common.hash_chain import hash_chain
from starkware.cairo.common.memcpy import memcpy
from starkware.cairo.common.math import assert_not_zero, assert_not_equal, assert_nn
from starkware.cairo.common.math_cmp import is_not_zero
from starkware.cairo.common.uint256 import (
    Uint256, uint256_add, uint256_sub, uint256_le, uint256_lt, uint256_check)

@contract_interface
namespace IERC20:
    func transfer(recipient : felt, amount : Uint256) -> (success : felt):
    end

    func transferFrom(sender : felt, recipient : felt, amount : Uint256) -> (success : felt):
    end
end

#
# Structs
#

struct Stash:
    member token : felt
    member amount : Uint256
    member key : felt
    member hint_id : felt
    member owner : felt
    member claimed : felt
end

struct StashView:
    member token : felt
    member amount : Uint256
    member key : felt
    member hints_len : felt
    member hints : felt*
    member owner : felt
    member claimed : felt
end

#
# Storage
#

# Store a Stash struct given a location and id
@storage_var
func stashes(location : felt, id : felt) -> (stash : Stash):
end

# Store the number of stashes at a given location. Used to generate unique stash ids
@storage_var
func stashIds(location : felt) -> (len : felt):
end

# Store hint parts for a given stash.
# The first entry (index = 0) for a hint specifies the number of parts composing the entire hint.
# The complete hint can be retrieved by concatenating all of the hint parts.
# num_parts = hints[hint_id][0]
# hint = hints[hint_id][1] + hints[hint_id][2] + ... + hints[hint_id][num_parts]
@storage_var
func hints(hint_id : felt, index : felt) -> (hint : felt):
end

@storage_var
func latestHintId() -> (hint_id : felt):
end

@constructor
func constructor{}():
    return ()
end

# Create a stash.
# location: The location of the stash.
# token: The address of the asset in the stash.
# amount: The amount number of tokens in the stash.
# key: The key that will unlock the contents of stash.
#    This should be the result of chained hashing of array of [keys_len, keys...]
#    See: https://github.com/starkware-libs/cairo-lang/blob/fc97bdd8322a7df043c87c371634b26c15ed6cee/src/starkware/cairo/common/hash_chain.cairo#L8
# hint_parts_len: Number of short strings that make up the hint
# hint_parts: array of short strings that make up hint
@external
func createStash{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        location : felt, token : felt, amount : Uint256, key : felt, hint_parts_len : felt,
        hint_parts : felt*) -> (success : felt):
    alloc_locals

    assert_not_zero(token)
    assert_not_zero(key)
    assert_nn(hint_parts_len)

    let (local sender) = get_caller_address()
    let (this_address) = get_contract_address()

    # pull tokens from token address
    let (res) = IERC20.transferFrom(
        contract_address=token, sender=sender, recipient=this_address, amount=amount)
    assert_not_zero(res)

    let (stashId) = stashIds.read(location)

    let (hint_id) = _save_hint(hint_parts, hint_parts_len)

    let stash = Stash(token=token, amount=amount, key=key, hint_id=hint_id, owner=sender, claimed=0)
    stashes.write(location, stashId, stash)
    stashIds.write(location, stashId + 1)

    # Cairo equivalent to 'return (true)'
    return (1)
end

# Claim stash contents.
#
# This will compute the hash chain of all key elements prepended with number of keys.
# If the resulting hash matches the stash key the contents will be released to the caller
#
# Prepends the key array length such that hash_chain([keys_len, keys...])
# See: https://github.com/starkware-libs/cairo-lang/blob/fc97bdd8322a7df043c87c371634b26c15ed6cee/src/starkware/cairo/common/hash_chain.cairo#L8
#
# Params
# --------
# location: the location of the stash
# id: the id of the stash
# keys: array of keys that will be hashed to create unlock key
# key_count: length of keys array
@external
func claimStash{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        location : felt, id : felt, keys_len : felt, keys : felt*) -> (success : felt):
    alloc_locals

    let (stash : Stash) = stashes.read(location, id)

    # ensure stash was not already claimed
    assert_not_equal(stash.claimed, 1)

    # Copy keys with count to new array for chained hashing
    let (keysWithCount) = alloc()
    assert [keysWithCount] = keys_len
    memcpy(keysWithCount + 1, keys, keys_len)

    let (unlockKey : felt) = hash_chain{hash_ptr=pedersen_ptr}(keysWithCount)

    # Check that key hash is stash key
    assert unlockKey = stash.key

    # transfer contents to claimer
    let (sender) = get_caller_address()
    let (res) = IERC20.transfer(contract_address=stash.token, recipient=sender, amount=stash.amount)

    assert_not_zero(res)

    let newStash = Stash(
        token=stash.token,
        amount=stash.amount,
        key=stash.key,
        hint_id=stash.hint_id,
        owner=stash.owner,
        claimed=1)
    stashes.write(location, id, newStash)

    return (1)
end

@view
func stashesAtLocation{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        location : felt) -> (numStashes : felt):
    let (numStashes) = stashIds.read(location)
    return (numStashes=numStashes)
end

@view
func getStash{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        location : felt, stashId : felt) -> (stash : Stash, hint_len : felt, hint : felt*):
    alloc_locals
    let (local stash) = stashes.read(location, stashId)
    let (hint_len : felt, hint : felt*) = getHint(stash.hint_id)
    return (stash, hint_len, hint)
end

@view
func getHint{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(hint_id : felt) -> (
        hint_len : felt, hint : felt*):
    alloc_locals
    let (hint_len) = hints.read(hint_id, 0)
    let (local hint : felt*) = alloc()
    _build_hint(hint_id, hint, 1, hint_len)

    return (hint_len, hint)
end

func _build_hint{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        hint_id : felt, arr : felt*, index : felt, remaining : felt) -> ():
    if remaining == 0:
        return ()
    end

    let (hint) = hints.read(hint_id, index)
    assert [arr] = hint
    _build_hint(hint_id, arr + 1, index + 1, remaining - 1)
    return ()
end

func _save_hint{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        hint_parts : felt*, hint_parts_len : felt) -> (hint_id : felt):
    alloc_locals

    if hint_parts_len == 0:
        return (0)
    end

    let (local hint_id) = latestHintId.read()
    let hint_id = hint_id + 1

    hints.write(hint_id, 0, hint_parts_len)
    _save_hint_parts(hint_id, 1, hint_parts, hint_parts_len)

    latestHintId.write(hint_id)
    return (hint_id)
end

# Stores array of hints.
# Returns false if no hints were stored, 1 otherwise
func _save_hint_parts{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        hint_id : felt, index : felt, arr : felt*, remaining : felt) -> (has_hint : felt):
    if remaining == 0:
        return (0)
    end

    hints.write(hint_id, index, [arr])
    _save_hint_parts(hint_id, index + 1, arr + 1, remaining - 1)
    return (1)
end
