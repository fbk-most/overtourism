# Scripts Over-Tourism Analysis

This folder contains Jupyter notebooks and Python modules for analyzing over-tourism patterns using mobility data, specifically focused on Vodafone telecommunication data and various tourism-related datasets.    


## Overview
The analysis proposed is split in two, exploring solutions to two different task that we call `diffusion 1,2` and `diffusion 3`.   
For the first case we implement a hierarchical mobility framework to identify critical tourism flows and hotspots in the Trentino region.    
The workflow for `diffusion 1,2` processes raw OD data from multiple sources to generate mobility hierarchies, flux analysis, and interactive visualizations. The main script that does that is `main_diffusione_1_2.py` and is inspired by:    
Hierarchical organization of urban mobility and its connection with city livability.   
Bassolas et al.   
The workflow for `diffusion 3` processes raw presences data from multiple sources to inform Markowitz like strategy for presences distributions.   
This technique considers presences with respect to average non-touristic presences (October) to be returns (in portfolio lenguage), and minimizes the variance (risk of overtourism) of presences constrained 

## Description of the pipeline Diffusion 1,2
## Hierarchical Flow Analysis  

The analysis we propose is a **hierarchical analysis of flows**.  
At the level of each `comune` (the polygons from the shapefile of the Trentino region), we non-parametrically characterize the hierarchy of:  

- total incoming flows (`out_1_tot`)  
- total outgoing flows (`out_2_tot`)  

and, respectively, the hierarchy of their:  

- `sources` generating the total incoming flows  
- `sinks` receiving the total outgoing flows  

Each output is computed for different levels of **aggregation** (see section `(TCAD12)`).  

We consider two types of flows:  

- **Touristic flows**: aggregated over two weeks (Vodafone data) in July–August.  
- **Non-touristic flows**: representative of an average day in October.  

---

### Method  

For each `comune`, we compute the total incoming and outgoing flows and iteratively apply the **Loubar criterion** to identify the most critical hotspots.  

The **Lorenz curve** of total flows (incoming/outgoing) is defined as the ordered CDF:  

$$
\text{LorenzCurve} = 
\Bigl(i, \ 
CumulativeTotalFlows^{in/out}_i \ = \ \frac{\sum_{i' \leq i}\sum_j T_{i'j}^{in/out}}{\sum_{ij} T_{ij}^{in/out}} \Bigr)
$$

where the ordering is given by:  

