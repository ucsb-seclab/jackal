
import logging
import os
import datetime 
import networkx as nx

from greed.TAC.base import TAC_Statement
from greed.exploration_techniques import ExplorationTechnique, DirectedSearch, HeartBeat, Prioritizer
from greed import Project
from greed import options
from greed.utils.extra import gen_exec_id

from myutils import *
from myglobals import *
from taint_analysis import CalldataToCallTarget


LOGGING_FORMAT = "%(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
log = logging.getLogger("analyze_call")
log.setLevel(logging.INFO)


def analyze_call_from_ep(project, worker_folder, contract_addr, entry_point, call, last_block, taint_analysis_for_contract, taint_analysis_for_func):
    
    p = project

    options.GREEDY_SHA = True
    options.LAZY_SOLVES = False
    options.STATE_INSPECT = False
    options.MAX_SHA_SIZE = 300
    options.OPTIMISTIC_CALL_RESULTS = True
    options.DEFAULT_EXTCODESIZE = True
    options.DEFAULT_CREATE2_RESULT_ADDRESS = True
    options.DEFAULT_CREATE_RESULT_ADDRESS = True
    options.MATH_CONCRETIZE_SYMBOLIC_EXP_EXP = True
    options.MATH_CONCRETIZE_SYMBOLIC_EXP_BASE = True

    MAX_CALLDATA_SIZE = 1024

    calldata = entry_point.signature 
    
    block_info = w3.eth.get_block(last_block)

    # Let's set the CALLER to my account
    init_ctx = {
                "CALLDATA": calldata, 
                "CALLER": "0x6b6Ae9eDA977833B379f4b49655124b4e5c64086", 
                "ORIGIN": "0x6b6Ae9eDA977833B379f4b49655124b4e5c64086",
                "ADDRESS": contract_addr,
                "NUMBER": last_block,
                "DIFFICULTY": block_info["totalDifficulty"],
                "TIMESTAMP": block_info["timestamp"]
                }

    xid = gen_exec_id()
    
    entry_state = p.factory.entry_state(
                                        xid=xid, 
                                        init_ctx=init_ctx, 
                                        max_calldatasize=MAX_CALLDATA_SIZE,
                                        partial_concrete_storage=True
                                        )

    simgr = p.factory.simgr(entry_state=entry_state)
    
    directed_search = DirectedSearch(call)
    simgr.use_technique(directed_search)

    prioritizer = Prioritizer(scoring_function=lambda s: -s.globals['directed_search_distance'])
    simgr.use_technique(prioritizer)
    
    #heartbeat = HeartBeat(beat_interval=100, show_op=False)
    #simgr.use_technique(heartbeat)

    log.info(f"  Symbolically executing from {entry_point.name} to {call.__internal_name__} at {call.id}")
    
    result = dict()

    while True:
        try:
            simgr.run(find=lambda s: s.curr_stmt.id == call.id)
        except Exception as e:
            result['ep'] = entry_point.signature
            result['status'] = "SYMEXCEPTION-{}".format(e)
            return result
        
        if len(simgr.found) == 1:
            log.info(f"   ✅ Found state for {call.__internal_name__} at {call.id}!")
            state = simgr.one_found
                        
            if state.solver.frame != 0:
                panic(worker_folder, msg="Wrong frame for solver when raching CALL (!=0)")
            
            log.info(f"   Running taint analysis now...")
            ta = CalldataToCallTarget(state, worker_folder, taint_analysis_for_contract, taint_analysis_for_func) 
            ta.run()

            result['status'] = "SUCCESS"
            result['ep'] = entry_point.signature
            result['calldata'] = ta.calldata_for_call
            result['calldata_size'] = ta.calldata_size
            if taint_analysis_for_contract:
                result["target_contract_tainted"] =  "A"  if ta.target_contract_tainted else "N"
                if result["target_contract_tainted"] == "N":
                    result["solution_target_contract"] = ta.first_solution_for_contract_target
            if taint_analysis_for_func:
                result["target_function_tainted"] =  "A"  if ta.target_function_tainted else "N" 
                if result["target_function_tainted"] == "N":
                    result["solution_target_function"] = ta.first_solution_for_function_target
            
            return result
        else:
            result['ep'] = entry_point.signature
            result['status'] = "UNREACHABLE"
            return result

