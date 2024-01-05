# Bunch of random stuff that is useful here and there

import sys
import pdb
import logging
import requests
import os 

from myglobals import *

from greed.exploration_techniques import ExplorationTechnique

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    # Background colors:
    GREYBG = '\033[100m'
    REDBG = '\033[101m'
    GREENBG = '\033[102m'
    YELLOWBG = '\033[103m'
    BLUEBG = '\033[104m'
    PINKBG = '\033[105m'
    CYANBG = '\033[106m'

class multipdb(pdb.Pdb):
    """A Pdb subclass that may be used
    from a forked multiprocessing child
    """
    def interaction(self, *args, **kwargs):
        _stdin = sys.stdin
        try:
            sys.stdin = open('/dev/stdin')
            pdb.Pdb.interaction(self, *args, **kwargs)
        finally:
            sys.stdin = _stdin

# We panic only when there are errors that 
# need to be fixed in the worker/analyses
def panic(worker_folder, msg=''):
    log.critical(f"[!!] {msg}")
    # Create panic file to signal the worker to stop.
    with open(worker_folder + "/.panic", "w") as f:
        f.write("panic")
    
    #multipdb().set_trace()

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

# Class to store information regarding a call
class CallInfo():
    def __init__(self, call_stmt):

        self._wrapped_call = call_stmt

        self.has_static_target_contract = None
        self.has_static_target_function  = None

        self.target_contract_classification = 'x'
        self.target_contract_classification_type = ''
        self.target_function_classification = 'y'
        self.target_function_classification_type = ''

        # If static, here we have the values
        self.contract_target = None
        self.function_target = None

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return getattr(self,attr)
        return getattr(self._wrapped_call, attr)


class GreedExceptionLogger(ExplorationTechnique):
    def __init__(self, contract_addr, log_file_name):
        super(GreedExceptionLogger, self).__init__()
        self.log_file_name = log_file_name
        self.reported_states = set()
        if not os.path.exists(self.log_file_name):
            with open(self.log_file_name, "a") as log_file_name_fd:
                log_file_name_fd.write(f"\n====={contract_addr}=====")
    
    def check_stashes(self, simgr, stashes):
        if len(stashes['errored']) >= 1:
            for errored_state in stashes['errored']:
                # Grab the exceptions if we haven't done it before 
                if errored_state.pc not in self.reported_states:
                    with open(self.log_file_name, "a") as log_file_name_fd:
                        log_file_name_fd.write("\n"+errored_state.error.args[0]+"\n")
                    self.reported_states.add(errored_state.pc)
        return stashes
