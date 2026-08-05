import ast

from haversine import haversine 

from math import isinf

from numpy import arange,arctan2,inf,isnan,array,nan
from networkx import read_graphml,write_graphml,grid_2d_graph,set_node_attributes

from os.path import join, isfile

from pandas import DataFrame, read_parquet

from tqdm import tqdm
# Personal
from data_preparation.diffusion.GeometrySphere import ProjCoordsTangentSpace

def GetLattice(grid,
               N_i,
               N_j,
               complete_path_lattice,
               str_i_name = "i",
               str_j_name = "j",
               str_centroid_x = "centroidx",
               str_centroid_y = "centroidy"
               ):
    '''
        Output:
            lattice: graph -> graph object of the lattice associated to the grid
        Description:
            This function is used to get the lattice of the city, it is a graph object that contains the nodes and the edges of the city.
            It is used to compute the gradient and the curl of the city.
        @params grid: geodataframe -> grid of the city
        @params N_i: int -> number of rows of the grid
        @params N_j: int -> number of columns of the grid
        @params complete_path_lattice: str -> path to the lattice file
        @params str_i_name: str -> name of the column that contains the i index
        @params str_j_name: str -> name of the column that contains the j index
        @params str_centroid_x: str -> name of the column that contains the x coordinate of the centroid
        @params str_centroid_y: str -> name of the column that contains the y coordinate of the centroid
        @description:
            The script initialize the lattice given the position of the centroid of the grid.
            It initializes the features:
            NODES:
                - x: x coordinate of the centroid
                - y: y coordinate of the centroid
            EDGES:
                - dx: x component of the vector field
                - dy: y component of the vector field
                - distance: distance between the two nodes
                - angle: angle between the two nodes
                - d/dx: derivative of the x component of the vector field
                - d/dy: derivative of the y component of the vector field
    '''
    ## BUILD GRAPH OBJECT GRID
    ## CHECK IF LATTICE ALREADY EXISTS
    if isfile(complete_path_lattice):
        print(f"Loading existing lattice from {complete_path_lattice}")
        lattice = read_graphml(complete_path_lattice)
        return lattice
    else:
        print(f"Creating new {N_i}x{N_j} lattice...")
        
        # Create the base grid graph
        lattice = grid_2d_graph(N_i, N_j)
        print("Setting node attributes...")
        
        # Pre-process the grid data into a dictionary for faster lookup
        grid_dict = {(row[str_i_name], row[str_j_name]): {
            'x': row[str_centroid_x],
            'y': row[str_centroid_y]
        } for idx, row in grid.iterrows()}
        
        # Set node attributes all at once
        set_node_attributes(lattice, grid_dict)
        
        # Pre-compute all node coordinates for faster edge processing
        node_coords = {}
        for node in lattice.nodes():
            try:
                node_coords[node] = (
                    lattice.nodes[node]['x'],
                    lattice.nodes[node]['y']
                )
            except KeyError:
                # Skip nodes without coordinates
                pass
        
        # Process edges with progress bar for better monitoring
        print("Processing edges...")
        edges_list = list(lattice.edges())
        
        # Group edges for batch processing (improves performance)
        batch_size = min(1000, len(edges_list))  # Adjust based on memory constraints
        
        for i in tqdm(range(0, len(edges_list), batch_size)):
            batch_edges = edges_list[i:i+batch_size]
            
            for edge in batch_edges:
                try:
                    # Get pre-computed coordinates
                    if edge[0] not in node_coords or edge[1] not in node_coords:
                        continue
                    
                    x0, y0 = node_coords[edge[0]]
                    x1, y1 = node_coords[edge[1]]
                    
                    # Calculate edge attributes efficiently
                    dx, dy = ProjCoordsTangentSpace(x1, y1, x0, y0)
                    
                    # Set all edge attributes at once (reduces dict lookups)
                    edge_attrs = {
                        'dx': dx,
                        'dy': dy,
                        'distance': haversine((y0, x0), (y1, x1)),
                        'angle': arctan2(dy, dx),
                        'd/dx': 1/dx if dx != 0 and not isnan(1/dx) else inf,
                        'd/dy': 1/dy if dy != 0 and not isnan(1/dy) else inf
                    }
                    
                    # Update all edge attributes at once
                    lattice[edge[0]][edge[1]].update(edge_attrs)
                    
                except (KeyError, ZeroDivisionError) as e:
                    # More specific error handling
                    pass
        
        # Save the lattice - make sure directory exists
        print(f"Saving lattice to {complete_path_lattice}")
        write_graphml(lattice, complete_path_lattice)
        
        print("Lattice creation complete")
        return lattice
    
