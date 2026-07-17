import os
from collections import defaultdict
# Setting the base dir of the project: alternative to export echo $PROJECT_DIR and os.environ["PROJECT_DIR"]
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))                # Path to the project NOTE: __file__ is (builtin to the python interpreter) the path to the current file   
class StructureProject:
    """
    This class is used to structure the project by defining the base directories of the project
    @param _dir_basedata: str -> Path to the data directory (where the data is stored)
    NOTE: This contains the base structure of the directories that the project will need. As the project grows, more directories will be added, 
    and the constructor updated with input more variables that represent the analysis. In this way both the data and the output will represent the 
    idea that is being developed.
    NOTE: The principle of usage of this object is that every time we save something, we want to have it in some directory that reflects the scope of it.
    For example, suppose that you have trajectories of ants and you would like to test some measure related to the trajectories changing the parameters of pre-processing
    of those trajectories, then the parameter would be a branch.
    """
    def __init__(self,name_data,name_output,name_scripts,name_config):
        self._all_dirs = defaultdict()
        self._all_dirs["base_data"] = os.path.join(PROJECT_DIR, name_data)
        self._all_dirs["base_output"] = os.path.join(PROJECT_DIR, name_output)
        self._all_dirs["base_scripts"] = os.path.join(PROJECT_DIR, name_scripts)
        self._all_dirs["base_config"] = os.path.join(PROJECT_DIR, name_config)
        if not os.path.exists(self._all_dirs["base_data"]):
            os.makedirs(self._all_dirs["base_data"])
        if not os.path.exists(self._all_dirs["base_output"]):
            os.makedirs(self._all_dirs["base_output"])
        if not os.path.exists(self._all_dirs["base_scripts"]):
            os.makedirs(self._all_dirs["base_scripts"])
        if not os.path.exists(self._all_dirs["base_config"]):
            os.makedirs(self._all_dirs["base_config"])
    
    def _branch_dir_tree(self, key_to_branch, branch_name):
        """
            @param key_to_branch: str -> Key of the directory to branch
            @param branch_name: str -> Name of the branch to create
            @description: This function is used to create a branch in the directory tree
            NOTE: 
        """    
        self._all_dirs[branch_name] = os.path.join(self._all_dirs[key_to_branch], branch_name)
        if not os.path.exists(self._all_dirs[branch_name]):
            os.makedirs(self._all_dirs[branch_name])

    def _get_directory(self, key):
        """
            @param key: str -> Key of the directory to get
            @return: str -> Path to the directory
        """
        return self._all_dirs[key]
    
## Example of usage
if __name__=="__main__":
    # parameter set 0
    parameters0 = [0,1,3,8,9,10]
    parameter0_2_brance_name = {i:"par0_"+ str(i) for i in parameters0}
    # parameter set 1
    parameters1 = [0.1,1.2,3.122,8.111,9.5465,10.124]
    parameter1_2_brance_name = {i:"par1_"+ str(i) for i in parameters1}
    sp = StructureProject()
    # NOTE: Pay attention that 
    for i in parameters0:
        sp._branch_dir_tree("base_data", parameter0_2_brance_name[i])
        ## Do something with the directory
        for j in parameters1:
            sp._branch_dir_tree(parameter0_2_brance_name[i], parameter1_2_brance_name[j])
            ## Do something with the directory

## NOTE: this is an example on how you can easily construct the structure of the project