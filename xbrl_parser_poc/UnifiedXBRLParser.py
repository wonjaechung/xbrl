# Concepts to test: 

#### Numerical Facts (e.g., ifrs-full:Revenue)
#### General Text Blocks / Notes (e.g., ifrs-full:DisclosureOfOperatingSegmentsExplanatory)
#### Specific Footnotes (e.g., entity00413046_FootnoteOfOperatingSegments)

import pandas as pd
import xml.etree.ElementTree as ET
import re
import collections
import json

class UnifiedXBRLParser:
    """
    A unified parser to process Korean XBRL taxonomy files and a specific company's
    XBRL instance data. It merges taxonomy information (concepts, labels, relationships)
    with reported financial data, including narrative text blocks.
    """

    def __init__(self, file_paths):
        """
        Initializes the parser with paths to the required files.

        Args:
            file_paths (dict): A dictionary containing the paths to all necessary files.
        """
        self.file_paths = file_paths
        self.taxonomy_data = {}
        self.contexts = {}
        self.namespaces = {}

    def _get_namespaces(self, file_path):
        """Extracts all namespaces from an XML file to use in XPath queries."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        ns_declarations = re.findall(r'\sxmlns:([^=]+)="([^"]+)"', content)
        default_ns = re.search(r'\sxmlns="([^"]+)"', content)
        if default_ns:
            ns_declarations.append(('xbrli', default_ns.group(1)))
            
        return dict(ns_declarations)

    def _get_label_for_concept(self, concept_id, lang='en'):
        """Helper function to find the best available label for a concept."""
        if concept_id in self.taxonomy_data:
            labels = self.taxonomy_data[concept_id].get('labels', {})
            label_priority = [
                f'taxonomy_{lang}_label', f'instance_{lang}_label',
                'taxonomy_en_label', 'instance_en_label'
            ]
            for label_key in label_priority:
                if label_key in labels:
                    return labels[label_key]
        return concept_id

    def parse_concepts(self):
        """Parses the Concepts.csv file."""
        try:
            df = pd.read_csv(self.file_paths['concepts'])
            df['id'] = df['prefix'] + ':' + df['name']
            for _, row in df.iterrows():
                concept_id = row['id']
                if concept_id not in self.taxonomy_data:
                    self.taxonomy_data[concept_id] = collections.defaultdict(lambda: collections.defaultdict(list))
                
                self.taxonomy_data[concept_id]['id'] = concept_id
                self.taxonomy_data[concept_id]['attributes']['balance_type'] = row.get('balance')
                self.taxonomy_data[concept_id]['attributes']['period_type'] = row.get('periodType')
                self.taxonomy_data[concept_id]['attributes']['data_type'] = row.get('type')
                self.taxonomy_data[concept_id]['attributes']['is_abstract'] = row.get('abstract')

            print(f"Successfully parsed {len(df)} concepts.")
        except KeyError as e:
            print(f"Error parsing concepts: A required column is missing. Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while parsing concepts: {e}")
            
    def _parse_contexts(self):
        """Parses and translates the context elements from the instance file."""
        try:
            tree = ET.parse(self.file_paths['instance'])
            root = tree.getroot()
            
            for context in root.findall('{*}context'):
                context_id = context.get('id')
                period = context.find('{*}period')
                if period is None: continue

                instant = period.find('{*}instant')
                start_date = period.find('{*}startDate')
                end_date = period.find('{*}endDate')

                translated_dimensions = {}
                for dim in context.findall('.//{*}explicitMember'):
                    dimension_id = dim.get('dimension')
                    member_id = dim.text
                    dimension_label = self._get_label_for_concept(dimension_id)
                    member_label = self._get_label_for_concept(member_id)
                    translated_dimensions[dimension_label] = member_label

                self.contexts[context_id] = {
                    'period': instant.text if instant is not None else f"{start_date.text} to {end_date.text}",
                    'dimensions': translated_dimensions
                }
            print(f"Successfully parsed and translated {len(self.contexts)} contexts.")
        except Exception as e:
            print(f"Error parsing contexts: {e}")

    def _parse_xml_labels(self, file_path, lang, source="instance"):
        """Helper to parse XML label files."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            xlink_ns = "http://www.w3.org/1999/xlink"
            link_ns = "http://www.xbrl.org/2003/linkbase"
            
            locs = {loc.get(f"{{{xlink_ns}}}label"): loc.get(f"{{{xlink_ns}}}href").split('#')[-1] for loc in root.findall(f'.//{{{link_ns}}}loc')}
            
            for arc in root.findall(f'.//{{{link_ns}}}labelArc'):
                from_loc = arc.get(f"{{{xlink_ns}}}from")
                to_loc = arc.get(f"{{{xlink_ns}}}to")
                
                if from_loc in locs and to_loc:
                    concept_id = locs[from_loc]
                    label_element = root.find(f".//{{{link_ns}}}label[@{{{xlink_ns}}}label='{to_loc}']")
                    if label_element is not None and label_element.text:
                        label_text = label_element.text.strip()
                        label_role_uri = label_element.get(f"{{{xlink_ns}}}role")
                        label_role = label_role_uri.split('/')[-1] if label_role_uri else 'label'

                        if concept_id not in self.taxonomy_data:
                            self.taxonomy_data[concept_id] = collections.defaultdict(lambda: collections.defaultdict(list))
                        
                        # Store by a more predictable key, e.g., 'ko_documentation'
                        key_name = f'{lang}_{label_role}'
                        if label_role == 'label':
                            key_name = f'instance_{lang}_label'
                        
                        self.taxonomy_data[concept_id]['labels'][key_name] = label_text

            print(f"Successfully parsed {lang} labels from {source}.")
        except Exception as e:
            print(f"Error parsing {lang} labels from {file_path}: {e}")

    def parse_taxonomy_labels(self):
        """Parses the main Label Link.csv for standard labels."""
        try:
            df = pd.read_csv(self.file_paths['taxonomy_labels'], skiprows=3, on_bad_lines='skip')
            df['id'] = df['prefix'] + ':' + df['name']
            
            for _, row in df.iterrows():
                concept_id = row['id']
                if concept_id in self.taxonomy_data:
                    if pd.notna(row.get('label')):
                        self.taxonomy_data[concept_id]['labels']['taxonomy_ko_label'] = row['label']
                    if pd.notna(row.get('label.1')):
                        self.taxonomy_data[concept_id]['labels']['taxonomy_en_label'] = row['label.1']

            print(f"Successfully parsed taxonomy labels.")
        except Exception as e:
            print(f"Error parsing taxonomy labels: {e}")
            
    def parse_references(self):
        """Parses the Reference Link.csv to add accounting standard references."""
        try:
            df = pd.read_csv(self.file_paths['references'], skiprows=3, on_bad_lines='skip')
            df['id'] = df['prefix'] + ':' + df['name']
            
            for _, row in df.iterrows():
                concept_id = row['id']
                if concept_id in self.taxonomy_data:
                    ref = {
                        "name": row.get('Name'),
                        "number": row.get('Number'),
                        "paragraph": row.get('Paragraph'),
                        "uri": row.get('URI')
                    }
                    self.taxonomy_data[concept_id]['references']['accounting_standard'].append(ref)
            print("Successfully parsed references.")
        except Exception as e:
            print(f"Error parsing references: {e}")

    def parse_instance_facts(self):
        """Parses the main XBRL instance file, capturing both numerical facts and text blocks."""
        try:
            tree = ET.parse(self.file_paths['instance'])
            root = tree.getroot()
            
            for fact in root:
                if 'context' in fact.tag or 'unit' in fact.tag or 'Ref' in fact.tag:
                    continue

                tag_parts = fact.tag.split('}')
                if len(tag_parts) > 1:
                    ns_uri = tag_parts[0][1:]
                    local_name = tag_parts[1]
                    prefix = next((p for p, u in self.namespaces.items() if u == ns_uri), None)
                    if not prefix: continue
                    concept_id = f"{prefix}:{local_name}"
                else:
                    continue

                if fact.text:
                    # Ensure concept exists in our main dictionary
                    if concept_id not in self.taxonomy_data:
                        self.taxonomy_data[concept_id] = collections.defaultdict(lambda: collections.defaultdict(list))
                        self.taxonomy_data[concept_id]['id'] = concept_id

                    context_ref = fact.get('contextRef')
                    data_type = self.taxonomy_data[concept_id].get('attributes', {}).get('data_type')

                    # Heuristic: If data_type is unknown, but it has no unitRef, treat as text.
                    # This handles custom extension concepts like company-specific footnotes.
                    is_text_block = 'textBlockItemType' in str(data_type)
                    if data_type is None and fact.get('unitRef') is None:
                        is_text_block = True

                    if is_text_block:
                        self.taxonomy_data[concept_id]['reported_facts']['text_blocks'].append({
                            'text': fact.text.strip(),
                            'context': self.contexts.get(context_ref, {})
                        })
                    else: # Otherwise, treat as a numerical fact
                        self.taxonomy_data[concept_id]['reported_facts']['numerical_facts'].append({
                            'value': fact.text.strip(),
                            'unit_ref': fact.get('unitRef'),
                            'decimals': fact.get('decimals'),
                            'context': self.contexts.get(context_ref, {})
                        })
            print(f"Successfully parsed and contextualized instance facts (including text blocks).")
        except Exception as e:
            print(f"Error parsing instance file: {e}")

    def _parse_linkbase(self, file_path, relationship_type):
        """Generic parser for Presentation and Calculation linkbases, removing duplicates."""
        try:
            df = pd.read_csv(file_path, header=None, encoding='utf-8', on_bad_lines='skip')
            header_row_index = -1
            for i, row in df.iterrows():
                row_str = ''.join(map(str, row.values))
                if 'prefix' in row_str and 'name' in row_str and 'parent' in row_str:
                    header_row_index = i
                    break
            
            if header_row_index == -1:
                print(f"Could not find a valid header row in {file_path}")
                return

            df = pd.read_csv(file_path, header=header_row_index, encoding='utf-8', on_bad_lines='skip')
            df = df.dropna(subset=['prefix', 'name', 'parent'])
            df['id'] = df['prefix'] + ':' + df['name']

            temp_relations = collections.defaultdict(set)

            for _, row in df.iterrows():
                child_id = row['id']
                parent_id = row['parent']
                
                if child_id in self.taxonomy_data:
                    weight = row.get('weight') if 'weight' in row else None
                    rel_tuple = (parent_id, weight) if weight is not None else (parent_id,)
                    temp_relations[child_id].add(rel_tuple)
            
            for child_id, relations in temp_relations.items():
                for rel in relations:
                    rel_info = {'parent': rel[0]}
                    if len(rel) > 1 and rel[1] is not None:
                        rel_info['weight'] = str(rel[1]).strip()
                    self.taxonomy_data[child_id]['relationships'][relationship_type].append(rel_info)

            print(f"Successfully parsed {relationship_type} relationships.")
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")

    def run_parser(self):
        """Executes all parsing steps in the correct order."""
        print("--- Starting Unified XBRL Parser ---")
        self.namespaces = self._get_namespaces(self.file_paths['instance'])
        
        self.parse_concepts()
        self.parse_taxonomy_labels()
        self._parse_xml_labels(self.file_paths['labels_ko'], 'ko')
        self._parse_xml_labels(self.file_paths['labels_en'], 'en')
        
        self.parse_references()
        self._parse_linkbase(self.file_paths['presentation'], 'presentation_parent')
        self._parse_linkbase(self.file_paths['calculation'], 'calculation_parent')
        
        self._parse_contexts()
        self.parse_instance_facts()
        
        print("--- Parser finished successfully ---")
        return self.taxonomy_data

# --- Example Usage ---
if __name__ == '__main__':
    # NOTE: You must replace these with the actual paths to your files.
    file_paths = {
        'concepts': 'Concepts.csv',
        'labels_ko': 'entity00413046_2025-03-31_lab-ko.xml',
        'labels_en': 'entity00413046_2025-03-31_lab-en.xml',
        'presentation': 'Presentation Link.csv',
        'calculation': 'Calculation Link.csv',
        'instance': 'entity00413046_2025-03-31.xbrl',
        'taxonomy_labels': 'Label Link.csv',
        'references': 'Reference Link.csv'
    }