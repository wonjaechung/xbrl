import os
import pickle
import networkx as nx
import re
from datetime import datetime

# Simulated LangChain-like functionality without dependencies
class SimpleRetriever:
    def __init__(self, documents_path="all_documents.pkl"):
        with open(documents_path, 'rb') as f:
            self.documents = pickle.load(f)
        self.doc_ids = list(self.documents.keys())

    def invoke(self, query, k=5):  # Increase k for better coverage
        query_words = set(re.findall(r'\w+', query.lower()))
        results = []
        for doc_id, content in self.documents.items():
            content_words = set(re.findall(r'\w+', content.lower()))
            score = len(query_words.intersection(content_words)) / len(query_words) if query_words else 0
            if score > 0.3:  # Threshold
                summary = content.split("## Reported Numerical Facts")[0] if "## Reported Numerical Facts" in content else content[:1000]
                results.append({'id': doc_id, 'content': summary, 'score': score})
        return sorted(results, key=lambda x: x['score'], reverse=True)[:k]

class SimpleGraphInspector:
    def __init__(self, graph_path="xbrl_kg.graphml"):
        self.G = nx.read_graphml(graph_path)

    def invoke(self, concept_id):
        if concept_id not in self.G:
            return f"Concept '{concept_id}' not found in graph."
        parents = list(self.G.predecessors(concept_id))
        children = list(self.G.successors(concept_id))
        return (f"Concept: {concept_id}\nParents:\n" + "\n".join([f"- {p}" for p in parents]) + 
                f"\nChildren:\n" + "\n".join([f"- {c}" for c in children]) or "\nNo relationships.")

class FinancialAgent:
    def __init__(self, documents_path="all_documents.pkl", graph_path="xbrl_kg.graphml"):
        self.retriever = SimpleRetriever(documents_path)
        self.graph = SimpleGraphInspector(graph_path)
        self.documents = self.retriever.documents

    def answer(self, query):
        # Normalize query
        query = query.lower().strip()
        is_korean = any(0xAC00 <= ord(c) <= 0xD7A3 for c in query)

        # Map common Korean terms to English
        ko_map = {
            '매출': 'revenue', '수익': 'revenue', '부문별': 'segment', '이번분기': 'Q1 2025',
            '감가상각비': 'depreciation', '상각비': 'amortisation'
        }
        for ko, en in ko_map.items():
            query = query.replace(ko, en)

        # Step 1: Retrieve top docs
        docs = self.retriever.invoke(query, k=5)
        if not docs:
            return "No relevant documents found. Try rephrasing."

        # Step 2: Filter for relevance (e.g., exact concept match)
        target_concepts = ['ifrs-full:Revenue' if 'revenue' in query else None,
                           'ifrs-full:DepreciationExpense' if 'depreciation' in query else None,
                           'entity00413046:AmortisationExpense' if 'amortisation' in query else None]
        target_concepts = [c for c in target_concepts if c]
        best_docs = [d for d in docs if d['id'] in target_concepts] or docs[:3]

        # Step 3: Extract answer (prioritize summaries/facts)
        answer = []
        for doc in best_docs:
            doc_id = doc['id']
            content = doc['content']
            answer.append(f"Concept: {doc_id}\n{content}")

            # Step 4: Graph traversal for segments/related
            if 'segment' in query or '부문별' in query:
                graph_info = self.graph.invoke(doc_id)
                answer.append(f"\nRelated Relationships:\n{graph_info}")

        response = "\n---\n".join(answer)
        if not response:
            return "No relevant data found. Try a more specific query."
        return response

def main():
    if not os.path.exists("all_documents.pkl") or not os.path.exists("xbrl_kg.graphml"):
        print("Error: Required files missing. Run vector_database.py first.")
        return

    agent = FinancialAgent()
    print("\n--- Financial Analyst Agent (Simplified) ---")
    print("Ask questions (e.g., 'What is the revenue?', '부문별매출'). Type 'exit' to quit.")

    while True:
        query = input("\nYour question: ")
        if query.lower() == 'exit':
            break
        print("\n--- Answer ---")
        print(agent.answer(query))

if __name__ == '__main__':
    main()