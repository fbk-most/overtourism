import networkit as nk
import matplotlib.pyplot as plt
nk.setNumberOfThreads(8)

import folium

def plot_nk_graph_geometrical_interactive(G, grid, str_centroid_lat, str_centroid_lon, node_color='red', edge_color='blue'):
    """
    Interactive plot of the networkit graph G using folium.
    """
    # Get node positions
    positions = {}
    for node in range(G.numberOfNodes()):
        idx = node
        row = grid.loc[idx]
        positions[node] = (row[str_centroid_lat], row[str_centroid_lon])

    # Center map on mean position
    lats = [pos[0] for pos in positions.values()]
    lons = [pos[1] for pos in positions.values()]
    fmap = folium.Map(location=[np.mean(lats), np.mean(lons)], zoom_start=12)

    # Draw edges
    for u,v in G.iterEdges():
        latlngs = [
            [positions[u][0], positions[u][1]],
            [positions[v][0], positions[v][1]]
        ]
        folium.PolyLine(latlngs, color=edge_color, weight=2, opacity=0.7).add_to(fmap)

    # Draw nodes
    for node, (lat, lon) in positions.items():
        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color=node_color,
            fill=True,
            fill_opacity=0.8,
            popup=str(node)
        ).add_to(fmap)

    return fmap

def build_nk_graph_from_hotspot_dict(hotspot_2_origin_idx_2_crit_dest_idx, 
                                     grid, 
                                     flows,
                                     str_col_i = "i",
                                     str_col_j = "j", 
                                     str_col_weight = "n_trips"):
    """
    Build a directed networkit graph from the hotspot_2_origin_idx_2_crit_dest_idx dictionary.
    Nodes are grid indices (should be integers).
    """
    assert str_col_i in flows.columns, f"Column {str_col_i} not found in flows DataFrame."
    assert str_col_j in flows.columns, f"Column {str_col_j} not found in flows DataFrame."
    from polars import DataFrame,col
    if isinstance(flows, DataFrame):
        pass
    else:
        flows = DataFrame(flows)
    if str_col_weight not in flows.columns:
        is_weighted = False
    else:
        is_weighted = True
    # Map grid index to consecutive node ids for networkit
    grid_indices = list(grid.index)
    G = nk.graph.Graph(len(grid_indices), directed=True,weighted=is_weighted)    
    for hotspot_level in hotspot_2_origin_idx_2_crit_dest_idx.keys():
        for idx_in_i, list_indices_in_j in hotspot_2_origin_idx_2_crit_dest_idx[hotspot_level].items():
            for idx_in_j in list_indices_in_j:
                G.addEdge(idx_in_i, idx_in_j)
            if is_weighted:
                flows.filter(col(str_col_i) == idx_in_i,
                            col(str_col_j) == idx_in_j)
                weight = flows.select(col(str_col_weight)).to_numpy()[0][0]
                G.setWeight(idx_in_i, idx_in_j, weight)

    return G


def plot_nk_graph_geometrical(G, node2idx, grid, str_centroid_lat, str_centroid_lon, ax=None, node_color='red', edge_color='blue'):
    """
    Plot the networkit graph G using the centroids from grid for node positions.
    """
    import numpy as np
    fig_created = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 10))
        fig_created = True
    
    try:
        # Get node positions
        positions = {}
        for node in range(G.numberOfNodes()):
            idx = node2idx[node]
            row = grid.loc[idx]
            positions[node] = (row[str_centroid_lon], row[str_centroid_lat])
        # Draw nodes
        xs, ys = zip(*positions.values())
        ax.scatter(xs, ys, c=node_color, s=60, zorder=2)
        # Draw edges
        for u in range(G.numberOfNodes()):
            for v in G.iterOutNeighbors(u):
                x0, y0 = positions[u]
                x1, y1 = positions[v]
                ax.plot([x0, x1], [y0, y1], color=edge_color, alpha=0.7, zorder=1)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title("Networkit Graph in Geometrical Space")
        plt.axis('equal')
        plt.show()
    finally:
        # Close the figure if we created it
        if fig_created:
            plt.close(fig)