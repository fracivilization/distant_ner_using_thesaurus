# Distant Supervision NER using Thesaurus
Distant Supervision using Thesaurus

# Setup
## Setup python environment
This repository use poetry.
So, please run ...
```sh
poetry install
```
## Preprocess for UMLS
1. Please Dwonload 2021AA-full from https://www.nlm.nih.gov/research/umls/licensedcontent/umlsknowledgesources.html"
2. unzip the folder and unzip the mmsys system
3. Run Metamorphosys
    ```sh
    ./run_linux.sh # or ./run_mac.sh or run.bat
    ```
    1. Press "Install UMLS"
    2. Set Install Settings
       1. Source: data/2021AA-full
       2. Destination: data/2021AA-full/data
    3. Select New configuration
    4. License Agreement Notice: Accept
    5. Select Default Subset Configuration: Active Subset
    6. Source List>Select sources to INCLUDE in subset
       1.  Select all
    7. Done>Begin Subset> Would you like to save the changes?: No
    8.  MetamorphoSys Subset Log>OK

# Experiments
## Run main experiment
```sh
./scripts/main.sh
```
## Run experiment selecting 10 categories one by one
```sh
./scripts/select_1cat_exp.sh
```
## Run experiment in supervised setting in varying the size of supervised dataset
```sh
./scripts/check_supervised.sh
```