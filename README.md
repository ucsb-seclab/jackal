# Confusum Contractum: Confused Deputy Vulnerabilities in Ethereum Smart Contracts

![ubuntu](https://img.shields.io/badge/Ubuntu-20.04+-yellow)
[![python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)

<a href="https://sites.cs.ucsb.edu/~vigna/publications/2023_USENIX_Confusum.pdf"> <img align="right" width="350"  src="https://github.com/ucsb-seclab/jackal/assets/4940271/17ddd3c6-8d04-4fd1-bdf2-2fe74f9bcd27"> </a>

This repository contains the code used for our USENIX paper <a href="https://sites.cs.ucsb.edu/~vigna/publications/2023_USENIX_Confusum.pdf">Confusum Contractum: Confused Deputy Vulnerabilities in Ethereum Smart Contracts</a>.
Our system, `Jackal`, can be used to find exploitable confused deputy vulnerabilities on the Ethereum blockchain.

# ⚠️ Disclaimer 

For different technical and ethical reasons, here we are not releasing a fully automated "push-one-button" solution for the identification and automatic exploitation of smart contracts. Rather, we open-sourced all the necessary scripts to demonstrate the analyses presented in the paper. Interested researchers will have all the necessary code to replicate our work. In case something does not click, please reach out to us :)

# ⚡️ Setup

Just clone the repo and run the `setup.sh` script:

```bash
$ git clone https://github.com/ucsb-seclab/jackal.git && ./setup.sh <WEB3_RPC_ENDPOINT>
```

This script will install [ethpwn](https://github.com/ethpwn/ethpwn) (the Swiss Army Knife for Smart Contracts Hacking) and [greed](https://github.com/ucsb-seclab/greed), our symbolic execution engine for EVM smart contracts. 

The `WEB3_RPC_ENDPOINT` parameter is a URL to a JSON-RPC Web3 endpoint. If you are running a private node this can be, e.g., `http://0.0.0.0:8545`. Otherwise, you can use services like [Infura](https://www.infura.io/) or [Alchemy](https://www.alchemy.com/) to obtain access to their API (there is a free-tier which is more than enough for using our tool).



# 🚀 Usage

## `CALL` Inspector

The identification of controllable `CALL`(s) in a smart contract binary is done with the script [run.py](https://github.com/ucsb-seclab/jackal/blob/master/CheckConfusedContracts/run.py) in `CheckConfusedContracts`. e.g.,:

```bash
$ cd jackal/CheckConfusedContracts
$ python run.py --ca 0x204Db9Ca00912c0F9e6380342113f6A0147E6f8C --block 16380000 
```

`0x204Db9Ca00912c0F9e6380342113f6A0147E6f8C` is the address of the contract you want to analyze, while `16380000` is the block (height) that is gonna be used as a reference for this analysis (i.e., storage variables).
If a controllable `CALL` is detected the script will report a True positive by highlighting the log with a green color.


## Generic Checker

This script is used to find possible "generic" targets (see Section 4.3 in the paper) for an end-to-end exploitation of a confused deputy vulnerability. Please read the note in the [generic_checker.py](https://github.com/ucsb-seclab/jackal/blob/master/FindContractTargets/GenericChecker/generic_checker.py) for more information. Usage:

```bash
$ cd jackal/FindContractTargets/GenericChecker
$ python generic_checker.py --confused 0x11b815efb8f581194ae79006d24e0d814b7697f6 --target 0xdAC17F958D2ee523a2206206994597C13D831ec7 --tx 0x15bef4b45379ad3dfa676f206c1ce0d9d4a18164d82a0d1a71737652c9456212 --func 0xa9059cbb
```

## Token Checker
This script is used to find possible ERC20 targets (see Section 4.3 in the paper) for an end-to-end exploitation of a confused deputy vulnerability. Please read the note in the [tokens_checker.py](https://github.com/ucsb-seclab/jackal/blob/master/FindContractTargets/TokenChecker/tokens_checker.py.py) for more information. Usage:

```bash
$ cd jackal/FindContractTargets/TokenChecker
$ python tokens_checker.py --ca 0x2057CfB9fD11837D61B294D514C5bd03e5E7189A --block-start 14104827
```

## Automatic Exploit Generation

Finally, this script implement the (A)utomatic (E)xploit (G)eneration algorithm described in Section 4.4 of the paper. Specifically, this script automatically synthetize the necessary `CALLDATA` to (1) force a confused contract to call a `transfer` function in an ERC20 contract of choice, and (2) gracefully terminate the execution to complete the exploit.
Please read the note in the [aeg.py](https://github.com/ucsb-seclab/jackal/blob/master/ERC20AutomaticExploitGeneration/aeg.py) script for further information. Usage:

```bash
$ cd jackal/ERC20AutomaticExploitGeneration
$ python aeg.py 0xeC55Bf7E10b6594874554BAd1B461214Cab413d4 --aa_call_id 0x9f7 --contract_target 0x6B175474E89094C44Da98b954EedeAC495271d0F --function_target_sig 0xa9059cbb --block 11469710 --entry_point 0xcbd8c06a
```