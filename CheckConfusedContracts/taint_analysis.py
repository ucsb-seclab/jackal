import logging

from greed.solver.shortcuts import *
from sha_resolver import ShaResolver
from myutils import *
    
'''
# Not sure if I need this:
# Safety check, given the previous CALLDATA, do we have only one solution? If yes, good, otherwise
# it means targetContracts depends from other things and this is not a reliable check!
if self.state.solver.is_formula_sat( And(
                                        Equal(calldata_sol, self.state.calldata.readn(BVV(0,256), BVV(calldata_size,256))),
                                        NotEqual(targetContract_raw, self.state.registers[self.state.curr_stmt.arg2_var])
                                        )
                                    )
'''
class CalldataToCallTarget():
    def __init__(self, state_at_call, worker_folder, taint_analysis_for_contract, taint_analysis_for_func):
        self.state = state_at_call
        self.worker_folder = worker_folder

        self.taint_analysis_for_contract = taint_analysis_for_contract
        self.taint_analysis_for_func = taint_analysis_for_func

        self.target_contract_tainted = False
        self.target_function_tainted = False 

        self.first_solution_for_contract_target = ''
        self.first_solution_for_function_target = ''
        
        # Get an instance for the sha resolver
        self.sha_resolver = ShaResolver(self.state)
        self.state_has_shas = True if len(self.state.sha_observed) != 0 else False

        self.calldata_for_call = None
        self.calldata_size = None

    
    def reg_to_human(self, val):
        return hex(bv_unsigned_value(val))

    def mem_to_human(self, val, size):
        return bv_unsigned_value(val).to_bytes(bv_unsigned_value(size), 'big').hex()

    def we_done(self):
        # EXIT CONDITIONS
        if self.taint_analysis_for_contract and not self.taint_analysis_for_func:
            return self.target_contract_tainted
        elif self.taint_analysis_for_contract and self.taint_analysis_for_func:
            return self.target_contract_tainted and self.target_function_tainted
        elif not self.taint_analysis_for_contract and self.taint_analysis_for_func:
            return self.target_function_tainted
        return False
    
    def run(self):    
        # GET SOLUTIONS AT CALLSTATE 
        calldata_size = self.state.solver.eval(self.state.calldatasize)
        calldata_sol = self.state.solver.eval_memory(self.state.calldata, BVV(calldata_size,256), raw=True)

        # Fix CALLDATA solution in a new frame (+1)
        self.state.solver.push()
        if self.state.solver.frame != 1:
            panic(self.worker_folder, msg="Wrong frame for solver during taint analysis (!=1)")

        self.state.add_constraint(Equal(calldata_sol, self.state.calldata.readn(BVV(0,256), BVV(calldata_size,256))))

        # Resolve SHAs if any (this also fix the solutions in the solver in a new frame) (+1)
        if self.state_has_shas:
            if not self.sha_resolver.fix_shas():
                self.state.solver.pop_all() # Clean frames (0)
                if self.state.solver.frame != 0:
                    panic(self.worker_folder, msg="Wrong frame for solver during taint analysis (!=0)")
                # If we cannot fix SHAs, let's call it a day
                return
        
        self.calldata_for_call = self.mem_to_human(calldata_sol, BVV(calldata_size,256))
        self.calldata_size = calldata_size

        if self.taint_analysis_for_contract:
            # Get solution for targetContract
            targetContract_raw = self.state.solver.eval(self.state.registers[self.state.curr_stmt.arg2_var], raw=True)
            self.first_solution_for_contract_target = self.reg_to_human(targetContract_raw)

        if self.taint_analysis_for_func:
            # Get solution for targetFunction
            mem_offset_call_raw = self.state.solver.eval(self.state.registers[self.state.curr_stmt.arg4_var], raw=True)
            mem_offset_call = bv_unsigned_value(mem_offset_call_raw)
            
            # Here we consider only the first 4 bytes
            mem_argSize_raw = BVV(4, 256)
            mem_at_call_raw = self.state.solver.eval_memory_at(self.state.memory, mem_offset_call_raw, mem_argSize_raw, raw=True)
            mem_at_call = bv_unsigned_value(mem_at_call_raw)

            self.first_solution_for_function_target = self.mem_to_human(mem_at_call_raw, mem_argSize_raw)

        # removes sha constraints (-1)
        if self.state_has_shas:
            self.state.solver.pop()

        # remove constraint for CALLDATA
        self.state.solver.pop()

        # HERE FRAMEs ARE CLEAN (0)
        if self.state.solver.frame != 0:
            panic(self.worker_folder, msg="Wrong frame for solver during taint analysis (!=0)")
        

        # MANIPULATION ANALYSIS STARTING HERE 

        if self.taint_analysis_for_contract:
            # Fix CALLDATA solution in a new frame (+1)
            self.state.solver.push()
            self.state.add_constraint(Equal(calldata_sol, self.state.calldata.readn(BVV(0,256), BVV(calldata_size,256))))
            if self.state_has_shas and not self.sha_resolver.fix_shas():
                panic(self.worker_folder, msg="SHAs are broken????")

            # Safety check, given the previous CALLDATA, do we have multiple solutions? If yes,
            # it means targetContracts depends from other things and this is not a reliable check!
            # We'll tag this as not controllable to filter false-positve ahead
            if self.state.solver.is_formula_sat(NotEqual(targetContract_raw, self.state.registers[self.state.curr_stmt.arg2_var])):
                self.target_contract_tainted = False
            else: 
                # Ok, filter passed, let's check if we can find a path preserving CALLDATA with != targetContract
                
                # Remove constraints for SHAs related to original CALLDATA
                if self.state_has_shas:
                    self.state.solver.pop()
                # Remove constraint for original CALLDATA
                self.state.solver.pop()

                if self.state.solver.frame != 0:
                    panic(self.worker_folder, msg="Wrong frame for solver during taint analysis (!=0)")

                # We want a different CALLDATA
                self.state.add_constraint(NotEqual(calldata_sol, self.state.calldata.readn(BVV(0,256), BVV(calldata_size,256))))
                
                if not self.state.solver.is_sat():
                    self.target_contract_tainted = False
                else:   
                    shas_ok = True
                    # Fix SHAs if any
                    if self.state_has_shas:
                        if not self.sha_resolver.fix_shas():
                             # SHAs cannot be resolved anymore...
                            self.state.solver.pop_all() # Clean frames (0)
                            if self.state.solver.frame != 0:
                                panic(self.worker_folder, msg="Wrong frame for solver during taint analysis (!=0)")
                            shas_ok = False
                    if shas_ok:
                        # Check for different solution for the targetContract
                        if self.state.solver.is_formula_sat(NotEqual(targetContract_raw, self.state.registers[self.state.curr_stmt.arg2_var])):
                            self.target_contract_tainted = True

        self.state.solver.pop_all() # Clean frames (0)
        if self.state.solver.frame != 0:
            panic(self.worker_folder, msg="Wrong frame for solver during taint analysis (!=0)")

        if self.taint_analysis_for_func:
            # Fix CALLDATA solution in a new frame (+1)
            self.state.solver.push()
            self.state.add_constraint(Equal(calldata_sol, self.state.calldata.readn(BVV(0,256), BVV(calldata_size,256))))

            # We want argSize to be different than 0!
            self.state.add_constraint(NotEqual(self.state.registers[self.state.curr_stmt.arg5_var], BVV(0,256)))
            
            if self.state_has_shas and not self.sha_resolver.fix_shas():
                panic(self.worker_folder, msg="SHAs are broken????")

            if self.state.solver.is_formula_sat(NotEqual(mem_at_call_raw, 
                                                         self.state.memory.readn(self.state.registers[self.state.curr_stmt.arg4_var], BVV(4,256)))
                                                ):
                self.target_function_tainted = False
            
            else:
                # Ok, filter passed, let's check if we can find a path preserving CALLDATA with != targetFunction
                
                # Remove constraints for SHAs related to original CALLDATA
                if self.state_has_shas:
                    self.state.solver.pop()
                # Remove constraint for original CALLDATA
                self.state.solver.pop()

                if self.state.solver.frame != 0:
                    panic(self.worker_folder, msg="Wrong frame for solver during taint analysis (!=0)")

                # We want a different CALLDATA
                self.state.add_constraint(NotEqual(calldata_sol, self.state.calldata.readn(BVV(0,256), BVV(calldata_size,256))))
                # We want argSize to be different than 0!
                self.state.add_constraint(NotEqual(self.state.registers[self.state.curr_stmt.arg5_var], BVV(0,256)))

                if not self.state.solver.is_sat():
                    self.target_function_tainted = False
                else:
                    # Fix SHAs if any
                    shas_ok = True
                    if self.state_has_shas:
                        if not self.sha_resolver.fix_shas():
                            # SHAs cannot be resolved anymore...
                            self.state.solver.pop_all() # Clean frames (0)
                            if self.state.solver.frame != 0:
                                panic(self.worker_folder, msg="Wrong frame for solver during taint analysis (!=0)")
                            # If we cannot fix SHAs, let's call it a day
                            shas_ok = False
                    if shas_ok:
                        # Check for different solution for the targetFunction
                        if self.state.solver.is_formula_sat(NotEqual(mem_at_call_raw,
                                                                    self.state.memory.readn(self.state.registers[self.state.curr_stmt.arg4_var], BVV(4,256)))):
                            self.target_function_tainted = True

        self.state.solver.pop_all()

        # Just making sure :)
        if self.state.solver.frame != 0:
            panic(self.worker_folder, msg="Wrong frame for solver during taint analysis (!=0)")