# Here we want to understand from which function
# it is possible to reach this specific CALL statement. 
# Returns a list of entry-points that can reach the CALL.
def how_to_reach(p: Project, target_call:TAC_Statement):
    target_function = p.factory.block(target_call.block_id).function

    # If the function containing the CALL is public we are done.
    if target_function.public:
        #log.debug(f"Path {[target_function.name]}")
        return [target_function]

    # Otherwise, we need to find the entry points that lead to this CALL
    # using the callgraph.
    # To do that, we start from all the public functions, and see if they 
    # can reach the function.id of the CALL under analysis.
    possible_entry_points = [f for f in p.function_at.values() if f.public and f.id != '0x0']
    entry_points = set()
    for ep in possible_entry_points:
        if nx.has_path(p.callgraph, source=ep, target=target_function):
            #for path in nx.all_simple_paths(p.callgraph, source=ep, target=target_function):
            #    log.info(f"Path: {[func.name for func in path]}")
            entry_points.add(ep)
    
    return entry_points

def inspect_dynamically(worker_folder, p, contract_addr, call, last_block, taint_analysis_for_contract, taint_analysis_for_func):
    entry_points = how_to_reach(p, call)
    for ep in entry_points:
        if ep.signature != None:
            result = analyze_call_from_ep(p, worker_folder, contract_addr, ep, call, last_block,taint_analysis_for_contract, taint_analysis_for_func)
            return result
    return {'ep': "", 'status': "NO_ENTRY_POINT"}
    
def inspect_static(call):
    # Do we have a static value for the register holding the 
    # contract address?
    if call.arg2_val:
        #log.info(f"  {call.__internal_name__} at {call.id} calls contract at {hex(call.arg2_val.value)}")
        call.has_static_target_contract = True
        call.target_contract_classification = "N" # Not controllable
        call.target_contract_classification_type = "S" # Static classification (Gigahorse)
        call.static_target_contract = hex(call.arg2_val.value)
    if call.likely_known_target:
        #log.info(f"  {call.__internal_name__} at {call.id} calls function {call.target_function}")
        call.has_static_target_function = True
        call.target_function_classification = "N"
        call.target_function_classification_type = "S"
        call.static_target_function = call.likely_known_target