$$
\sum_{j} T_{ij} > \sum_{j} T_{i'j} \quad \text{if} \quad i > i'
$$  

To assess criticality, we select indices located to the right of the intersection between the derivative of the Lorenz curve at $i = i_{max}$ and the axis:  

$$
CumulativeTotalFlows^{in/out}_i = 0
$$  

(see Overleaf documentation for details).  

At each iteration `iter`, we select a new set of indices. The iteration value itself encodes the **criticality level**:  
- `iter = 0`: maximum criticality  
- ...  
- `iter = iter_{max}`: minimum criticality (naming convention could be improved).  

---

### Interpretation  

Each `comune` is thus associated with a **hotspot level** corresponding to its criticality. This allows us to quantify:  
- how much of the population moves into a `comune` (incoming flows),  
- or how strongly a `comune` sends people elsewhere (outgoing flows).  

To identify the **drivers of these flows**, we reapply the hierarchical classification within each hotspot. For example:  
- Suppose `comune i` is identified as a level-0 hotspot in the incoming flow case.  
- We then classify the contributing `sources` (`comuni j`) whose flows drive the incoming traffic into `comune i`.  

This yields a set of **relevant fluxes** that capture the majority of mobility.  
For instance, if hotspot level 0 contains region 0 as a hotspot, and incoming flows originate from regions {1, 2, 3, 4, 5}, the Loubar criterion might retain {1, 3, 5} as the critical contributing flows.  

---

### Extension to Relative Flows  

So far, the analysis considers the **absolute size of flows**. However, the pipeline can be easily extended to relative flows, i.e., **increases with respect to a null model** (e.g. November baseline data).  

In this case, we study flows after subtracting the baseline. The analysis also distinguishes between **weekdays and weekends**, allowing a more refined picture of criticality in mobility dynamics.  

## Description of the pipeline Diffusion 3
### Mathematical formulation
We call October `non touristic period` and July and August the `touristic period`.
Presences are therefore considered separately as: 
- $\langle P^{oct}_{i}\rangle_t$ (averaged over all days in october) 
- $P_i(t)$ for any touristic day.   

We define the return as:   
    $\Delta P_i(t) = \langle P^{oct}_{i} \rangle- P_i(t)$    
the observed deviation from the non-over-touristic presences.    
Overtouristic regimes are defined as: $\Delta P_i(t) \ll 0$.    

We define the risk as:    
$R = \sum_{i,j}^{|Polygons|} w_i \Sigma_{ij} w_j = \frac{1}{T}\sum_{i,j}^{|Polygons|} \sum_{t = 1}^{T}  w_i\Delta P_i(t)  w_j\Delta P_j(t)$   
Markowitz problem is the optimization problem that wants to minimize risk by constraining the the expected return and fixing a total amount of budget and mathematically expressed as:   
$w^{*}, \lambda^{*}, \gamma^{*} = \min_{w,\lambda, \gamma} \mathcal{L}(w, \lambda, \gamma) =
\frac{1}{2} w^\top \Sigma w+ \lambda \left( \mathbf{1}^\top w - 1 \right)+ \gamma \left( \langle\Delta P_i(t)^\top \rangle_t w - G \right)$   
where $G = \sum_i \langle\Delta P_i(t) \rangle_t$ and the equation 
is solved by:   
$w^\star = \Sigma^{-1}\left[a \mathbf{1} +  b\langle\Delta P\rangle_t  \right].$

### Selecting reliable data: Random matrix approach
The Markowitz approach is defined using the empirical correlation matrix that can be noisy due to the small sampling and statistically not descriptive. To face this problem we cleaned the matrix using principles from Random matrix theory. 
The only parameter needed is $q = \frac{T}{N}$, that defines how much data we have in time with respect to the number of sources. Marchenko-Pastur, teach us that the eigenvalues of the matrix that has its entrances drawn completely independently expects the eigenvalues to be confined in the interval $[\lambda_{min},\lambda_{max}]$, where:   
$\lambda_{min} = \sigma^{2}\,\bigl(1 - \sqrt{q}\,\bigr)^{2}$, 
$\lambda_{max} = \sigma^{2}\,\bigl(1 + \sqrt{q}\,\bigr)^{2}$   
Therefore, we cannot rely on the eigenvalues that are within those bounds.  
We therefore apply a filtering to the matrix and define a cleaned version of it as:   
$C_{ij} = \sum_{\lambda > \lambda_{max}} \lambda \ket{u_{\lambda}}\bra{v_{\lambda}}$   
where:   
$\Sigma_{ij} = \sum_{\lambda} \lambda \ket{u_{\lambda}}\bra{v_{\lambda}}$





   



### Layman Interpretation
We consider each time $t' \in T_{presences}^{hour}$ and assume that, for the subsequent hours, the best estimate for the return is given by  

$\Delta P_i(t' + dt) = \langle \Delta P_i \rangle_t$

that is, the observed daily average computed over all days in the `touristic period`.

We now clarify the interpretation of the portfolio.  
The quantity $w_i$ represents the signed fraction of people ($N$) that the policy maker is assumed to have the ability to influence (for instance, through targeted advertising campaigns).  
When $\mathrm{sign}(w_i) < 0$, this means people are being moved away (selling), whereas $\mathrm{sign}(w_i) > 0$ indicates that people are being attracted (buying).

In this setting, the portfolio becomes a decision-making tool that allows the policy maker to address the following question:  
```    
How many people must be moved or attracted so that, given the expected average return, the risk of overtourism in the next time interval is minimized?  
In other words, how can we find a strategy that, on any given day, and a given hour, reduces the likelihood that these movements lead to overtourism?
```
It is important to note that this portfolio is an *average* instrument; it does not account for day-to-day variations or allow for tailored strategies for each individual day.  
The essence of this approach lies in the explicit assumption that we cannot reliably predict hour-to-hour fluctuations in presences from the available data.  
Therefore, we aim to minimize the risk of adverse outcomes given the *average* observed behavior.



# Main Components

## Usage

### Production Usage Diffusion 1,2
```
python3 ./init_Data.py
python3 ./main_diffusione_1_2.py   
```

### Production Usage Diffusion 3
`ALL CASES`: Run all the possible aggragation from the product of cases:  
```
python3 ./init_Data.py
python3 ./main_diffusione3.py
```
`ONE CASE`: choose the variables that need to be mantained not aggregated:
```
python3 ./init_Data.py
python3 ./main_diffusione3.py --choose_case_pipeline --case_pipeline "visitor_country"       
```


### Testing Usage: Notebook 

- [`main_diffusion_1_2.ipynb`](main_diffusion_1_2.ipynb): Diffusion 1,2 analysis notebook that implements the complete workflow for flux analysis on Vodafone geometries.  
- [debug_markowitz_all_aggregated.ipynb](debug_markowitz.ipynb): Diffusion 3 analysis notebook that implements the workflow for the portfolio optimization

## Configuration
The parameters that are important for the `overtourism` analysis are defined in:   
- `constant_name_variables.py`: Name all the columns, directories and variables dictated by either the structure of the project or the data in input.    
- `default_parameters.py`: Contain all the parameters that are held constant for the current pourposes but that can be changed to explore further configurations of the touristic system.   
- `set_config.py`: import the precedent modules and store data in dictionary to be saved for a run of the main
- `global_imports.py`: Contains all the necessary import for the project. Import this to import them all.

## Data Sources

The analysis connects to the AIxPA platform for the following data sets:

- **Vodafone_OD**: origin destination data aggregated over 15 days during July-August, and over 30 days in October    
- **Vodafone_presences**: Mobile phone presence data
- **vodafone_aree**: Geographic area definitions

## (TCAD12): Technical considerations about aggregation in Diffusione 1,2 
 
The aggregation routine is determined by the keys of the dictionary:
`conditioning_2_columns_to_hold_when_aggregating`   
Each key specifies which columns are preserved during grouping, and therefore defines the aggregation level of the pipeline. Each key is associated with a:
- `grid_all_columns_day_hour_user_weekday`: holding all the columns that are obtained by the combination of the cases (`Out-1`)   
- `Tij_all_columns_day_hour_user_weekday`: holding all the columns that are obtained by the combination of the cases (`Out-2`)   

Columns names (`Out-1`):   
- `"hotspot_level_tot_{suffix_in}_flows_{user_profile}_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}"`: index of the hotspot level  
- `"tot_{suffix_in}_flows_{user_profile}_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}"`: contains the total number of flows per cell. (These are the columns that once were in the geodataframe.)   

Columns names (`Out-2`):   
- `"n_trips_{user_profile}_t_{str_t}_{str_t1}_{suffix_in}_w_{is_weekday}_d_{str_day}"`: number of trips per user type at time interval   
-`"n_trips_{user_profile}_t_{str_t}_{str_t1}_baseline_{suffix_in}_w_{is_weekday}_d_{str_day}"`: number flows that are from the baseline
- `"difference_baseline_{user_profile}_t_{str_t}_{str_t1}_baseline_{suffix_in}_w_{is_weekday}_d_{str_day}"`: number of flows that are in excess from the baseline. 


Keys and their meaning:   
-------------------------------------------------------------------------------

| Key                        | Columns retained                            |
|-----------------------------|---------------------------------------------|
| `day_hour_user_weekday`     | [`day`, `hour`, `user`, `weekday`]          |
| `hour_user_weekday`         | [`hour`, `user`, `weekday`]                 |
| `day_user_weekday`          | [`day`, `user`, `weekday`]                  |
| `day_hour_weekday`          | [`day`, `hour`, `weekday`]                  |
| `day_hour_user`             | [`day`, `hour`, `user`]                     |
| `day_weekday`               | [`day`, `weekday`]                          |
| `hour_weekday`              | [`hour`, `weekday`]                         |
| `user_weekday`              | [`user`, `weekday`]                         |
| `day_hour`                  | [`day`, `hour`]                             |
| `day_user`                  | [`day`, `user`]                             |
| `hour_user`                 | [`hour`, `user`]                            |
| `weekday`                   | [`weekday`]                                 |
| `day`                       | [`day`]                                     |
| `hour`                      | [`hour`]                                    |
| `user`                      | [`user`]                                    |
| `_`                         | [`_`]                                       |

-------------------------------------------------------------------------------
In summary, the dictionary keys control both the grouping logic (by fixing which columns remain) and the storage of outputs across the project dictionaries.




## Output Diffusione 1,2 after aggregation is applied
We have different levels of output that are characterized by the number of parameters that describe the context.   
The first kind depends just on the spatial subdivision we choose:     

- `Distance matrix` (saved as Parquet files) -> unique for all the analysis    

For each `day`:    
- `stops`: geojson -> `gdf_stops.geojson`    
- `grid 2 route`: json -> `grid_2_route.json`   
- `grid 2 stop`: json -> `grid_2_stop.json`   
- `stop 2 grid`: json -> `stop_2_grid.json`   
- `stop 2 route`: json -> `stop_2_route.json`   
- `stop 2 trip`: json -> `stop_2_trip.json`   
- `name stop 2 grid`: json -> `name_stop_2_grid.json`   
- `stop 2 grid`: json -> `stop_2_grid.json`   


For each `time interval` [`t_i`,`t_(i+1)`]:    
- `grid & bus`: geojson -> `grid_bus_{time interval}.geojson`   

For each `User Profile`:
- `Fluxes` DataFrame -> `fluxes_{User profile}_{time interval}.parquet` (mh.flows)
- `Presences` GeoDataFrame -> `grid_{User profile}_{time interval}.geojson` (mh.grid)     

For each `direction` {`in`,`out`}:     
- `Hierarchical hotspot` dictionary -> `hotspot_levels_{direction}_{User profile}_{time interval}.json`
- `Hierarchical hotspot bus` dictionary -> `hotspot_levels_{direction}_bus_{time interval}.json`
- `Interactive critical flows`: map -> `map_fluxes_{User Profile}_{time interval}_{direction}.html`      
- `Interactive critical flows bus`: map -> `map_fluxes_bus_{time interval}_{direction}.html`      
- `Interactive hotspots`: map -> `hierarchy_{User Profile}_{time interval}_{direction}.html`      
- `Interactive hotspots bus`: map -> `hierarchy_bus_{time interval}_{direction}.html`      

- `most critical directions`: map -> `most_critical_directions_{User Profile}_{time interval}_{day}.html`    
- `direction need bus`: map -> `need_for_bus_{time interval}_{day}.html`


### Description Output Diffusione 1,2

`Distance Matrix`: cols -> i	j	dir_vector	distance       
- i : `str_col_origin` (NOTE: name set in set_config)       
- j : `str_col_destination` (NOTE: name set in set_config)       
- dir_vector: unit vector linking centroid i,j     
- distance: distance between centroid i,j   

For each `time interval` and `User Profile` in [`COMMUTER`,`INHABITANT`,`TOURIST`,`VISITOR`],     
`Fluxes`: cols -> i	j	dir_vector	distance	population_i	population_j	n_trips_{`User Profile`}_t_{`t_i`}_{`t_(i+1)`}	n_trips_bus_{`t_i`}_{`t_(i+1)`}    
- i : `str_col_origin`: int -> idx of the geometry that tessellate the area of interest (NOTE: name set in set_config)       
- j : `str_col_destination`: int -> idx of the geometry that tessellate the area of interest (NOTE: name set in set_config)       
- dir_vector: unit vector linking centroid i,j        
- distance: distance between centroid i,j     
- population_i: `str_population_origin`: int -> population of the geometry that tessellate the area of interest    
- population_j: `str_population_destination`: int -> population of the geometry that tessellate the area of interest
- n_trips_{`User Profile`}_t_{`t_i`}_{`t_(i+1)`}: int -> number of fluxes measured from Vodafone Data (or generated by )
- n_trips_bus_{`t_i`}_{`t_(i+1)`}: int -> number of people that can be transported by bus from O to D depending on `int_number_people_per_bus` = 50        

`Presences`: cols -> 'AREA_LABEL', 'geometry','Popolazione_Totale', 'area', 'total_area_by_name','fraction_area', 'centroid_lat', 'centroid_lon',
       'tot_in_flows_{`User Profile`}_t_{`t_i`}_{`t_(i+1)`}','hotspot_level_tot_in_flows_{`User Profile`}_t_{`t_i`}_{`t_(i+1)`}',
       'tot_out_flows_{`User Profile`}_t_{`t_i`}_{`t_(i+1)`}','hotspot_level_tot_out_flows_{`User Profile`}_t_{`t_i`}_{`t_(i+1)`}', 'grid_id',
       'n_stops_{`t_i`}_{`t_(i+1)`}', 'is_roads_inside_droppable'        
- AREA_LABEL: name of the area (ex. San Martino di Castrozza)    
- geometry: polygon    
- Popolazione_Totale: int -> population according to Istat    
- area: area in m^2    
- total_area_by_name: area in m^2 (useful when a city is subdivided in multiple zones: Trento, Rovereto)    
- 'tot_in_flows_{`User Profile`}_t_{`t_i`}_{`t_(i+1)`}': sum of all the incoming flows    
- 'tot_out_flows_{`User Profile`}_t_{`t_i`}_{`t_(i+1)`}': sum of all the outgoing flows    
- 'hotspot_level_tot_out_flows_{`User Profile`}_t_{`t_i`}_{`t_(i+1)`}: hotspot level (0 most critical - 4 least, -1 if least of the least)    
- `str_grid_idx`: int -> index of the grid from 0 to n_cells     
- n_stops_{`t_i`}_{`t_(i+1)`}: int -> number of stops that are within the grid    


`Hierarchical hotspot (in and out)`: 
{`hotspot level`: [int_index_origin/destination]} -> `hotspot level` in {0,1,2,3,4}    

## Diffusione 3

We have different levels of output characterized by the number of parameters 
that describe the context of the Markowitz portfolio analysis.

The aggregation routine is determined by the keys of the dictionary 
`case2column_names_diffusione_3`, which is generated from all possible 
combinations of the conditioning variables:

    - `time`: `TIME_BLOCK_ID` (hourly analysis)
    - `visitor`: `VISITOR_CLASS_ID` (visitor type classification)
    - `country`: `COUNTRY` (nationality-based analysis)
    - `weekday`: `is_weekday` (weekday/weekend distinction)

Each key specifies which columns are preserved during grouping, and therefore 
defines the aggregation level of the pipeline. Each key is associated with:

    • Portfolio weight maps and analysis outputs
    • Expected return and risk calculations
    • Cleaned covariance matrices using Random Matrix Theory (RMT)

-------------------------------------------------------------------------------
Column Name Structure
-------------------------------------------------------------------------------

For each combination of conditioning variables, the following columns are 
generated with the pattern:

    `{metric}_{base}`  where     
    `base = "v_{visitor}_c_{country}_w_{is_weekday}_t_{time}"`   

Input Data Columns:   
    - `presences_{base}`: Aggregated presences for touristic period   
    - `presences_baseline_{base}`: Aggregated presences for October baseline

Markowitz Analysis Columns:   
    - `diff_oct_{base}`: Difference from October baseline (return measure)   
    - `diff_oct_mean0_{base}`: Mean-centered differences  
    - `diff_oct_mean0_var1_{base}`: Standardized differences (mean=0, var=1)  
    - `std_{base}`: Standard deviation of returns  
    - `exp_return_{base}`: Expected return for Markowitz optimization  
    - `cov_{base}`: Covariance matrix elements  
    - `portfolio_{base}`: Portfolio weights from Markowitz optimization  

-------------------------------------------------------------------------------
Aggregation Keys and Their Meaning
-------------------------------------------------------------------------------

| Key                          | Columns retained                                        |
|------------------------------|----------------------------------------------------------|
| `time`                       | [`TIME_BLOCK_ID`]                                       |
| `visitor`                    | [`VISITOR_CLASS_ID`]                                    |
| `country`                    | [`COUNTRY`]                                             |
| `weekday`                    | [`is_weekday`]                                          |
| `time_visitor`               | [`TIME_BLOCK_ID`, `VISITOR_CLASS_ID`]                   |
| `time_country`               | [`TIME_BLOCK_ID`, `COUNTRY`]                            |
| `time_weekday`               | [`TIME_BLOCK_ID`, `is_weekday`]                         |
| `visitor_country`            | [`VISITOR_CLASS_ID`, `COUNTRY`]                         |
| `visitor_weekday`            | [`VISITOR_CLASS_ID`, `is_weekday`]                      |
| `country_weekday`            | [`COUNTRY`, `is_weekday`]                               |
| `time_visitor_country`       | [`TIME_BLOCK_ID`, `VISITOR_CLASS_ID`, `COUNTRY`]        |
| `time_visitor_weekday`       | [`TIME_BLOCK_ID`, `VISITOR_CLASS_ID`, `is_weekday`]     |
| `time_country_weekday`       | [`TIME_BLOCK_ID`, `COUNTRY`, `is_weekday`]              |
| `visitor_country_weekday`    | [`VISITOR_CLASS_ID`, `COUNTRY`, `is_weekday`]           |
| `time_visitor_country_weekday`| [`TIME_BLOCK_ID`, `VISITOR_CLASS_ID`, `COUNTRY`, `is_weekday`] |

-------------------------------------------------------------------------------


## Output folder structure
Case diffusione 1,2:   
We have said that we condition the output according to a `Key` (i.e. `day_hour_user_weekday`) and the correspondingly retained columns (i.e. [`day`, `hour`, `user`, `weekday`]):   

Output/   
└── <`project_name`>/   
   └── <`day`>/   
        └── <`time_interval`>/  
                           └──<`is_weekday`>   
                              └──<`user`>   

Case Diffusione 3:   
Output/
└── <`combination_of_conditioning_variables`>/   
    ├── <`case_pipeline`>_portfolio_map.png   
    ├── <`case_pipeline`>_pastur_distribution_eigenvalues.png   
    └── `geodataframe_input_plots_markowitz_<case_pipeline>`.geojson

## User Profiles

The analysis supports different user types from Vodafone data:
- `VISITOR`: Day visitors
- `TOURIST`: Multi-day tourists
- `COMMUTER`: Regular commuters
- `INHABITANT`: Local residents
- `AGGREGATED`: Combined analysis across all user types

# Notes

- Some functionality requires specific ISTAT population data files 
- The notebook includes both synthetic flow generation and real data processing capabilities
- Geographic analysis is focused on the Trentino region with support for OSM data integration

#### Vodafone Data
- `Festivo - Prefestivo` days are missing in 202407 16-31


