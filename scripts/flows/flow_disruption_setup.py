"""This script allows us to select and parallelise the failure analysis simulations on a server with multipe core processors
    The failure simulations selected here are for:
        Inidiviudal edges of an initiating network - road + rail 
        For a partiuclar current or future scenario - [2019,2030,2050,2080]
    
    The script first reads in the edges data for a particular network 
        And then divides the numbers of edges into paritions which will be selected as initiating failure scenarios
        
        Example output - 2019,1,0,90
        - Network scenarios - year
        - Number of failure scenario - 1
        - First edge to sample for initiating failure - The one at location 0 on the edge list
        - Last edge to sample for initiating failure - The one at location 90 on the edge list  
        
        We are mainly selecting the first 91 edges of the flooded road + rail network one-by-one and failing them
        
        All partitions are writtening into text files named as parallel_network_scenario_dependency.txt 
        Example: partitions_2019.txt

        Example output in file: partitions.txt
            2019,1,0,90
            2019,2,90,181
            2019,3,181,272
            2019,4,272,363
            2019,5,363,453
            2019,6,453,544
            2019,7,544,635
        
        Each of these lines is a batch of scnearios that are run on different processors in parallel
"""
import os
import sys
import pandas as pd
from analysis_utils import *
from tqdm import tqdm
import subprocess 

tqdm.pandas()
def main(config):
    results_data_path = config['paths']['results']
    failure_results = os.path.join(results_data_path,"flow_disruptions")
    if os.path.exists(failure_results) == False:
        os.mkdir(failure_results)
    """
    Create edge failure files with the batches for parallel processing
    """
    damages_results_path = os.path.join(results_data_path,"risk_results","direct_damages_summary")

    rail_failure_edges = pd.read_csv(os.path.join(damages_results_path,"rail_edges_damages.csv"))
    road_failure_edges = pd.read_csv(os.path.join(damages_results_path,"road_edges_damages.csv"))

    all_failures = rail_failure_edges["edge_id"].values.tolist() + road_failure_edges["edge_id"].values.tolist()

    num_partitions = 200 # Number of partitions of the networks edges created for parallel processing
    num_blocks = 20
    scenarios = [2019,2030,2050,2080]
    # scenarios = [2030,2050,2080]
    for sc in scenarios:    
        num_values = np.linspace(0,len(all_failures)-1,num_partitions)
        fp = os.path.join(failure_results,str(sc))
        if os.path.exists(fp) == False:
            os.mkdir(fp)
        with open(f"parallel_{sc}.txt","w+") as f:
            for n in range(len(num_values)-1):  
                f.write(f'{sc},{fp},{int(num_values[n])},{int(num_values[n+1])}\n')        
        f.close()
    
        args = ["parallel",
                "-j", str(num_blocks),
                "--colsep", ",",
                "-a",
                f"parallel_{sc}.txt",
                "python",
                "flow_disruptions.py",
                "{}"
                ]
        print (args)
        subprocess.run(args)
                                
if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)