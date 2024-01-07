import web3
import subprocess
import os
import sys
import datetime
import json
import logging
import time
import shutil
import argparse

from greed import Project
from greed import options

from myglobals import *
from myutils import *
from inspect_call import inspect_call

from PathFeasibilityValidator import check_call_reachability

LOGGING_FORMAT = "%(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
log = logging.getLogger("hakcess_worker")
log.setLevel(logging.INFO)

class CallAnalysis():
    def __init__(self, call_id, contract_addr, call_type, call_tac_id, function_tac_id):
        self.call_id = call_id
        self.contract_addr = contract_addr
        self.call_type = call_type
        self.entry_point = ''
        self.function_tac_id = function_tac_id
        self.call_tac_id = call_tac_id
        self.classification = ''
        self.classification_type = ''
        self.contract_target = ''
        self.function_sig_target = ''
        self.result = ''
        self.calldata = ''
        self.calldata_size = 0
        self.analysis_time = 0

    def to_dict(self):
        return {
            'call_id': self.call_id,
            'contract_addr': self.contract_addr,
            'call_type': self.call_type,
            'entry_point': self.entry_point,
            'function_tac_id': self.function_tac_id,
            'call_tac_id': self.call_tac_id,
            'classification': self.classification,
            'classification_type': self.classification_type,
            'contract_target': self.contract_target,
            'function_sig_target': self.function_sig_target,
            'result': self.result,
            'calldata': self.calldata,
            'calldata_size': self.calldata_size,
            'analysis_time': self.analysis_time,
        }

    def from_dict(self, dict):
        self.id = dict['call_id']
        self.contract_addr = dict['contract_addr']
        self.call_type = dict['call_type']
        self.entry_point = dict['entry_point']
        self.function_tac_id = dict['function_tac_id']
        self.call_tac_id = dict['call_tac_id']
        self.classification = dict['classification']
        self.classification_type = dict['classification_type']
        self.contract_target = dict['contract_target']
        self.function_sig_target = dict['function_sig_target']
        self.result = dict['result']
        self.calldata = dict['calldata']
        self.calldata_size = dict['calldata_size']
        self.analysis_time = dict['analysis_time']

class ContractAnalysis():
    def __init__(self, contract_address):
        self.contract_address = contract_address
        self.block_ref = None
        self.funcs = 0
        self.tot_calls = 0

def is_contract(w3, contract_addr):
    if w3.eth.get_code(contract_addr).hex() != "0x":
        return True
    else:
        return False

def get_contract(address, where):
    if is_contract(w3, address):
        contract = w3.eth.contract(address=address)
        data = w3.eth.get_code(address).hex()
        full_path = os.path.join(where,"contract.hex")
        print(f'Saving contract at {full_path}')
        with open(full_path, "w") as f:
            f.write(data)
    else:
        print(f"{address} is not a contract")
        sys.exit(1)

# Gigahorse invocation over a target address.
def run_gigahorse(contract_addr):
    # Create folder if it does not exist
    exp_folder = os.path.join(WORKDIR, contract_addr[0:5], contract_addr)

    # Print exp folder
    print(f"Exp folder: {exp_folder}")

    if not os.path.exists(exp_folder):
        os.makedirs(exp_folder)

    # Get the contract bytecode from the chain
    get_contract(contract_addr, exp_folder)

    # Check if contract.hex exists
    folder = os.path.join(exp_folder, "contract.hex")
    if not os.path.exists(folder):
        print(f"Contract.hex does not exist at {folder}")
        sys.exit(1)

    # Run Gigahorse on the contract.hex file
    print(f"Running Gigahorse on {contract_addr}")

    command = f"cd {exp_folder} && timeout {GIGAHORSE_TIMEOUT} {GIGAHORSE_ANALYSIS_SCRIPT} --file ./contract.hex"
    print(f"{command}")
    subprocess.run(command, shell=True, check=True)

    # Check if .tac exists
    if not os.path.exists(os.path.join(exp_folder, "contract.tac")):
        #print("contract.hex.tac does not exist")
        # Report this in the gigahorse fails file
        with open(GIGAHORSE_FAILS, "a") as gigahorse_fails:
            print("Gigahorse analysis failed on {contract_addr}")
            #gigahorse_fails.write(f"Gigahorse analysis failed on {contract_addr}")
            return None

    print("Gigahorse finished!")

    return exp_folder

def load_csv(path: str, seperator: str='\t'):
    with open(path) as f:
        return [line.split(seperator) for line in f.read().splitlines()]

def load_csv_map(path: str, seperator: str='\t', reverse: bool=False):
    return {y: x for x, y in load_csv(path, seperator)} if reverse else {x: y for x, y in load_csv(path, seperator)}

