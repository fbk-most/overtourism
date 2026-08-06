import subprocess

import sys
sys.path.insert(0,'../../')


from data_preparation.diffusion.init_Data import init_Data
from data_preparation.diffusion.main_diffusione_1_2 import main_diffusione_1_2

def prepare_data():
    print("Preparing data for diffusion model...")
    init_Data()
    main_diffusione_1_2()
    subprocess.run(["python3", "data_preparation/diffusion/main_diffusione_3.py", "--choose_case_pipeline", "--case_pipeline", "weekday"])


if __name__ == "__main__":
    prepare_data()