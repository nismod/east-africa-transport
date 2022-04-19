"""This script allows us to select and parallelise the Damage and Loss estimations on a server with multiple core processors
"""
import os
import sys
import ujson
from SALib.sample import morris
import SALib.analyze.morris 
from analysis_utils import *
import subprocess 

def main(config):
    processed_data_path = config['paths']['data']
    results_path = config['paths']['results']

    hazard_csv = os.path.join(processed_data_path,
                            "hazards",
                            "hazard_layers.csv")
    network_csv = os.path.join(processed_data_path,
                            "damage_curves",
                            "network_layers_hazard_intersections_details.csv")
    damage_curves_csv = os.path.join(processed_data_path,
                            "damage_curves",
                            "asset_damage_curve_mapping.csv")
    hazard_damage_parameters_csv = os.path.join(processed_data_path,
                            "damage_curves",
                            "hazard_damage_parameters.csv")

    damage_results_folder = "risk_results/direct_damages"
    summary_folder = "risk_results/direct_damages_summary"
    timeseries_results_folder = "risk_results/loss_damage_timeseries"
    discounted_results_folder = "risk_results/loss_damage_npvs"

    flood_protection_column = "None"

    parameter_combinations_file = "parameter_combinations.txt"
    # Set up problem for sensitivity analysis
    problem = {
              'num_vars': 2,
              'names': ['cost_uncertainty_parameter','damage_uncertainty_parameter'],
              'bounds': [[0.0,1.0],[0.0,1.0]]
              }
    
    # And create parameter values
    param_values = morris.sample(problem, 10, num_levels=4, optimal_trajectories=8,local_optimization=False)
    param_values = list(set([(p[0],p[1]) for p in param_values]))
    with open(parameter_combinations_file,"w+") as f:
        for p in range(len(param_values)):  
            f.write(f"{p},{param_values[p][0]},{param_values[p][1]}\n")
    
    f.close()

    num_blocks = len(param_values)

    with open("damage_results.txt","w+") as f:
        with open(parameter_combinations_file,"r") as r:
            for p in r:
                pv = p.split(",")
                f.write(f"{damage_results_folder},{network_csv},{hazard_csv},{damage_curves_csv},{hazard_damage_parameters_csv},{pv[0]},{pv[1]},{pv[2]}\n")
    
    f.close()

    # param_values = pd.read_csv("parameter_combinations.txt", sep=",")
    # num_blocks = len(param_values)
    # flood_protection_column = "None"
    # parameter_combinations_file = "parameter_combinations.txt"

    """Next we call the failure analysis script and loop through the failure scenarios
    """
    args = ["parallel",
            "-j", str(num_blocks),
            "--colsep", ",",
            "-a",
            "damage_results.txt",
            "python",
            "damage_calculations.py",
            "{}"
            ]
    print ("* Start the processing of damage calculations")
    print (args)
    subprocess.run(args)

    with open("ead_eael_results.txt","w+") as f:
        with open(parameter_combinations_file,"r") as r:
            for p in r:
                pv = p.split(",")
                f.write(f"{damage_results_folder},{network_csv},{hazard_csv},{flood_protection_column},{pv[0]},{pv[1]},{pv[2]}\n")
    
    f.close()

    """Next we call the EAD and EAEL analysis script and loop through the failure results
    """
    args = ["parallel",
            "-j", str(num_blocks),
            "--colsep", ",",
            "-a",
            "ead_eael_results.txt",
            "python",
            "ead_eael_calculations.py",
            "{}"
            ]
    print ("* Start the processing of EAD and EAEL calculations")
    print (args)
    subprocess.run(args)

    """Next we call the summary scripts
    """
    args = [
            "python",
            "damage_loss_summarised.py",
            f"{damage_results_folder}",
            f"{summary_folder}",
            f"{network_csv}",
            f"{parameter_combinations_file}"
            ]
    print ("* Start the processing of summarising damage results")
    print (args)
    subprocess.run(args)

    """Next we call the timeseries and NPV scripts
    """
    args = [
            "python",
            "damage_loss_timeseries_and_npv.py",
            f"{summary_folder}",
            f"{timeseries_results_folder}",
            f"{discounted_results_folder}",
            f"{network_csv}"
            ]
    print ("* Start the processing of timeseries and NPV calculations")
    print (args)
    subprocess.run(args)

                                
if __name__ == '__main__':
    CONFIG = load_config()
    main(CONFIG)