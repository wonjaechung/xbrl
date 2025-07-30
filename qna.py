import os
import pickle
import networkx as nx
from langchain.agents import AgentExecutor, create_react_agent
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAI
from langchain.tools import Tool
from langchain.prompts import PromptTemplate

def create_retriever_tool(k=3):  # Reduced k for precision
    model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
    embeddings = HuggingFaceEmbeddings(model_name=model_name)
    vector_store = FAISS.load_local("xbrl_index", embeddings, allow_dangerous_deserialization=True)
    retriever = vector_store.as_retriever(search_kwargs={"k": k})

    def retrieve_and_summarize(query: str) -> str:
        ko_map = {'매출': 'revenue', '수익': 'revenue', '부문별': 'segment', '이번분기': 'Q1 2025', '감가상각비': 'depreciation', '상각비': 'amortisation'}
        translated_query = query.lower()
        for ko, en in ko_map.items():
            translated_query = translated_query.replace(ko, en)

        docs = retriever.invoke(translated_query)
        if not docs:
            return "No relevant documents found."

        summaries = []
        for doc in docs:
            concept_id = doc.metadata.get('id', 'N/A')
            # Strict filtering for revenue
            if 'revenue' in translated_query and concept_id != 'ifrs-full:Revenue':
                continue
            content = doc.page_content
            summary_parts = []
            # Always include summary
            if "## Analytical Summary" in content:
                summary_text = content.split("## Analytical Summary")[1].split("## Reported Numerical Facts")[0]
                summary_parts.append(f"Summary:\n{summary_text.strip()}")
            # Include facts for segment queries
            if "segment" in translated_query or "부문별" in query:
                if "## Reported Numerical Facts" in content:
                    facts_text = content.split("## Reported Numerical Facts")[1].split("##")[0]
                    summary_parts.append(f"Segment Facts:\n{facts_text.strip()}")
            # Include Q1 2025 for specific period
            if "Q1 2025" in translated_query or "이번분기" in query:
                if "## Reported Numerical Facts" in content:
                    facts_text = content.split("## Reported Numerical Facts")[1].split("##")[0]
                    summary_parts.append(f"Q1 2025 Facts:\n{facts_text.strip()}")
            summaries.append(f"Concept: {concept_id}\n\n" + "\n\n".join(summary_parts))
        return "\n\n---\n\n".join(summaries) or "No relevant data found."

    return Tool(
        name="Financial Concept Retriever",
        func=retrieve_and_summarize,
        description="Retrieve financial concepts, values, and segment breakdowns."
    )

def create_graph_inspector_tool(graph_path="xbrl_kg.graphml"):
    G = nx.read_graphml(graph_path)

    def inspect_relationships(concept_id: str) -> str:
        if concept_id not in G:
            return f"Concept '{concept_id}' not found."
        parents = [p for p, _ in G.in_edges(concept_id, data=True) if G[p][concept_id]['type'] == 'has_presentation']
        children = [c for _, c in G.out_edges(concept_id, data=True) if G[concept_id][c]['type'] == 'has_presentation']
        return (f"Concept: {concept_id}\nParents:\n" + "\n".join([f"- {p}" for p in parents]) + 
                f"\nChildren:\n" + "\n".join([f"- {c}" for c in children]) or "\nNo relationships.")

    return Tool(
        name="Knowledge Graph Inspector",
        func=inspect_relationships,
        description="Explore relationships, especially for segment breakdowns (use with 'ifrs-full:Revenue')."
    )

def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set.")
        return

    llm = OpenAI(temperature=0, model_name="gpt-3.5-turbo")
    tools = [create_retriever_tool(), create_graph_inspector_tool()]
    prompt_template = """
    You are a financial analyst answering questions about XBRL data. Use the provided tools to retrieve precise data and relationships. Cite values in KRW and concept IDs. Translate Korean terms (e.g., '매출' to 'revenue', '부문별' to 'segment', '이번분기' to 'Q1 2025'). Always prioritize 'ifrs-full:Revenue' for revenue queries. For segment queries, use the Knowledge Graph Inspector with 'ifrs-full:Revenue' to find related concepts.

    Tools:
    - Financial Concept Retriever: For values, summaries, and segment facts.
    - Knowledge Graph Inspector: For relationships (e.g., segment breakdowns).

    Instructions:
    1. Translate Korean terms to English for better retrieval.
    2. For 'revenue' or '매출', use Retriever with 'ifrs-full:Revenue'.
    3. For 'segment' or '부문별', use Retriever for facts and Inspector for relationships.
    4. For 'Q1 2025' or '이번분기', focus on 2025-01-01 to 2025-03-31 facts.
    5. If no data, suggest rephrasing with specific terms.
    6. Answer concisely, citing concept IDs and KRW values.

    Question: {question}

    Answer format:
    Answer: [Your answer here, citing values in KRW and concept IDs]
    Sources: [List concept IDs]
    """
    prompt = PromptTemplate(template=prompt_template, input_variables=["question"])
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    print("\n--- Financial Analyst Agent ---")
    print("Ask questions (e.g., 'What is the revenue?', '부문별매출', '이번분기 매출 얼마야?'). Type 'exit' to quit.")

    while True:
        query = input("\nYour question: ")
        if query.lower() == 'exit':
            break
        result = agent_executor.invoke({"input": query})
        print("\n--- Answer ---")
        print(result["output"])

if __name__ == '__main__':
    main()