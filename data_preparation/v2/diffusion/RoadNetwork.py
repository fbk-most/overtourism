from os.path import exists
from networkx import Graph
from tqdm import tqdm
from copy import deepcopy
from shapely.geometry import LineString

def clean_graph_for_graphml(G):
    """
    Remove or convert attributes that are not compatible with GraphML format.
    
    Parameters:
        G (networkx.Graph): NetworkX graph to clean
    
    Returns:
        networkx.Graph: A copy of the graph with problematic attributes removed
    """
    G_clean = G.copy()
    
    # Remove geometry attributes from edges
    for u, v, k, data in G_clean.edges(data=True, keys=True):
        if 'geometry' in data:
            del data['geometry']
        
        # Convert all values to strings to ensure compatibility
        for key in list(data.keys()):
            if not isinstance(data[key], (str, int, float, bool)) or data[key] is None:
                data[key] = str(data[key])
    
    # Remove geometry attributes from nodes
    for node, data in G_clean.nodes(data=True):
        if 'geometry' in data:
            del data['geometry']
        
        # Convert all values to strings to ensure compatibility
        for key in list(data.keys()):
            if not isinstance(data[key], (str, int, float, bool)) or data[key] is None:
                data[key] = str(data[key])
    
    return G_clean

### --------------------------------------- PRUNING THE GRAPH -------------------------------------------- ###

def compute_list_nodes_to_merge_from_G(G,is_directed):
    """
        @description:
            - computes the list of nodes to merge from the graph G
            Essentially in the case of directed graph we generate a list of list of nodes.
            node,predecessor,successor
            node,predecessor,None
            node,None,successor
            NOTE: It is important the order of the nodes in the list.
        @input:
            - G: networkx graph
            - is_directed: boolean -> True if the graph is directed, False otherwise
        @output:
            - nodes_to_merge: list of tuples -> list of nodes to merge
        ----------------------------------------------------
            NOTE: Keeps looking at the nodes in the network that must not be considered as 1 road.
    """
    nodes_to_merge = []
    for node, degree in dict(G.degree()).items():
        if is_directed:
            if degree == 2:
                # For directed graphs, we need to check both in and out edges
                    predecessors = list(G.predecessors(node))
                    successors = list(G.successors(node))
                    # Only consider nodes with exactly one incoming and one outgoing edge
                    if len(predecessors) == 1 and len(successors) == 1:
                        nodes_to_merge.append((node, predecessors[0], successors[0]))
            elif degree == 1:
                # For directed graphs, we need to check if the node is a source or sink
                predecessors = list(G.predecessors(node))
                successors = list(G.successors(node))
                if len(predecessors) == 0 and len(successors) == 1:
                    # Source node
                    nodes_to_merge.append((node, None, successors[0]))
                elif len(predecessors) == 1 and len(successors) == 0:
                    # Sink node
                    nodes_to_merge.append((node, predecessors[0], None))
            else:
                # Skip nodes with degree > 2
                continue
        else:
            if degree == 2:
                nodes_to_merge.append(node)
            else:
                # Skip nodes with degree > 2
                continue

def is_source_and_sink(from_node, to_node):
    """
    Check if a node is a source or sink in a directed graph.
    """
    if from_node is None and to_node is not None:
        is_node_source = True
        is_node_sink = False
    # from_node is not None and to_node is None -> it means that node is in the the tail of the 
    if from_node is not None and to_node is None:
        is_node_source = False
        is_node_sink = True
    # both the from_node and to_node are not None -> it means that node is in the middle of the two and must be merged with boths
    if from_node is not None and to_node is not None:
        is_node_source = True
        is_node_sink = True
    return is_node_source, is_node_sink


