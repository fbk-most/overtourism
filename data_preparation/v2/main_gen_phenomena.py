from diffusion.main_generate_flows_and_grids import main_generate_flows_and_grids
from gen_phenomenon_dataframes import main as generate_df

if __name__ == "__main__":
    main_generate_flows_and_grids(local = False)
    generate_df()