# ---------------------- POTENTIAL -------------------------- #
def GetPotentialLattice(lattice,
                        VectorField,
                        str_potential_in = 'V_in',
                        str_potential_out = 'V_out',
                        str_grid_id = 'index',
                        str_rotor_z_in = 'rotor_z_in',
                        str_rotor_z_out = 'rotor_z_out',
                        str_index_vector_field = '(i,j)',
                        str_Ti = 'Ti',
                        str_Tj = 'Tj',
                        ):
    '''
        Input: 
            lattice -> without ['V_in','V_out']
            VectorField: Dataframe [index,(i,j),Ti,Tj]
        Output:
            lattice with:
                'V_in' potential for the incoming fluxes
                'V_out' potential for the outgoing fluxes
                'rotor_z_in': Is the rotor at the point (i,j) for the ingoing flux. (Tj) sum over i. So I look at a source and I say that the field
                              is the ingoing flux. This is strange as it does not give any information about where to go to find the sink.
                'rotor_z_out': Is the rotor at the point (i,j) for the ingoing flux. (Ti) sum over j. So I look at a source and I say that the field
                               is the outgoing flux. In this way I am considering the analogue case to the google algorithm for
                               page rank as I am at a random point and the field points at the direction with smaller potential, the sink, that is 
                               the higher rank of importance.
                    
        Describe:
            Output = Input for ConvertLattice2PotentialDataframe
    '''
    assert lattice is not None, "Lattice is None"
    assert VectorField is not None, "VectorField is None"
    assert str_index_vector_field in VectorField.columns, f"VectorField does not contain {str_index_vector_field}"
    set_node_attributes(lattice, 0, str_potential_in)
    set_node_attributes(lattice, 0, str_potential_out)
    set_node_attributes(lattice, 0, str_grid_id)
    set_node_attributes(lattice, 0, str_rotor_z_in)
    set_node_attributes(lattice, 0, str_rotor_z_out)
    max_i = max(ast.literal_eval(node_str)[0] for node_str in lattice.nodes)
    max_j = max(ast.literal_eval(node_str)[1] for node_str in lattice.nodes)
    # Initialize potential to 0 -> in this way the boundary is 0
    for node_str in lattice.nodes:    
        ij = ast.literal_eval(node_str)
        i = ij[0]
        j = ij[1]
        lattice.nodes[node_str][str_potential_in] = 0
        lattice.nodes[node_str][str_potential_out] = 0


    for edge in lattice.edges(data=True):
        # Extract the indices of the nodes
        node_index_1, node_index_2 = edge[:2]    
        VectorField.index = VectorField[str_index_vector_field]
        # Compute the value of V for the edge using the formula
        # NOTE: The formula seems to have dx multiplying the y component of the vector field (it is not the case as (0,0),(1,0) is moving in x)
        # NOTE: I computed dx thinking that (1,0) being the y !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  dx is dy
        # NOTE: CHECK df_distance
        dxTjx = lattice[node_index_1][node_index_2]['dy'] * VectorField.loc[node_index_1, str_Ti][0]
        dyTjy = lattice[node_index_1][node_index_2]['dx'] * VectorField.loc[node_index_1, str_Tj][1]
        node_Vin = lattice.nodes[node_index_1][str_potential_in] + dxTjx  + dyTjy  
        node_Vout = lattice.nodes[node_index_1][str_potential_out] + lattice[node_index_1][node_index_2]['dx'] * VectorField.loc[node_index_1, str_Ti][1]  + lattice[node_index_1][node_index_2]['dy'] * VectorField.loc[node_index_1, str_Ti][0]      
        # ROTOR NOTE: AGAIN[d/dx is d/dy] NETWORKX USES THIS CONVENTION
        if not isinf(lattice[node_index_1][node_index_2]['d/dy']):
            ddxTjy = lattice[node_index_1][node_index_2]['d/dy'] * VectorField.loc[node_index_1, str_Tj][1]
        else:
            ddxTjy = 0
        if not isinf(lattice[node_index_1][node_index_2]['d/dx']):
            ddyTjx = lattice[node_index_1][node_index_2]['d/dx'] * VectorField.loc[node_index_1, str_Tj][0]  
        else:
            ddyTjx = 0
        rotor_z_in = ddxTjy  - ddyTjx
        if not isinf(lattice[node_index_1][node_index_2]['d/dy']):    
            ddxTiy = lattice[node_index_1][node_index_2]['d/dy'] * VectorField.loc[node_index_1, str_Ti][1]
        else:
            ddxTiy = 0
        if not isinf(lattice[node_index_1][node_index_2]['d/dx']):
            ddyTix = lattice[node_index_1][node_index_2]['d/dx'] * VectorField.loc[node_index_1, str_Ti][0]  
        else:
            ddyTix = 0
        rotor_z_out = ddxTiy  - ddyTix
        lattice.nodes[node_index_2][str_potential_in] = node_Vin
        lattice.nodes[node_index_2][str_potential_out] = node_Vout
        lattice.nodes[node_index_2][str_grid_id] = VectorField.loc[node_index_1, 'index']
        lattice.nodes[node_index_2][str_rotor_z_in] = rotor_z_in
        lattice.nodes[node_index_2][str_rotor_z_out] = rotor_z_out
    return lattice

