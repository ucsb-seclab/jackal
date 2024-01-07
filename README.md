# Confusum Contractum: Confused Deputy Vulnerabilities in Ethereum Smart Contracts

![ubuntu](https://img.shields.io/badge/Ubuntu-20.04+-yellow)
[![python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)

<a href="https://sites.cs.ucsb.edu/~vigna/publications/2023_USENIX_Confusum.pdf"> <img align="right" width="350"  src="https://github.com/ucsb-seclab/jackal/assets/4940271/17ddd3c6-8d04-4fd1-bdf2-2fe74f9bcd27"> </a>

This repository contains the code used for our USENIX paper <a href="https://sites.cs.ucsb.edu/~vigna/publications/2023_USENIX_Confusum.pdf">Confusum Contractum: Confused Deputy Vulnerabilities in Ethereum Smart Contracts</a>.
Our system, `Jackal`, can be used to find exploitable confused deputy vulnerabilities on the Ethereum blockchain.

# Disclaimer 

For different technical and ethical reasons, here we are not releasing a fully automated "push-one-button" solution for the identification and automatic exploitation of smart contracts. Rather, we open-sourced all the necessary scripts to demonstrate the analyses presented in the paper. Interested researchers will have all the necessary code to replicate our work. In case something does not click, please reach out to us :)

# Setup

First, you will need to install [ethpwn](https://github.com/ethpwn/ethpwn) (the Swiss Army Knife for Smart Contracts Hacking) and [greed](https://github.com/ucsb-seclab/greed): our symbolic execution engine for EVM smart contracts. To do this, follow the instructions in the respective repos.
 Here a TL;DR:

```bash
# Clone and install ethpwn, make sure your pip version is >= 23.1.2
git clone git@github.com:ethpwn/ethpwn.git && cd ./ethpwn && pip install -e .

# Clone and install greed
git clone git@github.com:ucsb-seclab/greed.git
# Create a virtual environment (e.g., using virtualenvwrapper)
mkvirtualenv greed
# Activate the virtual environment
workon greed
# Install greed (will setup gigahorse, yices, and `pip install -e greed`)
cd greed
./setup.sh
```

After that, you are ready to clone and use `Jackal`!

```bash
git clone https://github.com/ucsb-seclab/jackal.git
```

# Usage