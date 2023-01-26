# from __future__ import absolute_import, division, print_function

import argparse
import sys
import logging
import pandas as pd
import os
import shutil
import json

import pydicom
from rt_utils import RTStructBuilder
import surface_distance as sd


# TODO rewrite the docstring
def is_empty(folder_path):
    """
    Checks if the folder is empty or not.
    
    #more detailed description (if needed)

    Parameters
    ----------
    folder_path : TYPE
        DESCRIPTION.

    Returns
    -------
    int
        DESCRIPTION.

    """
    if len(os.listdir(folder_path)) == 0:
        return 1
    else:
        return 0
    
def patient_info(rtstruct_file_path,
                 information,
                 ):
    """
    Extracts patient informations from RTSTRUCT file.
    
    #more detailed description (if needed)

    Parameters
    ----------
    rtstruct_file_path : TYPE
        DESCRIPTION.
    info_needed : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    rtstruct_dataset = pydicom.dcmread(rtstruct_file_path)
    info = rtstruct_dataset[information].value
    return info

def voxel_spacing(ct_folder_path):
    """
    Computing voxel spacing.
    
    #more detailed description (if needed)

    Parameters
    ----------
    ct_folder_path : TYPE
        DESCRIPTION.

    Returns
    -------
    voxel_spacing_mm : TYPE
        DESCRIPTION.

    """
    ct_images = os.listdir(ct_folder_path)
    slices =[pydicom.read_file(ct_folder_path+"/"+s, force=True) for s in ct_images]
    slices = sorted(slices, key=lambda x:x.ImagePositionPatient[2])
    pixel_spacing_mm = list(map(float, slices[0].PixelSpacing._list))
    slice_thickness_mm = float(slices[0].SliceThickness)
    voxel_spacing_mm = pixel_spacing_mm.copy()
    voxel_spacing_mm.append(slice_thickness_mm)
    return voxel_spacing_mm

def extract_manual_segments(patient_data,
                            alias_names,
                            mbs_segments,
                            dl_segments,
                            config,
                            ):
    """
    Creating the list of manual segments.
    
    #more detailed description (if needed)

    Parameters
    ----------
    patient_data : TYPE
        DESCRIPTION.
    alias_names : TYPE
        DESCRIPTION.
    mbs_segments : TYPE
        DESCRIPTION.
    dl_segments : TYPE
        DESCRIPTION.
    config : TYPE
        DESCRIPTION.
     : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    # TODO put some code to handle the case in which one or more of the
    # OARs is not present.
    # Creates the list of manual segments
    all_segments = patient_data.get_roi_names()
    manual_segments = [0 for i in range(len(alias_names))]
    for name in all_segments:
        if name in mbs_segments:
            continue
        elif name in dl_segments:
            continue
        elif name in config["Prostate names"]:
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
            to_keep = input(f"Do you want to keep {name}? Enter Y (yes) or N (no) \n").upper()
            # TODO put some code to handle the case in which the user
            # provides the wrong input, and see if there is a better way
            # to write the following if-else.
            if to_keep == "Y":
                # TODO check if it is correct to print on the standard
                # output, if it correct how I wrote the code and put some
                # check to the input provided by the user.
                what_is = input(f"To which alias name is {name} associated? Enter P (Prostate), A (Anorectum), B (Bladder), L (Left femur) or R (Right femur) \n").upper()
                if what_is == "P":
                    manual_segments[0] = name
                    config["Prostate names"].append(name)
                    print(name,"added to Prostate names in config.json")
                elif what_is == "A":
                    manual_segments[1] = name
                    config["Rectum names"].append(name)
                    print(name,"added to Rectum names in config.json")
                elif what_is == "B":
                    manual_segments[2] = name
                    config["Bladder names"].append(name)
                    print(name,"added to Bladder names in config.json")
                elif what_is == "L":
                    manual_segments[3] = name
                    config["Left femur names"].append(name)
                    print(name,"added to Left femur names in config.json")
                elif what_is == "R":
                    manual_segments[4] = name
                    config["Right femur names"].append(name)
                    print(name,"added to Right femur names in config.json")
            elif to_keep == "N":
                continue
    return manual_segments