def SmoothPotential(lattice, 
                    str_potential_in = 'V_in',
                    str_potential_out = 'V_out'):
    # Smooth V_in and V_out by taking the average over all the neighbors
    for node_str in lattice.nodes:
        neighbors = list(lattice.neighbors(node_str))
        num_neighbors = len(neighbors)
        
        # Calculate the average of V_in and V_out for the neighbors
        avg_Vin = sum(lattice.nodes[neighbor][str_potential_in] for neighbor in neighbors) / num_neighbors
        avg_Vout = sum(lattice.nodes[neighbor][str_potential_out] for neighbor in neighbors) / num_neighbors
        
        # Assign the average values to the current node
        lattice.nodes[node_str][str_potential_in] = avg_Vin
        lattice.nodes[node_str][str_potential_out] = avg_Vout    
    return lattice

def ConvertLattice2PotentialDataframe(lattice,
                                      str_grid_id = 'index',
                                      str_potential_in = 'V_in',
                                      str_potential_out = 'V_out',
                                      str_rotor_z_in = 'rotor_z_in',
                                      str_rotor_z_out = 'rotor_z_out'):
    '''
        Input: 
            Lattice with potential
        Output:
            Dataframe with:
                V_in, V_out, centroid (x,y), index, node_id(i,j)
        Usage:
            3D plot for Potential and Lorenz Curve.
    '''
    data_ = []
    for node,data in lattice.nodes(data=True):
        asserts_conversion_lattice_2_dataframe(lattice,node,str_grid_id,str_potential_in,str_potential_out,str_rotor_z_in,str_rotor_z_out)
        # Extract the indices of the nodes
        ij = ast.literal_eval(node)    
        node_id = (ij[0],ij[1])
        # Compute the value of V_in for the edge
        node_Vin = lattice.nodes[node][str_potential_in]  
        
        # Compute the value of V_out for the edge
        node_Vout = lattice.nodes[node][str_potential_out]
        x = lattice.nodes[node]['x']
        y = lattice.nodes[node]['y']
        index_ = lattice.nodes[node][str_grid_id]
        rotor_z_in = lattice.nodes[node][str_rotor_z_in]
        rotor_z_out = lattice.nodes[node][str_rotor_z_out]
        # Save the information to the list
        data_.append({str_potential_in: node_Vin,
                      str_potential_out: node_Vout,
                      str_grid_id: index_ ,
                      'node_id': node_id,
                      'x':x,
                      'y':y,
                      str_rotor_z_in:rotor_z_in,
                      str_rotor_z_out:rotor_z_out})
        
        # Create a DataFrame from the list
        PotentialDataframe = DataFrame(data_)
        PotentialDataframe[str_grid_id] = PotentialDataframe.index
        # Format the 'node_id' column using ast.literal_eval
#        PotentialDataframe['node_id'] = PotentialDataframe['node_id'].apply(ast.literal_eval)
    return PotentialDataframe



