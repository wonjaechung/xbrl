# StatementGenerator.py

import collections
import pandas as pd
from datetime import datetime
import re

class StatementGenerator:
    """
    Generates traditional financial statements (e.g., Income Statement)
    in a structured Markdown format based on parsed XBRL data.
    """
    def __init__(self, parser, all_documents):
        self.parser = parser
        self.all_documents = all_documents
        self.taxonomy = parser.taxonomy_data
        self.presentation_links = self._get_presentation_links(parser)
        self.role_definitions = {role['roleURI']: f"{role['Name_EN']} {role['ID']}" for role in parser.role_definitions}
        self.child_map = self._build_child_map()

    def _get_presentation_links(self, parser):
        """Extracts and organizes presentation links from the parser's XML data."""
        links = collections.defaultdict(list)
        for concept_id, data in self.taxonomy.items():
            if 'relationships' in data and 'presentation_parent' in data['relationships']:
                for rel in data['relationships']['presentation_parent']:
                    parent_id = rel.get('parent')
                    role_uri = rel.get('roleURI')
                    order = rel.get('order', 1.0)
                    if parent_id and role_uri:
                        links[role_uri].append({'parent': parent_id, 'child': concept_id, 'order': order})
        # Sort links by order
        for role_uri in links:
            links[role_uri].sort(key=lambda x: x.get('order', 1.0))
        return links

    def _build_child_map(self):
        child_map = collections.defaultdict(list)
        for role_uri, links in self.presentation_links.items():
            for link in links:
                child_map[(role_uri, link['parent'])].append(link['child'])
        return child_map

    def _get_label(self, concept_id, lang='ko'):
        """Gets the best available label for a concept."""
        return self.parser._get_label_for_concept(concept_id, lang)

    def _get_fact_value(self, concept_id, period_end_date, dimensions):
        """
        Retrieves a numerical fact by parsing it from the generated concept document.
        This is more reliable than querying the complex parser object.
        """
        doc_content = self.all_documents.get(concept_id)
        if not doc_content:
            return None

        # Recreate the exact context ID string that DocumentGenerator would have created.
        if dimensions:
            context_id_string = " and ".join([f"{k}: {v}" for k, v in sorted(dimensions.items())])
            # Search for the exact ID string within the HTML comment
            search_pattern = f"<!-- Context (IDs): {context_id_string} -->"
        else:
            # For Primary Context, there's no ID comment, so we find the header directly
            search_pattern = "### **Context (Labels): Primary Context**"

        # Find the block of text for the correct context using simple string search
        if search_pattern in doc_content:
            # Find the start position
            start_pos = doc_content.find(search_pattern)
            # Find the end position (next context or accounting references)
            end_pos = doc_content.find("### **Context (Labels)", start_pos + len(search_pattern))
            if end_pos == -1:
                end_pos = doc_content.find("## Accounting Standard References", start_pos + len(search_pattern))
            if end_pos == -1:
                end_pos = len(doc_content)
            
            context_block = doc_content[start_pos:end_pos]
        else:
            return None

        # Within that block, find the correct period and extract the value
        # Look for period that ends with the specified date
        period_match = re.search(f"- \\*\\*Period: [^\\n]*to {re.escape(period_end_date)}[^\\n]*\\*\\*[^\\n]*\\n\\s*- \\*\\*Value\\*\\*: ([0-9,.-]+)", context_block)
        if period_match:
            value_str = period_match.group(1).replace(",", "")
            try:
                return float(value_str)
            except (ValueError, TypeError):
                return None
        return None

    def _format_bignum(self, num):
        """Formats a large number with commas."""
        if num is None:
            return ""
        if not isinstance(num, (int, float)):
            return ""
        return f"{num:,.0f}"

    def _generate_rows(self, role_uri, parent_concept, period_end_date, dimensions, level=0):
        """Recursively generates the rows of a financial statement."""
        rows = []
        children = self.child_map.get((role_uri, parent_concept), [])

        for child_concept in children:
            indent = "    " * level
            label = self._get_label(child_concept)
            
            # Convert underscore to colon for concept ID matching
            concept_id_for_search = child_concept.replace('_', ':')
            value = self._get_fact_value(concept_id_for_search, period_end_date, dimensions)
            
            # Don't show rows that are just structural or have no value
            child_rows = self._generate_rows(role_uri, child_concept, period_end_date, dimensions, level + 1)
            
            if value is not None or child_rows:
                amount_str = f"{value:,.0f}" if isinstance(value, (int, float)) else ""
                rows.append(f'| {indent}{label} | {amount_str} |')
                rows.extend(child_rows)
        return rows

    def generate_statement(self, role_uri, period_end_date, dimensions):
        """Generates a complete financial statement for a given role URI."""
        if role_uri not in self.role_definitions:
            return f"# Statement for {role_uri}\\n\\n*Role URI not found.*\\n"

        role_name = self.role_definitions[role_uri]
        statement_title = f"# {role_name}\\n"
        
        all_children = {link['child'] for link in self.presentation_links.get(role_uri, [])}
        all_parents = {link['parent'] for link in self.presentation_links.get(role_uri, [])}
        root_concepts = sorted(list(all_parents - all_children))

        table = "| Account | Amount |\\n|---|---|\\n"
        for root in root_concepts:
             table_rows = self._generate_rows(role_uri, root, period_end_date, dimensions, level=0)
             if table_rows:
                table += "\\n".join(table_rows) + "\\n"

        if not root_concepts:
            return f"{statement_title}\\n*Could not find a root concept to start the statement.*\\n"

        return statement_title + table 