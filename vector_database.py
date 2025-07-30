import os
import pickle
import networkx as nx

from document_generator import DocumentGenerator
from xbrl_parser_poc.UnifiedXBRLParser import UnifiedXBRLParser
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings


class KnowledgeGraphBuilder:
    def __init__(self, unified_data, doc_ids):
        self.unified_data = unified_data
        self.doc_ids = doc_ids
        self.G = None

    def build_graph(self):
        """Builds a NetworkX graph with enriched nodes and bidirectional edges."""
        if not self.unified_data:
            raise ValueError("No unified_data provided for graph building.")
            
        self.G = nx.DiGraph()
        for doc_id in self.doc_ids:
            attrs = self.unified_data.get(doc_id, {})
            self.G.add_node(doc_id, 
                            label=attrs.get('labels', {}).get('taxonomy_en_label', doc_id),
                            ko_label=attrs.get('labels', {}).get('taxonomy_ko_label', ''),
                            facts=len(attrs.get('reported_facts', {}).get('numerical_facts', [])))

        for concept_id, data in self.unified_data.items():
            if concept_id not in self.G: continue
            relationships = data.get('relationships', {})
            for rel_type, parents in relationships.items():
                for parent_info in parents:
                    parent_id = parent_info.get('parent')
                    if parent_id and self.G.has_node(parent_id):
                        edge_attrs = {'type': rel_type}
                        if 'weight' in parent_info:
                            edge_attrs['weight'] = float(parent_info.get('weight', 1.0))
                        
                        self.G.add_edge(concept_id, parent_id, **edge_attrs)
                        
                        reverse_attrs = {'type': f'has_{rel_type.split("_")[0]}'}
                        self.G.add_edge(parent_id, concept_id, **reverse_attrs)

        nx.write_graphml(self.G, "xbrl_kg.graphml")
        print("Knowledge graph built and saved to xbrl_kg.graphml")
        
        isolates = list(nx.isolates(self.G))
        if isolates:
            print(f"Warning: {len(isolates)} isolated nodes (no relationships found).")

if __name__ == '__main__':
    print("--- Running XBRL Parser and Document Generator ---")
    data_folder = './data'
    file_paths = {
        'instance': os.path.join(data_folder, 'entity00413046_2025-03-31.xbrl'),
        'labels_ko': os.path.join(data_folder, 'entity00413046_2025-03-31_lab-ko.xml'),
        'labels_en': os.path.join(data_folder, 'entity00413046_2025-03-31_lab-en.xml'),
        'taxonomy_labels': os.path.join(data_folder, 'Label Link.csv'),
        'references': os.path.join(data_folder, 'Reference Link.csv'),
        'presentation': os.path.join(data_folder, 'Presentation Link.csv'),
        'calculation': os.path.join(data_folder, 'Calculation Link.csv'),
        'concepts': os.path.join(data_folder, 'Concepts.csv'),
    }
    
    parser = UnifiedXBRLParser(file_paths)
    unified_data = parser.run_parser()
    
    doc_generator = DocumentGenerator(unified_data)
    all_documents = doc_generator.generate_all_documents()
    print("-" * 50)

    if all_documents:
        print("\n--- Building Vector Database and Knowledge Graph ---")

        # --- Vector Database (using LangChain) ---
        print("Initializing embedding model...")
        model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
        embedding_function = SentenceTransformerEmbeddings(model_name=model_name)
        
        doc_contents = list(all_documents.values())
        doc_ids = list(all_documents.keys())
        metadatas = [{"id": concept_id} for concept_id in doc_ids]

        print(f"Creating FAISS index for {len(doc_contents)} documents...")
        vector_store = FAISS.from_texts(
            texts=doc_contents,
            embedding=embedding_function,
            metadatas=metadatas
        )
        
        vector_store.save_local("xbrl_index")
        print("FAISS index saved to 'xbrl_index' directory.")

        # --- Knowledge Graph ---
        print("\nBuilding knowledge graph...")
        kg_builder = KnowledgeGraphBuilder(unified_data=unified_data, doc_ids=list(all_documents.keys()))
        kg_builder.build_graph()

        # --- Save documents for Q&A context ---
        with open("all_documents.pkl", 'wb') as f:
            pickle.dump(all_documents, f)
            print("all_documents.pkl saved successfully.")
        
        print("-" * 50)
        print("Vector database and knowledge graph creation complete.")
    else:
        print("No documents were generated, skipping database creation.") 