def inspect_call(target_dir, worker_folder, contract_addr, project, func_id, call, last_block, call_report):
    
    p = project

    # Wrap the call object to add metadata regarding this analysis
    call = CallInfo(call)

    job_start_time = datetime.datetime.now().timestamp()
    log.info(f" Statically investigating {call.__internal_name__} at {call.id}")

    inspect_static(call)

    # Case 1: NN_CALL, we are done, no need for further analysis.
    if call.target_contract_classification  == "N" and call.target_function_classification == "N":
        log.info(f"  {call.id} is a NN_CALL (SS)")
        call_report['entry_point'] = '-'
        call_report['classification'] = "NN"
        call_report['classification_type'] = "SS"
        call_report['contract_target'] = call.static_target_contract
        call_report['function_sig_target'] = call.static_target_function
        call_report['result'] = "SUCCESS"
        call_report['calldata'] = "0x"
        call_report['calldata_size'] = 0
        call_report['analysis_time'] = datetime.datetime.now().timestamp() - job_start_time

    # Case 2: Ny_CALL, contract is constant, function is unknown, run our dynamic analysis
    elif call.target_contract_classification  == "N" and call.target_function_classification == "y":
        log.info(f"  {call.id} is a Ny_CALL")
        
        call_report['classification'] = "Ny"
        call_report['classification_type'] = "SD"
        call_report['contract_target'] = call.static_target_contract
        call_report['function_sig_target'] = "-"
        call_report['calldata'] = '0x'
        call_report['calldata_size'] = 0

        result = inspect_dynamically(worker_folder, p, contract_addr, call, last_block, 
                                                taint_analysis_for_contract=False, taint_analysis_for_func=True)
        

        if result['status'] == "SUCCESS":
            call_report['entry_point'] = result["ep"]
            call_report['classification'] = "N" + result["target_function_tainted"]
            
            if result["target_function_tainted"] == "N":
                call_report['function_sig_target'] = result["solution_target_function"]
            else:
                call_report['function_sig_target'] = "*"
            call_report['result'] = "SUCCESS"
            call_report['calldata'] = result["calldata"]
            call_report['calldata_size'] = result["calldata_size"]
            call_report['analysis_time'] = datetime.datetime.now().timestamp() - job_start_time
            log.info(f"  {call.id} is a {call_report['classification']}_CALL (SD)")
        else:
            call_report['entry_point'] = result["ep"]
            call_report['result'] = result["status"]
            call_report['analysis_time'] = datetime.datetime.now().timestamp() - job_start_time


    # Case 3: xy_CALL:
    # nothing can be said statically about anything, proceed with full taint analysis.
    elif call.target_contract_classification  == "x" and call.target_function_classification == "y":
        log.info(f"  {call.id} is a xy_CALL")

        call_report['classification'] = "xy"
        call_report['classification_type'] = "DD"
        call_report['contract_target'] = "-"
        call_report['function_sig_target'] = "-"
        call_report['calldata'] = '0x'
        call_report['calldata_size'] = 0

        result = inspect_dynamically(worker_folder, p, contract_addr, call, last_block, 
                                                taint_analysis_for_contract=True, taint_analysis_for_func=True)
        

        if result['status'] == "SUCCESS":
            call_report['entry_point'] = result["ep"]
            call_report['classification'] = result["target_contract_tainted"] + result["target_function_tainted"]
            call_report['classification_type'] = "DD"
            if result["target_contract_tainted"] == "N":
                call_report['contract_target'] = result["solution_target_contract"]
            else:
                call_report['contract_target'] = "*"
            if result["target_function_tainted"] == "N":
                call_report['function_sig_target'] = result["solution_target_function"]
            else:
                call_report['function_sig_target'] = "*"
            call_report['result'] = "SUCCESS"
            call_report['calldata'] = result["calldata"]
            call_report['calldata_size'] = result["calldata_size"]
            call_report['analysis_time'] = datetime.datetime.now().timestamp() - job_start_time
            log.info(f"  {call.id} is a {call_report['classification']}_CALL (DD)")
        else:
            call_report['entry_point'] = result["ep"]
            call_report['result'] = result["status"]
            call_report['analysis_time'] = datetime.datetime.now().timestamp() - job_start_time


    # Case 4: xN_CALL:
    # nothing can be said statically about targetContract, targetFunction is not controllable.
    elif call.target_contract_classification  == "x" and call.target_function_classification == "N":
        log.info(f"  {call.id} is a xN_CALL")

        call_report['classification'] = "xN"
        call_report['classification_type'] = "DS"
        call_report['contract_target'] = "-"
        call_report['calldata'] = '0x'
        call_report['calldata_size'] = 0
        call_report['function_sig_target'] = call.static_target_function

        result = inspect_dynamically(worker_folder, p, contract_addr, call, last_block, 
                                                taint_analysis_for_contract=True, taint_analysis_for_func=False)
        

        if result['status'] == "SUCCESS":
            call_report['entry_point'] = result["ep"]
            call_report['classification'] = result["target_contract_tainted"] + "N"
            call_report['classification_type'] = "DS"
            if result["target_contract_tainted"] == "N":
                call_report['contract_target'] = result["solution_target_contract"]
            else:
                call_report['contract_target'] = "*"
            
            call_report['result'] = "SUCCESS"
            call_report['calldata'] = result["calldata"]
            call_report['calldata_size'] = result["calldata_size"]
            call_report['analysis_time'] = datetime.datetime.now().timestamp() - job_start_time
            log.info(f"  {call.id} is a {call_report['classification']}_CALL (DS)")
        else:
            call_report['entry_point'] = result["ep"]
            call_report['result'] = result["status"]
            call_report['analysis_time'] = datetime.datetime.now().timestamp() - job_start_time


    else:
        panic(worker_folder, msg="Unexpected classification")