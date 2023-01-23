# from __future__ import absolute_import, division, print_function

import argparse
import sys
import logging
import pandas as pd
import os
import shutil
import json

from rt_utils import RTStructBuilder
import surface_distance

def move_file_folder():
    return

# TODO Check if it is correct to put a docstring after main and if I have to
# add Parameters and other stuff (initially this was in logging.info).
# TODO check if it is better to use logging messages or not (and how to 
# visualize them)
def main(argv):
    """Computation of Hausdorff distance (HD), volumetric Dice similarity 
    coefficient (volDSC) and surface Dice similarity coefficient (surfDSC) 
    between manual and automatic segmentations for pelvic structures.
    
    """
    # TODO Create the backbone of the script (open the dcm files), then add 
    #one new small piece at the time
                     
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description 
                                     = "HD, volDSC and surfDSC computation")
    parser.add_argument("-i", "--input-folder",
                        dest="input_folder_path",
                        metavar="PATH",
                        default=None,
                        required=True,
                        help="Path to the folder of input DICOM study/ies",
                        )
    # TODO maybe it is better to change the name otutput_folder
    parser.add_argument("-o", "--output-folder",
                        dest="output_folder_path",
                        metavar="PATH",
                        default=False,
                        required=False,
                        help="""Path where patient folders will be moved after
                             execution (optional)
                             """,
                        )
    
    args = parser.parse_args(argv)
        
    # TODO check if keep this or not
    # Check required arguments
    if args.input_folder_path == None:
        logging.warning('Please specify input DICOM study folder!')
     
    # Convert to python path style
    input_folder_path = args.input_folder_path.replace('\\', '/')
    output_folder_path = args.output_folder_path.replace('\\', '/')
    
    # Opening the json file where the lists of names are stored
    fd = open(r"C:\Users\Marco\Desktop\università\Magistrale\software_and_computing\project\config.json", "r")
    config = json.load(fd)
    
    # This lists do not change during execution so it is possible to assign
    # them to variables
    compared_methods = config["Compared methods"]
    mbs_segments = config["MBS segments"]
    dl_segments = config["DL segments"]
    alias_names = config["Alias names"]
    
    # TODO put some checks and alternatives if input_folder is already
    # patient_folder and if input_folder contains files and not only dir.
    patient_folders = [folder for folder in os.listdir(input_folder_path)]
    for patient_folder in patient_folders:
        patient_folder_path = os.path.join(input_folder_path,
                                           patient_folder,
                                           )
        
        # TODO put some checks in case folders or incorrect files are present
        # and if folder structure is different.
        # TODO if there are multiple CTs or CT and MR the iages should be
        # put in differet folders and selected one at the tima.
        # RTSTRUCT and DICOM series should be in different folders
        rtstruct_folder = "RTSTRUCT"
        rtstruct_folder_path = os.path.join(patient_folder_path,
                                            rtstruct_folder,
                                            )
        # FIXME if the folder already exists it will exit with an error
        os.mkdir(rtstruct_folder_path)
        dicom_series_folder = "DICOM"
        dicom_series_folder_path = os.path.join(patient_folder_path,
                                                dicom_series_folder,
                                                )
        # FIXME if the folder already exists it will exit with an error
        os.mkdir(dicom_series_folder_path)
        for file in os.listdir(patient_folder_path):
            file_path = os.path.join(patient_folder_path,
                                     file,
                                     )
            # TODO should be more general (maybe looking at the metadata)
            if os.path.isfile(file_path):
                if file.startswith("CT"):
                   shutil.move(file_path,
                               dicom_series_folder_path,
                               )
                elif file.startswith("RS"):
                   shutil.move(file_path,
                               rtstruct_folder_path,
                               )
                   rtstruct_file_path = os.path.join(rtstruct_folder_path,
                                                     file,
                                                     )
                else:
                    pass
            else:
                pass
            
        # Reading current patient files
        rtstruct = RTStructBuilder.create_from(dicom_series_folder_path, 
                                               rtstruct_file_path,
                                               )
        
        # Creates the list of manual segments
        all_segments = rtstruct.get_roi_names()
        manual_segments = [0 for i in range(len(alias_names))]
        for name in all_segments:
            if name in config["Prostate names"]:
                manual_segments[0] = name
            elif name in config["Rectum names"]:
                manual_segments[1] = name
            elif name in config["Bladder names"]:
                manual_segments[2] = name
            elif name in config["Left femur names"]:
                manual_segments[3] = name
            elif name in config["Right femur names"]:
                manual_segments[4] = name
            else:
                # TODO update name lists if the name is not present asking
                # to the user.
                continue
        
        # TODO should be subdivided into functions, and shoud be run also with
        # DL segments.
        # Computing HD, DSC and SDSC for every segment in manual and MBS lists
        for index in range(len(alias_names)):
            
            # TODO automatic extraction of the contour is needed
            # Binary labelmap creation
            reference_segment_labelmap = rtstruct.get_roi_mask_by_name(manual_segments[index])
            segment_to_compare_labelmap = rtstruct.get_roi_mask_by_name(mbs_segments[index])
        
            # TODO must be extracted from images, and see if it is better to put
            # it in another part of the code.
            voxel_spacing_mm = [0.977, 0.977, 3]
            
            # TODO shorten names
            # Metrics computation
            surf_dists = surface_distance.compute_surface_distances(reference_segment_labelmap,
                                                                    segment_to_compare_labelmap,
                                                                    voxel_spacing_mm,
                                                                    )
            surface_dice = surface_distance.compute_surface_dice_at_tolerance(surf_dists,
                                                                              tolerance_mm=3,
                                                                              )
            print(patient_folder,alias_names[index],"surface Dice:",surface_dice)
            hausdorff_distance = surface_distance.compute_robust_hausdorff(surf_dists,
                                                                           percent=95,
                                                                           )
            print(patient_folder,alias_names[index],"95% Hausdorff distance:",hausdorff_distance,"mm")
            volume_dice = surface_distance.compute_dice_coefficient(reference_segment_labelmap,
                                                                    segment_to_compare_labelmap,
                                                                    )
            print(patient_folder,alias_names[index],"volumetric Dice:",volume_dice)
            
        
        # TODO check if this indentation can be acceptable
        # Moving patient folder to a different location, if the destination
        # folder does not exist it will be automatically created.
        if output_folder_path:
            shutil.move(patient_folder_path,
                        os.path.join(output_folder_path, patient_folder),
                        )
            #TODO this should not be a print and should be shorter
            print(f"{patient_folder} successfully moved to {output_folder_path}")
        else:
            pass
        
                     

if __name__ == "__main__":
    main(sys.argv[1:])