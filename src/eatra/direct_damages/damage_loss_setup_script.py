"""This script allows us to select and parallelise the Damage and Loss estimations on a server with multiple core processors
"""
import os
import sys
import ujson
from SALib.sample import morris
import SALib.analyze.morris 
from analysis_utils import *
import subprocess 

def get_adaptation_options():
    adaptation_options = [
        {
            "num":"None",
            "option":"no_adaptation",
            "folder_name":"risk_results",
            "flood_protection":0
        },
        {
            "num":0,
            "option":"swales",
            "folder_name":"adaptation_option_0",
            "flood_protection":1.0/0.1
        },
        {
            "num":1,
            "option":"spillways",
            "folder_name":"adaptation_option_1",
            "flood_protection":1.0/0.1
        },
        {
            "num":2,
            "option":"embankments",
            "folder_name":"adaptation_option_2",
            "flood_protection":0
        },
        {
            "num":3,
            "option":"floodwall",
            "folder_name":"adaptation_option_3",
            "flood_protection":1.0/0.02
        },
        {
            "num":4,
            "option":"drainage",
            "folder_name":"adaptation_option_4",
            "flood_protection":1.0/0.02
        },
        {
            "num":5,
            "option":"upgrading",
            "folder_name":"adaptation_option_5",
            "flood_protection":0
        }
    ]

    return adaptation_options

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

    adaptation_options = get_adaptation_options() 
    generate_new_parameters = False
    generate_direct_damages = False
    generate_EAD_EAEL = True
    generate_summary_results = True
    generate_timeseries = True
    for option in adaptation_options:
        folder_name = option['folder_name']
        results_folder = os.path.join(results_path,folder_name)
        if os.path.exists(results_folder) == False:
            os.mkdir(results_folder)
        
        damage_results_folder = f"{folder_name}/direct_damages"
        summary_folder = f"{folder_name}/direct_damages_summary"
        timeseries_results_folder = f"{folder_name}/loss_damage_timeseries"
        discounted_results_folder = f"{folder_name}/loss_damage_npvs"
        
        # Rework the networks file and write it to a new path
        networks = pd.read_csv(network_csv)
        network_csv = os.path.join(results_folder,
                                "network_layers_hazard_intersections_details.csv")
        networks.to_csv(network_csv,index=False)
        del networks
        
        # Rework the networks file and write it to a new path
        hazards = pd.read_csv(hazard_damage_parameters_csv)
        hazards = hazards[hazards["hazard_type"] == "flooding"]
        hazards["flood_protection"] = option['flood_protection']
        hazard_damage_parameters_csv = os.path.join(results_folder,
                                "hazard_damage_parameters.csv.csv")
        hazards.to_csv(hazard_damage_parameters_csv,index=False)
        del hazards

        parameter_combinations_file = "parameter_combinations.txt"
        if generate_new_parameters is True:
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
        else: 
            param_values = pd.read_csv("parameter_combinations.txt", sep=",")
        
        num_blocks = len(param_values)

        with open("damage_results.txt","w+") as f:
            with open(parameter_combinations_file,"r") as r:
                for p in r:
                    pv = p.split(",")
                    f.write(f"{damage_results_folder},{network_csv},{hazard_csv},{damage_curves_csv},{option['num']},{hazard_damage_parameters_csv},{pv[0]},{pv[1]},{pv[2]}")
        
        f.close()

        

        """Next we call the failure analysis script and loop through the failure scenarios
        """
        if generate_direct_damages is True:
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

        print(f"Done with direct damage calculations for {option['option']}")
        
        flood_protection = option["flood_protection"]
        flood_protection_column = option["option"]
        with open("ead_eael_results.txt","w+") as f:
            with open(parameter_combinations_file,"r") as r:
                for p in r:
                    pv = p.split(",")
                    f.write(f"{damage_results_folder},{network_csv},{hazard_csv},{flood_protection},{flood_protection_column},{pv[0]},{pv[1]},{pv[2]}")
        
        f.close()

        """Next we call the EAD and EAEL analysis script and loop through the failure results
        """
        if generate_EAD_EAEL is True:
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
        if generate_summary_results is True:
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
        if generate_timeseries is True:
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