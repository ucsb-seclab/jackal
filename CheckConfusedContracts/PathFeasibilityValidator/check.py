

import argparse

from ethpwn import *
from .check_plugin import CheckPlugin

'''
# e.g.,
# python check.py --target  <CHECKSUMMED_CONTRACT_ADDRESS> --block <BLOCK_NUMBER>
 --calldata 6dbf2fa000000000000000000000000080000000000000000000000000000000000000002f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f00000000000000000000000000000000000000000000000000000000000002002f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2
 --calltacid 0x1f7
'''
def main():
    arg_parser = argparse.ArgumentParser(description='path_feasibility_validator')
    arg_parser.add_argument('--target',   type=str, required=True)
    arg_parser.add_argument('--block',    type=int, required=True)
    arg_parser.add_argument('--calldata', type=str, required=True)
    arg_parser.add_argument('--calltacid', type=str, required=True)

    args = arg_parser.parse_args()

    target = normalize_contract_address(args.target)

    a1 = get_evm_at_block(args.block)

    cp = CheckPlugin(args.calltacid)
    a1.register_plugin(cp)

    wallet_conf = get_wallet(None)

    txn_data = dict()
    txn_data['sender'] = wallet_conf.address
    txn_data['to'] = target
    txn_data['calldata'] = args.calldata
    txn_data['wallet_conf'] = get_wallet(None)

    new_txn = a1.build_new_transaction(txn_data)

    rcpt, _ = a1.apply(new_txn)

    print(a1.plugins.jackal_pfv_checker.call_is_reachable)


def check_call_reachability(target:str, block:int, calldata:str, calltacid:str):

    target = normalize_contract_address(target)

    a1 = get_evm_at_block(block)

    cp = CheckPlugin(calltacid)
    a1.register_plugin(cp)

    txn_data = dict()
    txn_data['to'] = target
    txn_data['calldata'] = calldata

    new_txn = a1.build_new_transaction(txn_data)
    rcpt, _ = a1.apply(new_txn)
    #print(rcpt)

    return a1.plugins.jackal_pfv_checker.call_is_reachable


if __name__ == '__main__':
    main()
