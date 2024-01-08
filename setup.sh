
#!/bin/bash
# set -x

# CURRENT-WORKDIR: jackal
read -p "Press continue if you are in a python virtual env: " ANSWER

apt-get update 
apt-get install -y htop tmux git vim nano\ 
                   wget cmake python3-pip wget\
                   graphviz libgraphviz-dev libffi-dev python3.11-dev python3.11\
                   gperf libgmp-dev mkisofs bison clang doxygen flex libncurses5-dev\ 
                   libsqlite3-dev mcpp libboost-all-dev time

# get the WEB3_PROVIDER url from user
read -p "Enter WEB3_PROVIDER url: " W3_PROVIDER

# export the WEB3_PROVIDER as environment variable
export WEB3_PROVIDER=$W3_PROVIDER

git clone https://github.com/ethpwn/ethpwn.git
cd ethpwn && pip install -e .
ethpwn wallet create

rm ~/.config/ethpwn/config.json

echo "{
  \"default_network\": \"mainnet\",
  \"default_node_urls\": {
    \"mainnet\": \"$W3_PROVIDER\",
  },
}" > ~/.config/ethpwn/config.json


# back to jackal folder
cd ..se
git clone https://github.com/ucsb-seclab/greed.git
cd greed
git checkout fae1812180ff2ffe4b0a789f84071988b0917745 # release 1.0.0
echo "OK" | ./setup.sh

echo "DONE!"