import web3 
import os

# We consider for EVERY analysis the same block.
# For the hackcess-live, we consider the block of deployment of the contract.
BLOCK_REF = -1

WORKDIR = "../Analyses/"

# 30 minutes for taint analysis
TIMEOUT_TAINT_ANALYSIS = 60 * 2

# This script is exported by greed during the installation
GIGAHORSE_ANALYSIS_SCRIPT = "analyze_hex.sh"
GIGAHORSE_TIMEOUT = "20m"

if os.environ.get('WEB3_PROVIDER', None):
    w3 = web3.Web3(web3.Web3.HTTPProvider(os.environ['WEB3_PROVIDER']))
else:
    w3 = web3.Web3(web3.Web3.HTTPProvider('http://127.0.0.1:8545'))

assert(w3.is_connected())


