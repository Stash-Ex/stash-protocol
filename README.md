# Stash

## Overview

Stash is a blockchain protocol that lets anyone lock and hide digital assets  (stashes) on any website ~~or any location for that matter~~, permissionlessly and without the need for 3rd parties. Stashes can later be claimed, and the contents released, by providing the correct set of keys or other requirements. The first use case for this protocol will be a browser extension which helps users create and discover caches as they browse the internet, enabling new methods for users to engage with content creator, brands, and each other. 

With the ever growing popularity of the metaverse and digitial property rights enabled by blockchain, there arises a need to be able to interact with the metaverse in a similar manner to the "real world". The Stash protocol aims to create a flexible mechanism for attaching digital assets to a "location" in the metaverse, allowing for new interactions between users, apps, and any web3 connected technology.    

### Inspiration

This protocol was inspired by [GeoCaching](https://www.geocaching.com/play). From scavenger hunts to log books, we envision Stash becoming an open protocol that creates new ways for people to interact with one another and engage with content across the internet and time. 

## Details

### **Stash**

Stashes are made up of four components:

1. **ID** - This is the identifier for a cache and is composed of two things: 
    1. **Location** - Any text set by the creator of the cache. Can be website url, image link, GPS coordinates or anything else to provide context. Can also be used when claiming as describe in **[Cache Modes](https://www.notion.so/Stash-e93bf5a1c5814a1d96b51f1b803344c4)** below. 
    2. **Cache Number** - Auto-incremented number to uniquely identify caches in same location.   
2. **Contents** - The crypto assets locked in the cache at time of creation. Can be added to by anyone, anytime after creation.
3. **Keys** (optional) - Set by the creator of the cache. Hash of messages that will release contents when claiming the cache. Scavenger will provide the smart contract with pre-image of the keys which the smart contract will hash, compare for equality to cache keys and release contents on match.
4. **Hints** (optional) - Plaintext messages to help user find the keys. Set by creator at time of cache creation. Can be updated by creator at any time.



# Prep Env
Install [Nile](https://github.com/OpenZeppelin/nile)

# Compile
Compile all contracts under contracts directory  
`nile compile`  

# Test
Optional - Run all tests under tests directory  
`pytest`

# Deploy
Run the local dev node  
`nile node`

Copy the private key from .env file and `export PKEY=1234`
   
```
nile setup PKEY1
nile compile contracts/Stash.cairo
nile deploy Stash --alias stash
```

## Optional - Deploy token for testing
Compile and deploy ERC20 with name Token, symbol TKN and initial supply of 1000 going to first local address.  
Convert the strings to felts using the python tool. 
```
nile compile contracts/token/IERC20.cairo
nile compile contracts/token/ERC20.cairo

TOKEN=$(python tools/tools.py to-felt Token)
SYMBOL=$(python tools/tools.py to-felt TKN)
LOCAL_ACCOUNT=$(cat 127.0.0.1.accounts.json | jq -c 'first(.[].address)' | xargs)

nile deploy ERC20 --alias erc20 $TOKEN $SYMBOL 1000 0 $LOCAL_ACCOUNT
```

# Create a stash.
Assuming you deployed the token for testing.

1. Approve the stash protocol as a spender for your stash.  
Use python to convert the hex address to a number otherwise nile complains  
`nile send PKEY1 erc20 approve $(grep Stash.json 127.0.0.1.deployments.txt | cut -d : -f 1 | python -c "print(int(input(), 16))") 100 0`  
2. Confirm transaction succeeded.  
`nile debug <TRANSACTION HASH>`  
1. Create a stash
```
# nile invoke stash createStash [location, token, amount low, amount high, key, hint]
LOCATION=1
AMOUNT_LOW=100
AMOUNT_HIGH=0
ERC20_ADDRESS=$(grep erc20 127.0.0.1.deployments.txt | cut -d : -f 1 | python -c "print(int(input(), 16))")
KEY=$(python tools/tools.py calc-key-hash hello world)
HINT_LEN=1
HINT=$(python tools/tools.py to-felt "the answer is hello world") # Hint must be split into chunks of 31 characters!!

nile send PKEY1 stash createStash $LOCATION $ERC20_ADDRESS $AMOUNT_LOW $AMOUNT_HIGH $KEY $HINT_LEN $HINT
```
4. Confirm transaction was accepted
`nile debug <TRANSACTION_HASH>`
5. Confirm stash protocol has your funds
`nile call erc20 balanceOf $(grep Stash.json 127.0.0.1.deployments.txt | cut -d : -f 1 | python -c "print(int(input(), 16))")`
6. Take a look at the stash and verify some data.  
The stash will have id #0.  
`nile call stash getStash $LOCATION 0`  
This returns stash data [token, amount low, amount high, key, hint, owner, claimed]
   - the token and acccout addresses in `127.0.0.1.deployements.txt` should be the same as the erc20 and owner respectively.
   - the amount, hey, and hint should all be the same
   - claimed will be 0 as it is unclaimed 


# Claim a Stash
Set up a new account and claim the tokens in the stash.
```
export PKEY2=5678  
nile setup PKEY2

LOCAL_ACCOUNT_2=$(cat 127.0.0.1.accounts.json | jq -c 'nth(1; .[].address)' | xargs)
```

Claim the stash with the new account
```
NUM_KEYS=2
KEY1=$(python tools/tools.py to-felt hello)
KEY2=$(python tools/tools.py to-felt world)
nile send PKEY2 stash claimStash $LOCATION 0 $NUM_KEYS $KEY1 $KEY2
```

Confirm transaction succeeded
`nile debug <TRANSACTION_HASH>`

Check tokens were transferred to local account 2
`nile call erc20 balanceOf $LOCAL_ACCOUNT_2`

Check stash has status claimed (last return data = 1)
`nile call stash getStash $LOCATION 0`

# Alpha network deployment (goerli)

Convenient to track transaction status: https://alpha4.starknet.io/feeder_gateway/get_transaction_receipt?transactionHash=

1. Deploy PKEY1 and PKEY2
```
nile setup PKEY1 --network goerli
nile setup PKEY2 --network goerli
```
