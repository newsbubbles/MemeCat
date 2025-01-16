# Semantic Pythonic Dictionary
# lks-ai/semdict by Nathaniel D. Gibson
# This utility class is meant to serve as a quick way to semantically embed and recall any given textual data

from sentence_transformers import SentenceTransformer
import numpy as np
from scipy.spatial.distance import cosine
import os

os.environ['TOKENIZERS_PARALLELISM'] = 'false'  # To avoid the SentenceTransformer warning

# Initialization of the model takes a moment, so we only initalize it once.
sentence_transformer = SentenceTransformer('paraphrase-MiniLM-L6-v2')

class SemanticDict:
    def __init__(self, model_name='paraphrase-MiniLM-L6-v2'):
        self.model_name = model_name
        self.model = sentence_transformer
        self.embeddings = {}
        self.data = {}
        
    def __getstate__(self):
        state = self.__dict__.copy()
        state['model'] = None
        return state
    
    def __setstate__(self, state):
        self.__dict__.update(state)
    
    def restore(self):
        self.model = sentence_transformer

    def _embed(self, text):
        return self.model.encode(text)

    def add(self, key:str, value):
        """ Embed a key into the vector store, placing the value as the data for that entry

        Args:
            key (str): A textual representation of a semantic key to embed. Used for recall.
            value (Any): The data which is held at the key's embedded vector location.
        """
        key_embedding = self._embed(key)
        self.embeddings[key] = key_embedding
        self.data[key] = value

    def get(self, key, n=1, threshold=0.83):
        """ Get top `n` nearest neighbors to the `key` below `threshold` distance away

        Args:
            key (str): The query to search the vectorstore by. Include/Append anything which can be recalled with natural language.
            n (int, optional): Maximum number of results to return. Defaults to 1.
            threshold (float, optional): The maximum distance a neighboring entry can be from the key embedding. Defaults to 0.83.

        Returns:
            _type_: _description_
        """
        key_embedding = self._embed(key)
        distances = []
        
        for stored_key, embedding in self.embeddings.items():
            distance = cosine(key_embedding, embedding)
            if distance < threshold:
                distances.append((stored_key, distance))
        
        # Sort by distance and return the top n closest neighbors
        distances.sort(key=lambda x: x[1])
        closest_neighbors = distances[:n]

        # Return the data corresponding to the closest neighbors
        return [(stored_key, self.data[stored_key], _) for stored_key, _ in closest_neighbors]
    
    def remove(self, key:str):
        key_embedding = self._embed(key)
        return self.data.pop(key_embedding)
        
        
if __name__ == "__main__":

    # test utility function to measure elapsed time in steps
    import time
    last = time.time()
    def elapsed(tag):
        global last
        t = time.time()
        e = t - last
        print(tag, e)
        last = t
        

    # Initialize and add some data into the dict
    elapsed('start')
    sed = SemanticDict()
    elapsed('post model init') # shows time for class init as model init is already done
    sed.add("eat apple", {'action': {'type': 'eat', 'target': 'apple'}})
    elapsed('add apple')
    sed.add("take car", {'action': {'type': 'take', 'target': 'car'}})
    elapsed('add car')
    sed.add("take bananna", {'action': {'type': 'take', 'target': 'bananna'}})
    elapsed('add bananna')

    # Perform a simple search for "fruit"
    r = sed.get("fruit", n=10, threshold=0.83)  # Should return apple and bananna
    for embedding, value, distance in r:
        print(embedding, value, distance)
    elapsed('query time')
