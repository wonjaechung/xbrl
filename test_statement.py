# test_statement.py

import pickle
from StatementGenerator import StatementGenerator
from UnifiedXBRLParser import UnifiedXBRLParser

def test_statement_generation():
    """Test script to debug the statement generation process."""
    
    # Load the existing data
    with open('all_documents.pkl', 'rb') as f:
        all_documents = pickle.load(f)
    
    # Set up file paths
    data_folder = './data'
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
    
    # Initialize parser
    parser = UnifiedXBRLParser(file_paths)
    parser.run_parser()
    
    # Initialize statement generator
    statement_gen = StatementGenerator(parser, all_documents)
    
    # Test parameters
    role_uri = 'http://dart.fss.or.kr/role/ifrs/dart_2024-06-30_role-D310000'
    period_end_date = '2025-03-31'
    dimensions = {
        'ifrs-full:ConsolidatedAndSeparateFinancialStatementsAxis': 'ifrs-full:ConsolidatedMember'
    }
    
    print("=== DEBUGGING STATEMENT GENERATION ===")
    print(f"Role URI: {role_uri}")
    print(f"Period: {period_end_date}")
    print(f"Dimensions: {dimensions}")
    print()
    
    # Check if role exists
    if role_uri in statement_gen.role_definitions:
        print(f"✓ Role found: {statement_gen.role_definitions[role_uri]}")
    else:
        print(f"✗ Role not found. Available roles:")
        for uri, name in list(statement_gen.role_definitions.items())[:5]:
            print(f"  - {uri}: {name}")
        return
    
    # Check presentation links
    if role_uri in statement_gen.presentation_links:
        print(f"✓ Found {len(statement_gen.presentation_links[role_uri])} presentation links")
        
        # Show first few concepts
        for i, link in enumerate(statement_gen.presentation_links[role_uri][:5]):
            print(f"  {i+1}. {link['parent']} -> {link['child']}")
    else:
        print("✗ No presentation links found for this role")
        return
    
    # Test getting a specific concept's value
    test_concept = 'ifrs-full:Revenue'
    print(f"\n=== TESTING VALUE EXTRACTION FOR {test_concept} ===")
    
    if test_concept in all_documents:
        print("✓ Concept document found")
        value = statement_gen._get_fact_value(test_concept, period_end_date, dimensions)
        print(f"Extracted value: {value}")
        
        # Show the search pattern
        context_id_string = " and ".join([f"{k}: {v}" for k, v in sorted(dimensions.items())])
        search_pattern = f"### **Context: {context_id_string}**"
        print(f"Search pattern: {search_pattern}")
        
        # Show if pattern exists in document
        doc_content = all_documents[test_concept]
        if search_pattern in doc_content:
            print("✓ Search pattern found in document")
        else:
            print("✗ Search pattern NOT found in document")
            print("Available context headers:")
            import re
            headers = re.findall(r'<!-- Context \(IDs\): .*? -->', doc_content)
            for header in headers[:3]:
                print(f"  - {header}")
            
            # Let's try a simple string search
            simple_pattern = f"### **Context: {context_id_string}**"
            if simple_pattern in doc_content:
                print(f"✓ Simple pattern found: {simple_pattern}")
            else:
                print(f"✗ Simple pattern not found: {simple_pattern}")
    else:
        print(f"✗ Concept document not found for {test_concept}")
    
    print("\n=== GENERATING STATEMENT ===")
    statement = statement_gen.generate_statement(role_uri, period_end_date, dimensions)
    print(statement)

if __name__ == '__main__':
    import os
    test_statement_generation() 