def verify_confused_contract(deputy, calldata, call_tac_id, block):
    # Key: tac_id, value: original_pc
    TAC_TO_PC = load_csv_map(WORKDIR + f"/{deputy[0:5]}/{deputy}/TAC_Statement_OriginalStatement.csv")

    # res[1] is the calldata associated to the True positive
    cmd_check_tp = CMD_CHECK_TP.format(deputy, calldata, hex(int(TAC_TO_PC[call_tac_id],16)+1), block)

    # Start the py-evm script with subprocess and grab the output
    p = subprocess.Popen(cmd_check_tp, stdout=subprocess.PIPE, shell=True)

    # grab the output
    (output, err) = p.communicate()

    pyevm_res = output.strip().decode('utf-8')

    if pyevm_res == 'True':
        return True
    else:
        print("AA_CALL cannot be verified by py-evm :(")
        return False


#
# This script will implement the symbolic analysis as explained in Section 4.1 and 4.2 of the paper
# https://www.usenix.org/conference/usenixsecurity23/presentation/gritti.
#
# The script will check if a CALL target and func can both be controllable from CALLDATA.
# If this is true (i.e., AA classification), it will automatically synthetize a value for the CALLDATA
# and check if the CALL is reachable (with that CALLDATA) with a concrete execution using py-evm.
# If the CALL is reachable, the script will report a True positive (green color), if a CALL is reported
# to be controllabe by the symbolic analysis but it is not reachable with py-evm, the script will still
# report it, but its color is gonna be RED (this is a potential False positive).
#
# e.g.:
#    python run.py --ca 0x204Db9Ca00912c0F9e6380342113f6A0147E6f8C --block 16380000
#
if __name__ == '__main__':

    arg_parser = argparse.ArgumentParser(description='Jackal')
    arg_parser.add_argument('--ca', type=str, required=True)
    arg_parser.add_argument('--block', type=int, required=True)
    args = arg_parser.parse_args()

    contract_addr = args.ca
    block_ref = args.block

    # Does the contract exists at the block_ref?
    #   -> If it does not, as we are searching for exploitable bugs, we can skip this.
    if w3.eth.get_code(contract_addr, block_ref).hex() == '0x':
        log.info(f" [!]{contract_addr} selfdestruct at block {block_ref}")
        sys.exit(0)

    # Run Gigahorse against it
    target_dir = run_gigahorse(contract_addr)
    if target_dir == None:
        log.info(f" [!]{contract_addr} Gigahorse failed")
        sys.exit(0)

    # Some state options
    if os.environ.get('WEB3_PROVIDER', None):
        options.WEB3_PROVIDER = os.environ['WEB3_PROVIDER']
    else:
        options.WEB3_PROVIDER = 'http://127.0.0.1:8545'

    # Let's create the greed project
    try:
        project = Project(target_dir=target_dir)
    except Exception as e:
        print(f'Could not create greed project for {contract_addr}')
        sys.exit(0)

    calls = list()
    callcodes = list()
    for func in project.function_at.values():
        calls.extend([s for block in func.blocks for s in block._statement_at.values() if s.__internal_name__ == "CALL"])
        callcodes.extend([s for block in func.blocks for s in block._statement_at.values() if s.__internal_name__ == "CALLCODE"])

    if len(calls) + len(callcodes) == 0:
        print("No CALL(s) have been found in the contract. Aborting.")
        sys.exit(0)

    # Final report of all the CALLs in the contract.
    call_reports = list()

    for func in project.function_at.values():
        calls = [s for block in func.blocks for s in block._statement_at.values() if s.__internal_name__ == "CALL"]
        all_calls = calls

        if len(all_calls) != 0:
            for num, call in enumerate(all_calls):

                # every call has a unique id in the contract.
                call_id = contract_addr + "_" + call.id

                call_report = dict()
                inspect_call(target_dir, target_dir, contract_addr, project, func.id, call, block_ref, call_report)

                if call_report['classification'] == 'AA':
                    if check_call_reachability(contract_addr, block_ref, call_report['calldata'], call.id):
                        call_report['verified'] = True
                    else:
                        call_report['verified'] = False

                call_reports.append(call_report)

    for call_report in call_reports:
        if call_report['classification'] == 'AA' and call_report['verified'] == True:
            print(f'{bcolors.OKGREEN}{call_report}{bcolors.ENDC}')
        elif call_report['classification'] == 'AA' and call_report['verified'] == False:
            print(f'{bcolors.RED}{call_report}{bcolors.ENDC}')
        else:
            print(call_report)
