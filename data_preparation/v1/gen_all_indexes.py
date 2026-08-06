from data_preparation import gen_capacity_indexes, gen_diffusion_indexes, gen_overtourism_indexes, gen_hidden_indexes, gen_geojson

def main():
    gen_capacity_indexes.main()
    gen_diffusion_indexes.main()
    gen_overtourism_indexes.main()
    gen_hidden_indexes.main()
    gen_geojson.main()

def local():
    gen_capacity_indexes.local()
    gen_diffusion_indexes.local()
    gen_overtourism_indexes.local()
    gen_hidden_indexes.local()
    gen_geojson.local()

if __name__ == ("__main__"):
    local()