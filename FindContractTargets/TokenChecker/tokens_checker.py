#!/usr/bin/env python3

import sys
import time
import requests
import argparse

from myutils import *
from ethpwn import *

# The minimal value considered to raise a warning
MIN_USD_VAL = 100.0 

def check_balance(token_contract, confused_contract, block_ref):
    contract = context.w3.eth.contract(token_contract.contract_address, 
                            abi='[{"constant":true,"inputs":[{"name":"who","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]')

    token_balance = 0
    attempt = 0
    max_attempts = 5
    while True:
        try:
            token_balance = contract.functions.balanceOf(confused_contract).call(block_identifier=block_ref)
            break
        except Exception as e:
            #print(e)
            attempt += 1 
            if attempt == max_attempts:
                break
            time.sleep(1)

    if token_balance != 0:
        token_balance_usd = get_val_in_usd(token_contract.contract_address,
                                            token_contract.decimals,
                                            token_balance,
                                            block_ref)
        
        if token_balance_usd != 'NIL' and token_balance_usd >= MIN_USD_VAL:
            print(f'{bcolors.WARNING}💰 Balance of {token_balance / (10**token_contract.decimals) } {token_contract.name} for {confused_contract} (${token_balance_usd}){bcolors.ENDC}')

class ERC20Token:
    def __init__(self, contract_address, name, symbol, decimals):
        self.contract_address = contract_address
        self.name = name
        self.symbol = symbol
        self.decimals = decimals

'''
This script implements the Token Checker as presented in the paper in Section 4.3 (Token Checker).
The scripts takes as an input the address of a confused contract (--ca) and check within a range 
of blocks if there was any transfer of "interesting" tokens (in tokens.csv) to the confused contract.
We automatically discard whatever is less than 100$ value.

The value of the tokens are checked at the time of the transfer (querying uniswap and sushiswap)

e.g., 
   python tokens_checker.py --ca 0x2057CfB9fD11837D61B294D514C5bd03e5E7189A --block-start 14104827
'''
if __name__ == '__main__':

    arg_parser = argparse.ArgumentParser(description='TokenChecker')

    # The address of the confused contract
    arg_parser.add_argument('--ca', type=str, required=True)
    # The block to start the analysis from
    arg_parser.add_argument('--block-start', type=int, required=True)
    # The block to end the analysis to
    arg_parser.add_argument('--block-end', type=int)
    
    args = arg_parser.parse_args()

    contract_addr = args.ca
    contract_addr = context.w3.to_checksum_address(contract_addr)
    
    block_start = args.block_start

    if args.block_end == None:
        block_end = context.w3.eth.get_block("latest")["number"]
    else:
        block_end = args.block_end

    print(f"<<<Scanning from block {block_start} to block {block_end}>>>")

    # Load tokens.
    with open("./tokens.csv", "r") as f:
        all_tokens = f.read().splitlines()

    all_tokens = {x.split(",")[1]:ERC20Token(x.split(",")[1], x.split(",")[2], x.split(",")[3], int(x.split(",")[4])) for x in all_tokens}
    print(f'Loaded {len(all_tokens)} tokens')
        
    for block_ref in range(block_start, block_end):
        print(f'Checking block {block_ref}...')
        block_logs = context.w3.eth.get_logs({'fromBlock': block_ref, 'toBlock':block_ref+1})
        
        for log in block_logs:
            # ERC20 Transfer
            try:
                if log['topics'][0].hex() == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                    # Is the transfer directed to a confused contract?
                    to_addr = context.w3.to_checksum_address(log['topics'][2].hex()[26:])
                    if to_addr == contract_addr:
                        token_addr = log['address']
                        if token_addr in all_tokens.keys():
                            # Ok, let's check if the balance is different from 0 at this block (tokens didn't leave the contract in the same block)
                            check_balance(all_tokens[token_addr], contract_addr, block_ref)
                # WETH WIthdrawal
                elif log['topics'][0].hex() == '0x7fcf532c15f0a6db0bd6d0e038bea71d30d808c7d98cb3bf7268a95bf5081b65':
                    to_addr = context.w3.to_checksum_address(log['topics'][1].hex()[26:])
                    if to_addr == contract_addr:
                        token_addr = log['address']
                        if token_addr in all_tokens.keys():
                            check_balance(all_tokens[token_addr], contract_addr, block_ref)
            except Exception as e:
                print(e)
                continue

        
