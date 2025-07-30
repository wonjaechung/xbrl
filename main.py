# main.py

import os
import pickle
from UnifiedXBRLParser import UnifiedXBRLParser
from DocumentGenerator import DocumentGenerator
from StatementGenerator import StatementGenerator

def main():
    """
    Main execution script to run the XBRL parser and document generator.
    """
    # --- Configuration ---
    # Define the folder where your data files are located.
    data_folder = './data'
    output_folder = './output/concept_details'
    
    # Ensure the output directory exists
    os.makedirs(output_folder, exist_ok=True)

    # Define the paths to all the necessary XBRL and taxonomy files.
    file_paths = {
        'concepts': os.path.join(data_folder, 'Concepts.csv'),
        'labels_ko': os.path.join(data_folder, 'entity00413046_2025-03-31_lab-ko.xml'),
        'labels_en': os.path.join(data_folder, 'entity00413046_2025-03-31_lab-en.xml'),
        'presentation_xml': os.path.join(data_folder, 'entity00413046_2024-12-31_pre.xml'),
        'calculation': os.path.join(data_folder, 'Calculation Link.csv'),
        'instance': os.path.join(data_folder, 'entity00413046_2025-03-31.xbrl'),
        'taxonomy_labels': os.path.join(data_folder, 'Label Link.csv'),
        'references': os.path.join(data_folder, 'Reference Link.csv'),
        'role_types': os.path.join(data_folder, 'RoleTypes.csv')
    }

    # --- Step 1: Run the Unified XBRL Parser ---
    print("--- Running Unified XBRL Parser ---")
    parser = UnifiedXBRLParser(file_paths)
    unified_data = parser.run_parser()
    
    # Add file paths to the data for reference in the generator
    unified_data['__file_paths__'] = file_paths
    print("-" * 50)

    # --- Step 2: Generate Enhanced Analytical Documents FIRST ---
    # This is now a prerequisite for the statement generator
    print("\n--- Generating Enhanced Analytical Documents ---")
    doc_generator = DocumentGenerator(unified_data)
    all_documents = doc_generator.generate_all_documents()
    print("-" * 50)

    # --- Step 3: Generate Core Financial Statements ---
    # This now uses the documents generated in the previous step
    print("\n--- Generating Core Financial Statements ---")
    statement_gen = StatementGenerator(parser, all_documents)
    
    # Define the statements to generate by their role ID, found in RoleTypes.csv or the report itself.
    # [D310000] is typically the Income Statement.
    statements_to_generate = {
        'Consolidated Income Statement': 'http://dart.fss.or.kr/role/ifrs/dart_2024-06-30_role-D310000'
        # Add other statements here by their Role URI, e.g.,
        # 'Balance Sheet': 'http://dart.fss.or.kr/role/ifrs/dart_2024-06-30_role-D210000'
    }
    
    # Define the period and dimensions for the statements
    period_end_date = '2025-03-31'
    dimensions = {
        'ifrs-full:ConsolidatedAndSeparateFinancialStatementsAxis': 'ifrs-full:ConsolidatedMember'
    }

    for name, role_uri in statements_to_generate.items():
        print(f"  - Generating: {name}")
        statement_md = statement_gen.generate_statement(role_uri, period_end_date, dimensions)
        
        # Sanitize filename
        filename = name.replace(" ", "_") + ".md"
        filepath = os.path.join(output_folder, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(statement_md)

    # --- Step 4: Save Concept Documents ---
    # Save individual Markdown files
    print(f"\n--- Saving {len(all_documents)} Documents to '{output_folder}/concept_details' ---")
    concept_output_folder = os.path.join(output_folder, 'concept_details')
    os.makedirs(concept_output_folder, exist_ok=True)

    for concept_id, doc_content in all_documents.items():
        # Sanitize the concept_id to be a valid filename
        filename = concept_id.replace(":", "_").replace("/", "_")

        # Truncate filenames that are too long to prevent filesystem errors
        if len(filename) > 200:
            filename = filename[:200]
        
        filename += ".md"
        
        filepath = os.path.join(concept_output_folder, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(doc_content)
    
    # Save all documents to a single pickle file for efficient loading elsewhere
    pickle_path = 'all_documents.pkl'
    print(f"\n--- Saving all documents to '{pickle_path}' ---")
    with open(pickle_path, 'wb') as f:
        pickle.dump(all_documents, f)

    print("\n--- Process Finished Successfully ---")
    print(f"✅  {len(all_documents)} analytical documents have been generated and saved.")

if __name__ == '__main__':
    main()