def asserts_conversion_lattice_2_dataframe(lattice,
                                           node,
                                           str_grid_id,
                                           str_potential_in,
                                           str_potential_out,
                                           str_rotor_z_in,
                                           str_rotor_z_out):
        assert 'x' in lattice.nodes[node], f"Node {node} does not have x coordinate"
        assert 'y' in lattice.nodes[node], f"Node {node} does not have y coordinate"
        assert str_grid_id in lattice.nodes[node], f"Node {node} does not have {str_grid_id} coordinate"
        assert str_potential_in in lattice.nodes[node], f"Node {node} does not have {str_potential_in} coordinate"
        assert str_potential_out in lattice.nodes[node], f"Node {node} does not have {str_potential_out} coordinate"
        assert str_rotor_z_in in lattice.nodes[node], f"Node {node} does not have {str_rotor_z_in} coordinate"
        assert str_rotor_z_out in lattice.nodes[node], f"Node {node} does not have {str_rotor_z_out} coordinate"


def CompletePotentialDataFrame(VectorField,
                               grid,
                               PotentialDataframe,
                               str_Ti = 'Ti',
                               str_population = 'population'
                               ):
    PotentialDataframe[str_Ti] = VectorField[str_Ti]
    PotentialDataframe[str_population] = grid[str_population]    
    return PotentialDataframe


# ---------------------- VECTOR FIELD -------------------------- #
def parse_dir_vector(vector_string):
    if vector_string== '[nan,nan]' or vector_string== '[nan nan]':
        vector_array = array([0,0])
    # Split the string representation of the vector
    else:
        vector_parts = vector_string.strip('[]').split()
        # Convert each part to a float or np.nan if it's 'nan'
        vector_array = array([float(part) if part != 'nan' else nan for part in vector_parts])
    return vector_array


def from_Tij_df_distance_2_vec_field(Tij,
                                     df_distance,
                                     complete_path_vector_field,
                                     str_flux_column = 'number_people',
                                     str_dir_vector_column = 'dir_vector',
                                     str_index_fluxes_O_column = '(i,j)O',
                                     str_index_fluxes_D_column = '(i,j)D',
                                     str_Ti = 'Ti',
                                     str_Tj = 'Tj',
                                     str_index_vector_field = '(i,j)',
                                     
                                     ):
    """
        Convert the fluxes into VectorField DataFrame.
        @params Tij: DataFrame with the fluxes 
        @params df_distance: DataFrame with the distances
    """
    # Compute vector Flux in  OD
    print("Compute vector flux in OD from Tij-df_distance")
    if isfile(complete_path_vector_field):
        VectorField = read_parquet(complete_path_vector_field)
        return VectorField
    else:
        Tij['vector_flux'] = df_distance[str_dir_vector_column].apply(lambda x: parse_dir_vector(x) ) * Tij[str_flux_column]
        # Create VectorField DataFrame
        VectorField = DataFrame(index=Tij[str_index_fluxes_D_column].unique(), columns=[str_index_vector_field, str_Ti, str_Tj])
        Tj_values = Tij.groupby(str_index_fluxes_D_column)['vector_flux'].sum()
        VectorField[str_Tj] = Tj_values
        # Calculate 'Ti' values
        Ti_values = Tij.groupby(str_index_fluxes_O_column)['vector_flux'].sum()
        VectorField[str_Ti] = Ti_values
        VectorField['index'] = VectorField.index
        VectorField[str_index_vector_field] = VectorField['index']
        VectorField['index'] = VectorField.index
        VectorField.reset_index(inplace=True)
        VectorField.to_parquet(complete_path_vector_field, index=False)
        return VectorField