def advanced_simplify_road_network(G_original, preserve_attributes=True):
    """
    Advanced road network simplification that iteratively merges segments
    until no more simplifications are possible.
    
    Parameters:
        G_original: NetworkX graph of road network
        preserve_attributes: Whether to carefully preserve edge attributes
        
    Returns:
        G_simplified: Simplified network with only true intersections
    """
    import networkx as nx
    import time
    
    start_time = time.time()
    print("Starting network simplification...")
    
    # Work on a copy
    G = deepcopy(G_original)
    
    # Track initial stats
    initial_nodes = G.number_of_nodes()
    initial_edges = G.number_of_edges()
    
    # Track progress
    iteration = 0
    total_merged = 0
    
    # Check if the graph is directed
    is_directed = G.is_directed()


    while True:
        iteration += 1
        print(f"Iteration {iteration}...")
        
        # Find nodes with degree=2
        nodes_to_merge = compute_list_nodes_to_merge_from_G(G,is_directed)        
        if not nodes_to_merge:
            break
            
        # Count this iteration's merges
        merged_in_iteration = 0
        
        # Process nodes for undirected graphs
        if not is_directed:
            for node in tqdm(nodes_to_merge, desc="Processing undirected nodes"):
                # Skip if node was already removed
                if node not in G:
                    continue
                    
                # Get neighbors
                try:
                    neighbors = list(G.neighbors(node))
                    
                    # Skip if not exactly 2 neighbors
                    if len(neighbors) != 2:
                        continue
                        
                    n1, n2 = neighbors[0], neighbors[1]
                except Exception as e:
                    print(f"Error processing node {node}: {e}")
                    continue
                
                # Skip if would create parallel edge
                if n1 == n2 or G.has_edge(n1, n2):
                    continue
                
                try:
                    # Get edge data
                    edge1_data = G.get_edge_data(n1, node) or G.get_edge_data(node, n1)
                    edge2_data = G.get_edge_data(node, n2) or G.get_edge_data(n2, node)
                    
                    if edge1_data is None or edge2_data is None:
                        print(f"Warning: Missing edge data for node {node}")
                        continue
                    
                    # For geometry
                    merged_geom = None
                    if preserve_attributes and 'geometry' in edge1_data and 'geometry' in edge2_data:
                        try:
                            # Get coordinates
                            coords1 = list(edge1_data['geometry'].coords)
                            coords2 = list(edge2_data['geometry'].coords)
                            
                            # Check if we need to reverse coordinates
                            # If n1 -> node, then the end of coords1 should match node
                            # If node -> n2, then the start of coords2 should match node
                            
                            # Get node coordinates (from either edge)
                            node_point = None
                            for edge_data in [edge1_data, edge2_data]:
                                if 'geometry' in edge_data:
                                    geom = edge_data['geometry']
                                    if geom.geom_type == 'LineString':
                                        if G.has_edge(n1, node) and not G.has_edge(node, n1):
                                            # n1 -> node, so node is the end of edge1
                                            node_point = geom.coords[-1]
                                        elif G.has_edge(node, n1) and not G.has_edge(n1, node):
                                            # node -> n1, so node is the start of edge1
                                            node_point = geom.coords[0]
                                        break
                            
                            # Make sure the coordinates are in the right order
                            if coords1[-1] != coords2[0]:
                                # Try various possible configurations
                                if coords1[0] == coords2[0]:
                                    coords1.reverse()
                                elif coords1[-1] == coords2[-1]:
                                    coords2.reverse()
                                elif coords1[0] == coords2[-1]:
                                    coords1.reverse()
                                    coords2.reverse()
                            
                            # Create merged geometry with duplicate point removed
                            merged_coords = coords1[:-1] + coords2
                            merged_geom = LineString(merged_coords)
                        except Exception as e:
                            print(f"Error merging geometries: {e}")
                            merged_geom = None
                    
                    # Create merged attributes
                    merged_attrs = {}
                    
                    # Simple case - just use first edge attributes
                    if not preserve_attributes:
                        merged_attrs = edge1_data.copy()
                        if 'geometry' in merged_attrs and merged_geom:
                            merged_attrs['geometry'] = merged_geom
                    else:
                        # Carefully merge attributes
                        for key in set(edge1_data.keys()) | set(edge2_data.keys()):
                            if key == 'geometry' and merged_geom:
                                merged_attrs[key] = merged_geom
                            elif key == 'length':
                                # Sum lengths
                                merged_attrs[key] = edge1_data.get(key, 0) + edge2_data.get(key, 0)
                            elif key == 'osmid':
                                # Combine OSM IDs to maintain traceability
                                id1 = edge1_data.get(key, None)
                                id2 = edge2_data.get(key, None)
                                if isinstance(id1, list) and isinstance(id2, list):
                                    merged_attrs[key] = id1 + id2
                                elif isinstance(id1, list):
                                    merged_attrs[key] = id1 + [id2] if id2 else id1
                                elif isinstance(id2, list):
                                    merged_attrs[key] = [id1] + id2 if id1 else id2
                                else:
                                    merged_attrs[key] = [id1, id2] if id1 and id2 else id1 or id2
                            else:
                                # Default to first edge's attribute
                                merged_attrs[key] = edge1_data.get(key, edge2_data.get(key))
                    
                    # Add the merged edge
                    G.add_edge(n1, n2, **merged_attrs)
                    
                    # Remove the node and its edges
                    G.remove_node(node)
                    merged_in_iteration += 1
                    total_merged += 1
                except Exception as e:
                    print(f"Error during edge merging for node {node}: {e}")
                    continue
        
        # Process nodes for directed graphs
        else:
            for node, from_node, to_node in tqdm(nodes_to_merge, desc="Processing directed nodes"):
                # Skip if node was already removed
                if node not in G:
                    continue
                # skip if no union can be done
                if from_node is None and to_node is None:
                    continue
                is_source,is_sink = is_source_and_sink(from_node, to_node)
                # Skip if would create parallel edge
                if from_node == to_node or G.has_edge(from_node, to_node):
                    continue
                # consider to merge just those nodes that are in the middle
                if is_source and is_sink and node in G:
                    try:
                        # Get edge data
                        edge1_data = G.get_edge_data(from_node, node)
                        edge2_data = G.get_edge_data(node, to_node)
                        if edge1_data is None or edge2_data is None:
                            raise ValueError(f"Missing edge data for node {node}")
                            
                        
                        # NOTE: I am preserving the order by giving from_node, node, to_node
                        merged_geom = None
                        if preserve_attributes and 'geometry' in edge1_data and 'geometry' in edge2_data:
                            coords1 = list(edge1_data['geometry'].coords)
                            coords2 = list(edge2_data['geometry'].coords)
                            
                            # For directed graphs we assume the edge directions are correct
                            # Create merged geometry
                            merged_coords = coords1[:-1] + coords2  # Remove duplicate point
                            merged_geom = LineString(merged_coords)
                        
                        # Create merged attributes
                        merged_attrs = {}
                        
                        if not preserve_attributes:
                            merged_attrs = edge1_data.copy()
                            if 'geometry' in merged_attrs and merged_geom:
                                merged_attrs['geometry'] = merged_geom
                        else:
                            # Carefully merge attributes
                            for key in set(edge1_data.keys()) | set(edge2_data.keys()):
                                if key == 'geometry' and merged_geom:
                                    merged_attrs[key] = merged_geom
                                elif key == 'length':
                                    merged_attrs[key] = edge1_data.get(key, 0) + edge2_data.get(key, 0)
                                elif key == 'osmid':
                                    id1 = edge1_data.get(key, None)
                                    id2 = edge2_data.get(key, None)
                                    if isinstance(id1, list) and isinstance(id2, list):
                                        merged_attrs[key] = id1 + id2
                                    elif isinstance(id1, list):
                                        merged_attrs[key] = id1 + [id2] if id2 else id1
                                    elif isinstance(id2, list):
                                        merged_attrs[key] = [id1] + id2 if id1 else id2
                                    else:
                                        merged_attrs[key] = [id1, id2] if id1 and id2 else id1 or id2
                                else:
                                    merged_attrs[key] = edge1_data.get(key, edge2_data.get(key))
                        
                        # Add the merged edge
                        G.add_edge(from_node, to_node, **merged_attrs)
                        
                        # Remove the node and its edges
                        G.remove_node(node)
                        merged_in_iteration += 1
                        total_merged += 1
                    except Exception as e:
                        print(f"Error during directed edge merging: {e}")
                        continue
                
        print(f"  Merged {merged_in_iteration} edges in this iteration")
        
        # Break if no more merges in this iteration
        if merged_in_iteration == 0:
            break
    
    # Final stats
    elapsed = time.time() - start_time
    print(f"Simplification complete in {elapsed:.2f} seconds")
    print(f"Original: {initial_nodes} nodes, {initial_edges} edges")
    print(f"Simplified: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"Reduced by: {initial_nodes - G.number_of_nodes()} nodes ({(initial_nodes - G.number_of_nodes()) / initial_nodes * 100:.1f}%)")
    
    return G