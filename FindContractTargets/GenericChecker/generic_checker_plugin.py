
from ethpwn.ethlib.utils import normalize_contract_address
from ethpwn.ethlib.evm.plugins.base import BaseAnalysisPlugin
from ethpwn.ethlib.evm.plugins.utils import * 

from typing import NamedTuple

class TracedSSTORE(NamedTuple):
    id: int
    pc: str
    slot: str
    value: str
    code_contract: str
    storage_contract: str
    func: str

'''
NOTE: Whenever we see a CALLER executed by the candidate_target and the value
would be the confused_contract (i.e., the confused contract is calling the target),
we change it to a random address, collect the SSTOREs in the candidate_target and terminate.
'''
class GenericCheckerPlugin(BaseAnalysisPlugin):
    
    name = "jackal_generic_checker"
    
    def __init__(self, confused_contract=None, candidate_target=None, candidate_target_func=None, overwrite_caller=False):
        super().__init__()
        self.confused_contract = normalize_contract_address(confused_contract)
        self.candidate_target = normalize_contract_address(candidate_target)
        self.candidate_target_func = hex(candidate_target_func)
        
        # Arbitrary address used for the check
        self.new_caller = "0x484Ffb8d32054cC79041E7D90400145b4B8a4470"
        self.track_sstores = False
        self.overwrite_caller = overwrite_caller

        self.global_id = 0
        self.sstores_report = []

    def pre_opcode_hook(self, opcode, computation):
        curr_code_contract = normalize_contract_address(computation.msg.code_address)
        curr_storage_contract = normalize_contract_address(computation.msg.storage_address)
        curr_func = "0x" + computation.msg.data.hex()[0:8]

        # If the SSTORE tracking is active but the candidate target is not in scope
        # anymore, we deactivate this mode.
        # we will have to wait for the post_opcode_hook to enable again this mode.
        # We also deactivate this mode if we are in a different function!
        if self.track_sstores and (curr_storage_contract != self.candidate_target or curr_func != self.candidate_target_func):
            self.track_sstores = False
        
        if self.track_sstores:
            if opcode.mnemonic == 'SSTORE':        
                if curr_storage_contract == self.candidate_target:
                    pc = computation.code.program_counter - 1
                    tsstore = TracedSSTORE(
                                           self.global_id, 
                                           hex(pc), 
                                           hex(read_stack_int(computation, 1)),
                                           hex(read_stack_int(computation, 2)),
                                           curr_code_contract,
                                           curr_storage_contract,
                                           curr_func
                                          )
                    self.global_id += 1
                    self.sstores_report.append(tsstore)
        

    def post_opcode_hook(self, opcode, computation):
        curr_contract = normalize_contract_address(computation.msg.code_address)
        curr_func = "0x" + computation.msg.data.hex()[0:8]

        if curr_contract == self.candidate_target and opcode.mnemonic == 'CALLER' and curr_func == self.candidate_target_func:
            
            current_caller_type, _ = computation._stack.values[-1]
            current_caller = normalize_contract_address(read_stack_int(computation, 1))
            #print(f"Found CALLER executed by the candidate target {self.candidate_target}!")
            
            if current_caller == self.confused_contract:
                #print(f"   The caller is the confused contract {self.confused_contract}!")
                if self.overwrite_caller:
                    if current_caller_type == int:
                        computation._stack.values[-1] = (
                            int,
                            int(self.new_caller, 16)
                        )
                    else:
                        computation._stack.values[-1] = (
                            bytes,
                             bytes.fromhex(self.new_caller[2:])
                        )
                    
                # We need to start track sstores
                self.track_sstores = True
                    