# Pipeline Potential
def pipeline_potential_vector_field(Tij,
                                    df_distance,
                                    grid,
                                    lattice,
                                    complete_path_vector_field,
                                    complete_path_potential,
                                    str_flux_column = 'number_people',
                                    str_dir_vector_column = 'dir_vector',
                                    str_index_fluxes_O_column = '(i,j)O',
                                    str_index_fluxes_D_column = '(i,j)D',
                                    str_Ti = 'Ti',
                                    str_Tj = 'Tj',
                                    str_index_vector_field = '(i,j)',
                                    str_potential_in = 'V_in',
                                    str_potential_out = 'V_out',
                                    str_grid_id = 'index',
                                    str_rotor_z_in = 'rotor_z_in',
                                    str_rotor_z_out = 'rotor_z_out',
                                    str_population = 'population'                               

):
    """
        @param Tij: Dataframe with the number of people from i to j
        @param df_distance: Dataframe with the distance matrix and the direction vector
        @param lattice: Graph with the square lattice
        @param grid: Dataframe with the grid
        @param city: Name of the city
        @return PotentialDataframe: Dataframe with the potential
    """
    VectorField = from_Tij_df_distance_2_vec_field(Tij,
                                    df_distance,
                                    complete_path_vector_field,
                                    str_flux_column = str_flux_column,
                                    str_dir_vector_column = str_dir_vector_column,
                                    str_index_fluxes_O_column = str_index_fluxes_O_column,
                                    str_index_fluxes_D_column = str_index_fluxes_D_column,
                                    str_Ti = str_Ti,
                                    str_Tj = str_Tj,
                                    str_index_vector_field = str_index_vector_field,
                                    )
    if isfile(complete_path_potential):
        # Initialize the vector field in the edges of the grid whose centroids are the nodes
        lattice = GetPotentialLattice(lattice,
                                    VectorField,
                                    str_potential_in = str_potential_in,
                                    str_potential_out = str_potential_out,
                                    str_grid_id = str_grid_id,
                                    str_rotor_z_in = str_rotor_z_in,
                                    str_rotor_z_out = str_rotor_z_out,
                                    str_index_vector_field = str_index_vector_field,
                                    str_Ti = str_Ti,
                                    str_Tj = str_Tj)
        # smooth the potential
        lattice = SmoothPotential(lattice,
                                str_potential_in,
                                str_potential_out)
        # get the dataframe from the lattice    
        PotentialDataframe = ConvertLattice2PotentialDataframe(lattice,
                                                                str_grid_id = str_grid_id,
                                                                str_potential_in = str_potential_in,
                                                                str_potential_out = str_potential_out,
                                                                str_rotor_z_in = str_rotor_z_in,
                                                                str_rotor_z_out = str_rotor_z_out)
        PotentialDataframe = CompletePotentialDataFrame(VectorField,
                                                        grid,
                                                        PotentialDataframe,
                                                        str_Ti = str_Ti,
                                                        str_population = str_population)

        # Save the dataframe    
        PotentialDataframe.to_parquet(complete_path_potential, index=False)
    else:
        PotentialDataframe = read_parquet(complete_path_potential)
    return PotentialDataframe,lattice,VectorField