def compute_metrics(patient_data,
                    reference_segment,
                    segment_to_compare,
                    voxel_spacing_mm):
    """
    Computing Hausdorff distance (hd), volumetric Dice similarity coefficient
    (dsc) and surface Dice similarity coefficient (sdsc).
    
    #more detailed description (if needed)

    Parameters
    ----------
    patient_data : TYPE
        DESCRIPTION.
    reference_segment : TYPE
        DESCRIPTION.
    segment_to_compare : TYPE
        DESCRIPTION.
    voxel_spacing_mm : TYPE
        DESCRIPTION.

    Returns
    -------
    surface_dice : TYPE
        DESCRIPTION.
    volume_dice : TYPE
        DESCRIPTION.
    hausdorff_distance : TYPE
        DESCRIPTION.

    """
    # Binary labelmap creation
    reference_labelmap = patient_data.get_roi_mask_by_name(reference_segment)
    compared_labelmap = patient_data.get_roi_mask_by_name(segment_to_compare)
    
    # Metrics computation
    surf_dists = sd.compute_surface_distances(reference_labelmap,
                                              compared_labelmap,
                                              voxel_spacing_mm,
                                              )
    
    surface_dice = sd.compute_surface_dice_at_tolerance(surf_dists,
                                                        tolerance_mm=3,
                                                        )
    
    volume_dice = sd.compute_dice_coefficient(reference_labelmap,
                                              compared_labelmap,
                                              )
    
    hausdorff_distance = sd.compute_robust_hausdorff(surf_dists,
                                                     percent=95,
                                                     )
    return surface_dice, volume_dice, hausdorff_distance
    

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
    # TODO use more prints to make the user know whats going on during
    # execution (then see if it is better to use print, log messages or other)
    # TODO printed messages must be checked and rewritten in the correct way
                     
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
    parser.add_argument("-c", "--config-path",
                        dest="config_path",
                        metavar="PATH",
                        default=None,
                        required=True,
                        help="Path to the configuration json file",
                        )
    parser.add_argument("-e", "--excel-path",
                        dest="excel_path",
                        metavar="PATH",
                        default=None,
                        required=True,
                        help="""Path to the .xlsx file (if not present it will
                             be automatically created
                             """,
                        )
    parser.add_argument("-n", "--new-folder",
                        dest="new_folder_path",
                        metavar="PATH",
                        default=False,
                        required=False,
                        help="""Path where patient folders will be moved after
                             execution (optional)
                             """,
                        )
    parser.add_argument("-j", "--join-data",
                        dest="join_data",
                        metavar=bool,
                        default=False,
                        required=False,
                        help="Join previously extracted data with new ones",
                        )
    
    args = parser.parse_args(argv)
        
    # TODO check if keep this or not
    # Check required arguments
    if args.input_folder_path == None:
        logging.warning("Please specify input DICOM study folder!")
    if args.config_path == None:
        logging.warning("Please specify where is the configuration file!")
    if args.excel_path == None:
        logging.warning("""Please specify the location of
                        .xlsx file where data will be stored
                        """,
                        )
     
    # Convert to python path style
    input_folder_path = args.input_folder_path.replace("\\", "/")
    new_folder_path = args.new_folder_path.replace("\\", "/")
    config_path = args.config_path.replace("\\", "/")
    excel_path = args.excel_path.replace("\\", "/")
    
    # If true new data will be concatenated with old ones
    join_data = args.join_data
    
    # Opening the json file where the lists of names are stored
    fd = open(config_path)
    config = json.load(fd)
    
    # Extracting compared segmentation methods, mbs, dl and alias segments
    # names.
    compared_methods = config["Compared methods"]
    mbs_segments = config["MBS segments"]
    dl_segments = config["DL segments"]
    alias_names = config["Alias names"]
    
    # List where final data will be stored.
    final_data = []
    
    # If join_data is True, old data will be extracted from excel_path,
    # otherwise the old excel file will be overwritten.
    if join_data:
        try:
            # loading existing data
            old_data = pd.read_excel(excel_path)
            print(f"Successfully loaded {excel_path}")
            excel_file_exist = 1
        except: # TODO find the correct exception
            # TODO check if it is correct to use print
            # There is not an existing excel file in excel path
            print(f"Failed to load {excel_path}, a new file will be created")
            excel_file_exist = 0
    else:
        print(f"""Excel file at {excel_path} will be overwritten if already
              present, otherwise it will be created.""")
    
    # Check that input folder is not empty
    if is_empty(input_folder_path):
        sys.exit(f"{input_folder_path} is empty, aborting execution")
    
    # Check that input folder contains patient folders
    patient_folders = []
    for folder in os.listdir(input_folder_path):
        # Only patient folders are needed, other files are skipped
        if not os.path.isfile(os.path.join(input_folder_path,folder)):
            patient_folders.append(folder)
    if len(patient_folders) == 0:
        sys.exit(f"""{input_folder_path} does not contain folders.
                 Be sure to provide as input the folder that contains the
                 patients and not directly dcm files.
                 Aborting execution
                 """,
                 )
    
    # Selecting one patient at the time and analyzing it
    for patient_folder in patient_folders:
        patient_folder_path = os.path.join(input_folder_path,
                                           patient_folder,
                                           )
        
        # Checking that patient folder is not empty
        if is_empty(patient_folder_path):
            sys.exit(f"{patient_folder_path} is empty, aborting execution")
        
        # RTSTRUCT and DICOM series should be in different folders.
        # Creating RTSTRUCT folder if it is not already present, otherwise
        # going on with execution.
        rtstruct_folder = "RTSTRUCT"
        rtstruct_folder_path = os.path.join(patient_folder_path,
                                            rtstruct_folder,
                                            )
        try:
            os.mkdir(rtstruct_folder_path)
        except FileExistsError:
            pass
        
        # Creating CT folder if it is not already present, otherwise
        # going on with execution
        ct_folder = "CT"
        ct_folder_path = os.path.join(patient_folder_path,
                                                ct_folder,
                                                )
        try:
            os.mkdir(ct_folder_path)
        except FileExistsError:
            pass
        
        # Filling CT and RTSTRUCT folder if both empty
        if (is_empty(rtstruct_folder_path) and is_empty(ct_folder_path)):
            print("""Moving CT.dcm files into CT folder and RS.dcm files into
                  RTSTRUCT folder""")
            for file in os.listdir(patient_folder_path):
                file_path = os.path.join(patient_folder_path,
                                         file,
                                         )
                if os.path.isfile(file_path):
                    if file.startswith("CT"):
                        shutil.move(file_path,
                                    ct_folder_path,
                                    )
                    elif file.startswith("RS"):
                        shutil.move(file_path,
                                    rtstruct_folder_path,
                                    )  
                    else:
                        pass
                else:
                    pass
        # Exit to not mix different data
        elif is_empty(rtstruct_folder_path):
            sys.exit("""Only RTSTRUCT folder is empty. Aborting execution
                     to not mix different data. Check the data and try
                     again""")
        # Exit to not mix different data
        elif is_empty(ct_folder_path):
            sys.exit("""Only CT folder is empty. Aborting execution to not
                     mix different data. Check the data and try again""")
        # Going on if both folders have already data inside, to not merge
        # different data
        else:
            print("""Both RTSTRUCT and CT folders have already files in them.
                  Thus, no files will be moved""")
            pass
        
        # Check if RTSTRUCT or CT folders are still empty
        if (is_empty(rtstruct_folder_path) and is_empty(ct_folder_path)):
            sys.exit("""CT.dcm and/or RS.dcm files not available. Aborting
                     execution. Check the data and try again""")
        
        # Extracting rtstruct file path
        for file in os.listdir(rtstruct_folder_path):
            rtstruct_file_path = os.path.join(rtstruct_folder_path,
                                                     file,
                                                     )
            
        # Extraction of patient ID and frame of reference UID
        patient_id = patient_info(rtstruct_file_path,
                                  "PatientID",
                                  )
        frame_of_reference_uid = patient_info(rtstruct_file_path,
                                              "FrameOfReferenceUID",
                                              )
        
        # If join_data is True we need to check if the current study is
        # already in the dataframe and if it is to skip it. Otherwise no
        # checks are needed and every study will be analyzed. 
        if join_data:
            # If the excel file exists checks if the current frame of
            # reference uid is already saved there.
            if excel_file_exist:
                for frame_of_reference in old_data.loc[:,"Frame of reference"]:
                    if frame_of_reference == frame_of_reference_uid:
                        print("""This study is alreday in the dataframe, going
                              to the next one
                              """,
                              )
                        frame_uid_in_old_data = True
                        break
                    else:
                        frame_uid_in_old_data = False
                if frame_uid_in_old_data:
                    # TODO move patient folder in patient_used
                    continue
            else:
                # There is not an old dataframe beacuse in excel_path there is
                # not an existing excel file. We can go on with the current
                # patient.
                pass
                        
        # Extracting voxel spacing (here and and not in compute_metrics
        # because it is always the same for one patient and it does not make
        # sense to compute it more than once)
        voxel_spacing_mm = voxel_spacing(ct_folder_path)
            
        # Reading current patient files
        patient_data = RTStructBuilder.create_from(ct_folder_path, 
                                               rtstruct_file_path,
                                               )
        
        manual_segments = extract_manual_segments(patient_data,
                                                  alias_names,
                                                  mbs_segments,
                                                  dl_segments,
                                                  config,
                                                  )
        
        # Reference and compared segments lists.
        # With these lists it is possible to use a for loop to perform
        # manual-MBS, manual-DL and MBS-DL comparisons.
        ref_segs = [manual_segments,
                    manual_segments,
                    mbs_segments,
                    ]
        comp_segs = [mbs_segments,
                     dl_segments,
                     dl_segments,
                     ]
        
        # Computing HD, DSC and SDSC for every segment in manual and MBS lists.
        for methods in range(len(compared_methods)):
            # TODO maybe print some message to let the user know what's going
            # on and extract here values to store that are not segment
            # dependent, and clean the code.
            
            
            for segment in range(len(alias_names)):
                # Computing surface Dice similarity coefficient (sdsc), Dice
                # similarity coefficient (dsc) and Hausdorff distance (hd)
                sdsc, dsc, hd = compute_metrics(patient_data,
                                                ref_segs[methods][segment],
                                                comp_segs[methods][segment],
                                                voxel_spacing_mm,
                                                )
                
                # Creating a temporary list to store the current row of the
                # final dataframe.
                row_data = [patient_id,
                            frame_of_reference_uid,
                            compared_methods[methods],
                            ref_segs[methods][segment],
                            comp_segs[methods][segment],
                            alias_names[segment],
                            hd,
                            dsc,
                            sdsc,
                            ]
                
                # Adding the constructed raw to final_data
                final_data.append(row_data)
      
        # TODO check if this indentation can be acceptable
        # Moving patient folder to a different location, if the destination
        # folder does not exist it will be automatically created.
        if new_folder_path:
            shutil.move(patient_folder_path,
                        os.path.join(new_folder_path, patient_folder),
                        )
            #TODO this should not be a print and should be shorter
            print(f"{patient_folder} successfully moved to {new_folder_path}")
        else:
            pass
        
    # Creating the dataframe
    new_dataframe = pd.DataFrame(final_data,
                             columns=["Patient ID",
                                      "Frame of reference",
                                      "Compared methods",
                                      "Reference segment name",
                                      "Compared segment name",
                                      "Alias name",
                                      "95% Hausdorff distance (mm)",
                                      "Volumetric Dice similarity coefficient",
                                      "Surface Dice similarity coefficient",
                                      ],
                             )
    
    if join_data:
        try:
            # Concatenating old and new dataframes
            frames = [old_data, new_dataframe]
            new_dataframe = pd.concat(frames, ignore_index=True)
            print("Old and new dataframe concatenated")
        except NameError:
            print("""There is not an old dataframe, concatenation not
                  performed""")
        
    
    # Saving dataframe to excel
    new_dataframe.to_excel(excel_path, sheet_name="Data", index=False)
     
    # TODO check if it is better to change names
    # Updating config.json
    json_object = json.dumps(config, indent=4)
    with open(config_path, "w") as outfile:
        outfile.write(json_object)
    
    # with open(r"C:\Users\Marco\Documents\tirocinio\scripting_3DSlicer\config.json", "w") as outfile:
    #     outfile.write(json_object)
        
                     

if __name__ == "__main__":
    main(sys.argv[1:])