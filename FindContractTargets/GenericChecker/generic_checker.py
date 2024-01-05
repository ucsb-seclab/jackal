
import argparse

from generic_checker_plugin import GenericCheckerPlugin
from ethpwn import *
from myutils import *

#
# NOTE:
# 
# This script implements the GenericChecker as described in the paper in Section 4.3 (Generic Checker).
# To run the script like we did for our evaluation, an access to an blockchain index database is required
# (i.e., we need to enumerate the transactions sent by a confused contract to a target).
# However, because it is impractical to share such a database, we provide a simple test script that
# demonstrates the technique behind the GenericChecker.
# 
# This script takes as input:
#   1 - a confused contract (i.e., a contract for which a controllable CALL has been identified), 
#   2 - a candidate contract target (i.e., a contract that has been called by the confused contract and that can 
#     potentially hold a state for the confused contract.
#   3 - a transaction hash we want to test. This transaction should contain an internal transaction in which the 
#     confused contract calls the candidate contract target.
#   4 - the function signature of the function that has been called by the confused contract in the candidate contract target.
#       (this function should trigger SSTOREs to be a good candidate)
#
# As an example, you can try:
#  python test.py --confused 0x11b815efb8f581194ae79006d24e0d814b7697f6 --target 0xdAC17F958D2ee523a2206206994597C13D831ec7 --tx 0x15bef4b45379ad3dfa676f206c1ce0d9d4a18164d82a0d1a71737652c9456212 --func 0xa9059cbb
#

def main():

    arg_parser = argparse.ArgumentParser(description='generic_checker')
    arg_parser.add_argument('--confused', type=str, required=True)
    arg_parser.add_argument('--target', type=str, required=True)
    arg_parser.add_argument('--tx', type=str, required=True)
    arg_parser.add_argument('--func', type=str, required=True)

    args = arg_parser.parse_args()

    confused = normalize_contract_address(args.confused)
    target = normalize_contract_address(args.target)
    tx = args.tx
    func = args.func

    print(f'Running GenericChecker test...')
    print(f'  >Confused contract: {confused}\n  >Target contract: {target}\n  >Tx: {tx}\n  >Func: {func}')

    print(f'🧪 Test1: Collecting SSTOREs for {target} during {tx}.')

    a1 = get_evm_at_txn(tx)

    gcp = GenericCheckerPlugin(
                            confused_contract=0x11b815efb8f581194ae79006d24e0d814b7697f6,
                            candidate_target=0xdAC17F958D2ee523a2206206994597C13D831ec7,
                            candidate_target_func=0xa9059cbb
                            )
    a1.register_plugin(gcp)
    a1.next_transaction()
    sstores_report_original = a1.plugins.jackal_generic_checker.sstores_report
    print(f'  -> Observed {len(sstores_report_original)} SSTOREs')
    #for s in sstores_report_original:
    #    print(s)

    print(f'🧪 Test2: Collecting SSTOREs for {target} during {tx}. (Changing CALLER)')

    a2 = get_evm_at_txn(tx)
    gcp = GenericCheckerPlugin(
                            confused_contract=0x11b815efb8f581194ae79006d24e0d814b7697f6,
                            candidate_target=0xdAC17F958D2ee523a2206206994597C13D831ec7,
                            candidate_target_func=0xa9059cbb,
                            overwrite_caller=True
                            )
    a2.register_plugin(gcp)  
    a2.next_transaction()
    sstores_report_mod = a2.plugins.jackal_generic_checker.sstores_report
    print(f'  -> Observed {len(sstores_report_mod)} SSTOREs')
    #for s in sstores_report_mod:
    #    print(s)

    # Now, let's compare the reports, do we see any discrepancies in terms of
    # executed SSTOREs? If yes, it might be that the confused_contract is holding
    # some sort of "state" in the candidate_target
    sstores_pc_originals = [x.pc for x in sstores_report_original]
    sstores_pc_mods = [x.pc for x in sstores_report_mod]

    # if the number of SSTOREs is different, OR, we see SSTOREs in different PCs, we trigger a warning.
    if len(sstores_pc_originals) != len(sstores_pc_mods) or set(sstores_pc_originals) != set(sstores_pc_mods):
        print(f'>>>{bcolors.FAIL}Warning: SSTOREs are different!{bcolors.ENDC}<<<')
        # first, add None element to sstores_pc_mods if it has not the same length of sstores_pc_originals
        delta = len(sstores_pc_originals) - len(sstores_pc_mods)
        if delta > 0:
            sstores_pc_mods.extend([None]*delta)
        # now, let's zip the two lists and compare them
        # highlight the differences with colors
        print(f'{bcolors.FAIL}Original SSTORE(s){bcolors.ENDC} vs {bcolors.FAIL}Modified SSTORE(s){bcolors.ENDC}')
        for pc_original, pc_mod in zip(sstores_pc_originals, sstores_pc_mods):
            if pc_original != pc_mod:
                print(f"{bcolors.WARNING}pc: {pc_original} pc: {pc_mod}{bcolors.ENDC}")
            else:
                print(f"{bcolors.GREEN}pc: {pc_original} pc: {pc_mod}{bcolors.ENDC}")


if __name__ == '__main__':
    main()