## ------------------ MIGRATION TO NETWORKIT or GRAPH TOOLS ------------------ ##
def ConvertLattice2PotentialDataframe_networkit_graphtool(lattice, 
                                                         str_grid_id='index',
                                                         str_potential_in='V_in',
                                                         str_potential_out='V_out',
                                                         str_rotor_z_in='rotor_z_in',
                                                         str_rotor_z_out='rotor_z_out'):
    '''
    Convert a lattice graph (NetworKit or graph-tool) to a DataFrame containing potential data.
    
    Parameters:
        lattice: NetworKit graph or graph-tool graph with node attributes
        str_grid_id: Key for the grid index attribute
        str_potential_in: Key for the incoming potential attribute
        str_potential_out: Key for the outgoing potential attribute
        str_rotor_z_in: Key for the incoming rotor attribute
        str_rotor_z_out: Key for the outgoing rotor attribute
        
    Returns:
        DataFrame with columns: V_in, V_out, centroid (x,y), index, node_id(i,j), rotor values
        
    Usage:
        3D plot for Potential and Lorenz Curve.
    '''
    import networkit as nk
    import graph_tool.all as gt
    import pandas as pd
    import ast
    from pandas import DataFrame
    import numpy as np
    
    data_ = []
    
    if isinstance(lattice, nk.Graph):
        # NetworKit version
        # Check if necessary node attributes exist
        node_attrs = {
            'x': lattice.hasNodeAttribute('x'),
            'y': lattice.hasNodeAttribute('y'),
            str_grid_id: lattice.hasNodeAttribute(str_grid_id),
            str_potential_in: lattice.hasNodeAttribute(str_potential_in),
            str_potential_out: lattice.hasNodeAttribute(str_potential_out),
            str_rotor_z_in: lattice.hasNodeAttribute(str_rotor_z_in),
            str_rotor_z_out: lattice.hasNodeAttribute(str_rotor_z_out)
        }
        
        for attr, exists in node_attrs.items():
            if not exists:
                raise ValueError(f"Node attribute '{attr}' does not exist in the graph")
        
        # Process each node in the NetworKit graph
        for node in range(lattice.numberOfNodes()):
            if not lattice.hasNode(node):
                continue
                
            # Get node name (should be a string like "(i,j)")
            node_name = lattice.getNodeAttribute(node, "name")
            if node_name.startswith("(") and node_name.endswith(")"):
                ij = ast.literal_eval(node_name)
                node_id = (ij[0], ij[1])
            else:
                # Try to extract from coordinate data
                x = lattice.getNodeAttribute(node, "x")
                y = lattice.getNodeAttribute(node, "y")
                node_id = (node, node)  # Default if can't extract i,j
            
            # Get node attributes
            node_Vin = lattice.getNodeAttribute(node, str_potential_in)
            node_Vout = lattice.getNodeAttribute(node, str_potential_out)
            x = lattice.getNodeAttribute(node, 'x')
            y = lattice.getNodeAttribute(node, 'y')
            index_ = lattice.getNodeAttribute(node, str_grid_id)
            rotor_z_in = lattice.getNodeAttribute(node, str_rotor_z_in)
            rotor_z_out = lattice.getNodeAttribute(node, str_rotor_z_out)
            
            # Save to data list
            data_.append({
                str_potential_in: node_Vin,
                str_potential_out: node_Vout,
                str_grid_id: index_,
                'node_id': node_id,
                'x': x,
                'y': y,
                str_rotor_z_in: rotor_z_in,
                str_rotor_z_out: rotor_z_out
            })
            
    elif isinstance(lattice, gt.Graph):
        # graph-tool version
        # Check if necessary vertex properties exist
        vertex_props = {
            'x': 'x' in lattice.vertex_properties,
            'y': 'y' in lattice.vertex_properties,
            str_grid_id: str_grid_id in lattice.vertex_properties,
            str_potential_in: str_potential_in in lattice.vertex_properties,
            str_potential_out: str_potential_out in lattice.vertex_properties,
            str_rotor_z_in: str_rotor_z_in in lattice.vertex_properties,
            str_rotor_z_out: str_rotor_z_out in lattice.vertex_properties
        }
        
        for attr, exists in vertex_props.items():
            if not exists:
                raise ValueError(f"Vertex property '{attr}' does not exist in the graph")
        
        # Get vertex properties
        vp_x = lattice.vertex_properties['x']
        vp_y = lattice.vertex_properties['y']
        vp_grid_id = lattice.vertex_properties[str_grid_id]
        vp_potential_in = lattice.vertex_properties[str_potential_in]
        vp_potential_out = lattice.vertex_properties[str_potential_out]
        vp_rotor_z_in = lattice.vertex_properties[str_rotor_z_in]
        vp_rotor_z_out = lattice.vertex_properties[str_rotor_z_out]
        
        # Get node name property if it exists
        vp_name = None
        if 'name' in lattice.vertex_properties:
            vp_name = lattice.vertex_properties['name']
        
        # Process each vertex in the graph-tool graph
        for v in lattice.vertices():
            # Get node name
            if vp_name is not None:
                node_name = vp_name[v]
                if isinstance(node_name, str) and node_name.startswith("(") and node_name.endswith(")"):
                    ij = ast.literal_eval(node_name)
                    node_id = (ij[0], ij[1])
                else:
                    node_id = (int(v), int(v))  # Default if can't extract i,j
            else:
                # Try to infer from the vertex index (for grid graphs)
                node_id = (int(v) // lattice.num_vertices()**0.5, int(v) % lattice.num_vertices()**0.5)
            
            # Get vertex properties
            x = vp_x[v]
            y = vp_y[v]
            index_ = vp_grid_id[v]
            node_Vin = vp_potential_in[v]
            node_Vout = vp_potential_out[v]
            rotor_z_in = vp_rotor_z_in[v]
            rotor_z_out = vp_rotor_z_out[v]
            
            # Save to data list
            data_.append({
                str_potential_in: node_Vin,
                str_potential_out: node_Vout,
                str_grid_id: index_,
                'node_id': node_id,
                'x': x,
                'y': y,
                str_rotor_z_in: rotor_z_in,
                str_rotor_z_out: rotor_z_out
            })
    else:
        raise TypeError("Input lattice must be either a NetworKit graph or a graph-tool graph")
    
    # Create DataFrame from the list
    PotentialDataframe = DataFrame(data_)
    PotentialDataframe['index'] = PotentialDataframe.index
    
    return PotentialDataframe
