#!/usr/bin/env python
"""

Use SentenceTransformers to vectorize the lines in a file and compare
them for similarity. Small-scale version limited to what you can
afford to keep in memory (easily ~100,000 on ordinary hardware). On a
Mac Mini with an M4 Pro and 64 GB of RAM, it managed to process a
2.8-million line file in 63 minutes using faiss-cpu; it gets a lot
worse at larger sizes.

TODO: optimize memory use; currently still has some leftovers from
being LLM-written as multiple sequential scripts. This chews up a lot
of memory for large datasets.
"""

import os
import sys
import json
import argparse
import faiss
import networkx as nx
import numpy as np
from sentence_transformers import SentenceTransformer

parser = argparse.ArgumentParser(
    prog='dedupelines',
    formatter_class = argparse.RawDescriptionHelpFormatter,
    description = """
        strip near-duplicate lines from a file using a small AI model
    """
)
parser.add_argument('-d', '--model-directory',
    default=os.path.expanduser('~/.cache/models'),
    help='directory to store downloaded LLM; default ~/.cache/models')
parser.add_argument('-m', '--model',
    default='all-MiniLM-L6-v2',
    help='specialty model to use for vectorizing text')
parser.add_argument('-t', '--threshold',
    type=float,
    default=0.96,
    help='similarity threshold (0.7 = loose, 0.85 = moderate; default 0.96)'
)
parser.add_argument('-n', '--neighbors',
    type=int,
    default=5,
    help='number of nearest neighbors to eval for each line; default 5')
parser.add_argument('-o', '--output',
    type=str,
    help='output filename (default: $in-new)')
parser.add_argument('-D', '--debug',
    action='store_true',
    help='save intermediate files for debugging')
parser.add_argument('file',
    nargs=1,
    help='file to de-dupe'
)
args=parser.parse_args()
THRESHOLD = args.threshold
K = args.neighbors

if args.output:
    outfile = args.output
else:
    outfile = f"{args.file[0]}-new"

model = False
model_dir = os.path.expanduser(os.path.join(args.model_directory, args.model))
if not os.path.exists(model_dir):
    model = SentenceTransformer(model)
    model.save(model_dir)
if not model:
    model = SentenceTransformer(model_dir)

paragraphs = []
with open(args.file[0]) as f:
    paragraphs = [ x.rstrip() for x in f]

embeddings = model.encode(paragraphs, show_progress_bar=False,
    convert_to_numpy=True)
faiss.normalize_L2(embeddings)
dimension = embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)

distances, indices = index.search(embeddings, K)
G = nx.Graph()
G.add_nodes_from(range(len(paragraphs)))

for i in range(len(paragraphs)):
    for j_idx in range(K):
        score = distances[i][j_idx]
        match_idx = indices[i][j_idx]
        
        # Connect items if they hit the threshold and aren't themselves
        if score >= THRESHOLD and i != match_idx:
            G.add_edge(i, match_idx)

# Extract and sort connected groups by size (largest first)
clusters = list(nx.connected_components(G))
multi_item_clusters = [c for c in clusters if len(c) > 1]
multi_item_clusters.sort(key=len, reverse=True)

cluster_output = {}

for idx, cluster in enumerate(multi_item_clusters):
    cluster_id = f"cluster_{idx + 1}"
    # Store both the text and the original database IDs for tracking
    cluster_output[cluster_id] = {
        "cluster_size": len(cluster),
        "items": [
            {
                "original_id": int(doc_idx),
                "text": paragraphs[doc_idx]
            }
            for doc_idx in cluster
        ]
    }

if args.debug:
    OUTPUT_JSON_PATH = "tmp_1_cluster_info.json"
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as json_file:
        json.dump(cluster_output, json_file, indent=4, ensure_ascii=False)

deduplicated_dataset = {}
for cluster_id, cluster_data in cluster_output.items():
    items = cluster_data["items"]
    
    # Extract the IDs belonging to this cluster
    item_ids = [item["original_id"] for item in items]
    
    # Gather the specific vector embeddings for just these items
    cluster_vectors = embeddings[item_ids]
    
    # Calculate the average vector (the exact center point/centroid of this group)
    centroid = np.mean(cluster_vectors, axis=0)
    
    # Find which individual paragraph's vector sits closest to that center point
    # We do this by calculating the inner product (dot product) of vectors against the centroid
    similarities_to_centroid = np.dot(cluster_vectors, centroid)
    best_item_index_in_cluster = np.argmax(similarities_to_centroid)
    
    # Select the master paragraph data
    master_item = items[best_item_index_in_cluster]
    
    # Build a clean output payload
    deduplicated_dataset[cluster_id] = {
        "master_id": master_item["original_id"],
        "master_text": master_item["text"],
        "total_duplicates_removed": len(items) - 1,
        "all_cluster_ids": item_ids
    }

if args.debug:
    OUTPUT_PATH = "tmp_2_cluster_masters.json"
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(deduplicated_dataset, f, indent=4, ensure_ascii=False)

# Track all paragraph IDs that were parts of a cluster
clustered_ids = set()
for cluster_data in deduplicated_dataset.values():
    # all_cluster_ids contains both the masters and their duplicates
    for original_id in cluster_data["all_cluster_ids"]:
        clustered_ids.add(original_id)

# Separate out the completely unique paragraph IDs
all_ids = set(range(len(paragraphs)))
unique_ids = all_ids - clustered_ids

# Construct the finalized, deduplicated list
final_clean_dataset = []

# Add the golden master paragraphs chosen from the clusters
for cluster_id, cluster_data in deduplicated_dataset.items():
    final_clean_dataset.append({
        "original_id": cluster_data["master_id"],
        "text": cluster_data["master_text"],
        "type": "cluster_master",
        "duplicates_merged": cluster_data["total_duplicates_removed"]
    })

# Add the completely unique paragraphs
for original_id in unique_ids:
    final_clean_dataset.append({
        "original_id": original_id,
        "text": paragraphs[original_id],
        "type": "unique_paragraph",
        "duplicates_merged": 0
    })
final_clean_dataset.sort(key=lambda x: x['original_id'])

if args.debug:
    OUTPUT_FINAL_PATH = "tmp_3_clean_dataset.json"
    with open(OUTPUT_FINAL_PATH, "w", encoding="utf-8") as f:
        json.dump(final_clean_dataset, f, indent=4, ensure_ascii=False)

with open(outfile, "w") as o:
    for par in final_clean_dataset:
        print(par['text'], file=o)
