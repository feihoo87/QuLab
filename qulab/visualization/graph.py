import math

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np


def draw(graph,
         node_colors=None,
         ax=None,
         node_size=3000,
         font_size=18,
         arrowsize=10):
    # 创建有向图对象
    G = nx.DiGraph()

    # 添加边
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            # G.add_edge(node.replace('/', '\n'), neighbor.replace('/', '\n'))
            G.add_edge(neighbor.replace('/', '\n'), node.replace('/', '\n'))

    # 计算每个节点的层数（基于最长路径）
    layers = {}
    for node in nx.topological_sort(G):
        max_layer = -1
        for predecessor in G.predecessors(node):
            if layers.get(predecessor, -1) > max_layer:
                max_layer = layers[predecessor]
        layers[node] = max_layer + 1

    layer_groups = {}

    for k, v in layers.items():
        if v not in layer_groups:
            layer_groups[v] = []
        layer_groups[v].append(k)

    # 使用分层布局
    #pos = nx.multipartite_layout(G, subset_key=layer_groups)
    #pos = nx.planar_layout(G)
    #pos = nx.bfs_layout(G, start='a')
    pos = nx.arf_layout(G)
    pos_data = np.array(list(pos.values()))
    extent = (np.min(pos_data[:, 0]), np.max(pos_data[:, 0]),
              np.min(pos_data[:, 1]), np.max(pos_data[:, 1]))
    size = math.ceil(2.5 * (extent[1] - extent[0])), math.ceil(
        2.5 * (extent[3] - extent[2]))

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=size)

    # 生成颜色列表（关键修改）
    default_color = "lightblue"
    color_list = ([node_colors.get(node, default_color)
                   for node in G.nodes()] if node_colors else default_color)

    # 绘制图形
    nx.draw_networkx(G,
                     pos,
                     with_labels=True,
                     arrows=True,
                     node_color=color_list,
                     node_size=node_size,
                     node_shape='o',
                     font_size=font_size,
                     edge_color='gray',
                     arrowsize=arrowsize,
                     ax=ax)

    ax.axis('off')  # 关闭坐标轴
