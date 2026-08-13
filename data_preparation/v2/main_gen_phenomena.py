from diffusion.main_generate_flows_and_grids import main_generate_flows_and_grids
import gen_phenomenon_dataframes

if __name__ == "__main__":
    main_generate_flows_and_grids(local = False)
    gen_phenomenon_dataframes.main()