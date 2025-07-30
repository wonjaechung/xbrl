import faiss
from sentence_transformers import SentenceTransformer
import numpy as np
import pickle
import os
import networkx as nx

class QueryEngine:
    def __init__(self, index_path="xbrl_index.faiss", metadata_path="xbrl_metadata.pkl", documents_path="all_documents.pkl", graph_path="xbrl_kg.graphml"):
        print("Loading the vector database, knowledge graph, and model... This may take a moment.")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = faiss.read_index(index_path)
        
        with open(metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)
            self.doc_ids = self.metadata['doc_ids']
            
        with open(documents_path, 'rb') as f:
            self.documents = pickle.load(f)
            
        self.G = nx.read_graphml(graph_path)

        print("Query engine loaded successfully.")

    def search(self, query, top_k=3):
        """
        Searches the FAISS index for the top_k most similar documents to the query.
        """
        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            doc_id = self.doc_ids[idx]
            content = self.documents[doc_id]
            results.append({
                'id': doc_id,
                'score': distances[0][i],
                'content': content
            })
        return results

    def hybrid_search(self, query, top_k=3, depth=1):
        """
        Performs a hybrid search: vector search followed by graph traversal.
        """
        results = self.search(query, top_k)
        for res in results:
            doc_id = res['id']
            res['related_docs'] = []
            if self.G.has_node(doc_id):
                # Use descendants_at_distance for a more controlled traversal
                related_ids = list(nx.descendants_at_distance(self.G, doc_id, distance=depth))
                for rel_id in related_ids:
                    if rel_id in self.documents:
                        rel_content = self.documents[rel_id]
                        summary = rel_content.split("## Reported Numerical Facts")[0]
                        res['related_docs'].append({
                            'id': rel_id,
                            'summary': summary
                        })
        return results

if __name__ == '__main__':
    # We need to save the `all_documents` dictionary for the query engine to use.
    # Let's modify the document_generator to do this.
    if not os.path.exists("all_documents.pkl"):
        print("First, we need to generate and save the documents...")
        from document_generator import DocumentGenerator
        from xbrl_parser_poc.UnifiedXBRLParser import UnifiedXBRLParser
        
        data_folder = './data'
        file_paths = {
            'concepts': os.path.join(data_folder, 'Concepts.csv'),
            'labels_ko': os.path.join(data_folder, 'entity00413046_2025-03-31_lab-ko.xml'),
            'labels_en': os.path.join(data_folder, 'entity00413046_2025-03-31_lab-en.xml'),
            'presentation': os.path.join(data_folder, 'Presentation Link.csv'),
            'calculation': os.path.join(data_folder, 'Calculation Link.csv'),
            'instance': os.path.join(data_folder, 'entity00413046_2025-03-31.xbrl'),
            'taxonomy_labels': os.path.join(data_folder, 'Label Link.csv'),
            'references': os.path.join(data_folder, 'Reference Link.csv')
        }
        
        parser = UnifiedXBRLParser(file_paths)
        unified_data = parser.run_parser()
        doc_generator = DocumentGenerator(unified_data)
        all_documents = doc_generator.generate_all_documents()
        
        with open("all_documents.pkl", 'wb') as f:
            pickle.dump(all_documents, f)
        print("Documents saved to all_documents.pkl")

    # Now, start the interactive query engine
    engine = QueryEngine()
    
    print("\n--- XBRL Financials Hybrid Query Engine ---")
    print("Ask a question (e.g., 'gross profit', 'revenue from chemical medicines'). Type 'exit' to quit.")
    
    while True:
        query = input("\nYour question: ")
        if query.lower() == 'exit':
            break
            
        results = engine.hybrid_search(query)
        
        print(f"\n--- Top {len(results)} results for '{query}' ---")
        for i, result in enumerate(results):
            print(f"\n--- Result {i+1}: {result['id']} (Similarity Score: {result['score']:.4f}) ---")
            
            summary_part = result['content'].split("## Reported Numerical Facts")[0]
            print(summary_part)
            
            if result['related_docs']:
                print("--- Related Concepts (from Knowledge Graph) ---")
                for rel in result['related_docs']:
                    print(f"\n  --- Related Concept: {rel['id']} ---")
                    print(rel['summary']) 