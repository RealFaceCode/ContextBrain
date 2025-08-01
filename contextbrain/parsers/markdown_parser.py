"""
Markdown Language Parser for ContextBrain

Specialized parser for Markdown documents that extracts document structure,
headings, and content sections for enhanced searchability and context understanding.
"""

import re
import logging
from typing import List, Optional, Dict, Tuple

from .base import LanguageParser
from ..models import (
    CodeElement,
    ElementType,
    SourceLocation,
    ElementMetadata,
)

logger = logging.getLogger(__name__)


class MarkdownParser(LanguageParser):
    """
    Markdown parser for extracting document structure and headings.
    
    Features:
    - ATX-style heading extraction (# ## ### #### ##### ######)
    - Setext-style heading extraction (=== and --- underlines)
    - Document hierarchy and parent-child relationships
    - Content section extraction for each heading
    - Inline Markdown syntax handling in headings
    """
    
    def __init__(self):
        """Initialize the Markdown parser."""
        super().__init__()
        self.language_name = "markdown"
        self.current_file_path = ""
        self.current_content = ""
        self.current_lines = []
        
        # Regex patterns for heading detection
        self.atx_heading_pattern = re.compile(r'^(#{1,6})\s+(.+?)(?:\s*#+\s*)?$', re.MULTILINE)
        self.setext_h1_pattern = re.compile(r'^(.+)\n=+\s*$', re.MULTILINE)
        self.setext_h2_pattern = re.compile(r'^(.+)\n-+\s*$', re.MULTILINE)
        
        # Pattern to detect code blocks (to ignore headings inside them)
        self.code_block_pattern = re.compile(r'```[\s\S]*?```|`[^`\n]+`', re.MULTILINE)
        
        # Pattern to clean inline Markdown from heading text
        self.inline_markdown_pattern = re.compile(r'\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\([^)]+\)')
    
    async def parse_file(self, content: str, file_path: str) -> List[CodeElement]:
        """
        Parse a Markdown file and extract document structure.
        
        Args:
            content: Markdown source code content
            file_path: Path to the source file
            
        Returns:
            List of CodeElement objects representing headings and structure
        """
        self.current_file_path = file_path
        self.current_content = content
        self.current_lines = content.split('\n')
        
        elements = []
        
        try:
            # Extract all headings with their positions and levels
            headings = self._extract_all_headings(content)
            
            if not headings:
                logger.debug(f"No headings found in {file_path}")
                return elements
            
            # Sort headings by line number to maintain document order
            headings.sort(key=lambda h: h['line_number'])
            
            # Build hierarchy and extract content sections
            hierarchy = self._build_heading_hierarchy(headings)
            
            # Create CodeElement objects for each heading
            for i, heading_info in enumerate(headings):
                element = self._create_heading_element(heading_info, hierarchy, headings, i)
                if element:
                    elements.append(element)
            
            logger.debug(f"Extracted {len(elements)} heading elements from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to parse Markdown file {file_path}: {e}")
        
        return elements
    
    def _extract_all_headings(self, content: str) -> List[Dict]:
        """Extract all headings from the content with their metadata."""
        headings = []
        
        # Remove code blocks to avoid false positives
        content_without_code = self.code_block_pattern.sub('', content)
        
        # Extract ATX-style headings (# ## ### etc.)
        for match in self.atx_heading_pattern.finditer(content_without_code):
            level = len(match.group(1))  # Count the # characters
            text = match.group(2).strip()
            
            # Find the line number in original content
            line_number = content[:match.start()].count('\n') + 1
            
            headings.append({
                'level': level,
                'text': text,
                'clean_text': self._clean_heading_text(text),
                'line_number': line_number,
                'type': 'atx',
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        # Extract Setext-style H1 headings (underlined with ===)
        for match in self.setext_h1_pattern.finditer(content_without_code):
            text = match.group(1).strip()
            line_number = content[:match.start()].count('\n') + 1
            
            headings.append({
                'level': 1,
                'text': text,
                'clean_text': self._clean_heading_text(text),
                'line_number': line_number,
                'type': 'setext_h1',
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        # Extract Setext-style H2 headings (underlined with ---)
        for match in self.setext_h2_pattern.finditer(content_without_code):
            text = match.group(1).strip()
            line_number = content[:match.start()].count('\n') + 1
            
            headings.append({
                'level': 2,
                'text': text,
                'clean_text': self._clean_heading_text(text),
                'line_number': line_number,
                'type': 'setext_h2',
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        return headings
    
    def _clean_heading_text(self, text: str) -> str:
        """Clean inline Markdown syntax from heading text."""
        # Remove bold, italic, code spans, and links
        cleaned = self.inline_markdown_pattern.sub(lambda m: m.group(1) or m.group(2) or m.group(3) or m.group(4), text)
        return cleaned.strip()
    
    def _build_heading_hierarchy(self, headings: List[Dict]) -> Dict[int, Optional[int]]:
        """
        Build parent-child relationships between headings.
        
        Returns:
            Dictionary mapping heading index to parent heading index
        """
        hierarchy = {}
        heading_stack = []  # Stack to track parent headings at each level
        
        for i, heading in enumerate(headings):
            level = heading['level']
            
            # Find the appropriate parent by popping headings of equal or lower level
            while heading_stack and heading_stack[-1]['level'] >= level:
                heading_stack.pop()
            
            # Set parent relationship
            if heading_stack:
                parent_index = heading_stack[-1]['index']
                hierarchy[i] = parent_index
            else:
                hierarchy[i] = None  # Top-level heading
            
            # Add current heading to stack
            heading_stack.append({'level': level, 'index': i})
        
        return hierarchy
    
    def _extract_content_section(self, heading_info: Dict, headings: List[Dict], heading_index: int) -> str:
        """Extract the content section for a heading (from heading to next heading of equal or higher level)."""
        current_level = heading_info['level']
        start_line = heading_info['line_number']
        
        # Find the end line (next heading of equal or higher level)
        end_line = len(self.current_lines)
        for i in range(heading_index + 1, len(headings)):
            next_heading = headings[i]
            if next_heading['level'] <= current_level:
                end_line = next_heading['line_number'] - 1
                break
        
        # Extract content lines (skip the heading line itself)
        content_lines = []
        for line_num in range(start_line, min(end_line + 1, len(self.current_lines))):
            if line_num < len(self.current_lines):
                content_lines.append(self.current_lines[line_num])
        
        # Join and clean up the content
        content = '\n'.join(content_lines).strip()
        
        # Limit content length for storage efficiency
        if len(content) > 2000:
            content = content[:2000] + "..."
        
        return content
    
    def _create_heading_element(self, heading_info: Dict, hierarchy: Dict[int, Optional[int]], all_headings: List[Dict], heading_index: int) -> Optional[CodeElement]:
        """Create a CodeElement for a heading."""
        try:
            level = heading_info['level']
            clean_text = heading_info['clean_text']
            line_number = heading_info['line_number']

            # Determine element type based on heading level
            element_type_map = {
                1: ElementType.H1,
                2: ElementType.H2,
                3: ElementType.H3,
                4: ElementType.H4,
                5: ElementType.H5,
                6: ElementType.H6
            }
            element_type = element_type_map.get(level, ElementType.DOCUMENT_HEADING)

            # Generate unique ID
            normalized_path = self.current_file_path.replace('\\', '/').replace('/', '_')
            safe_text = re.sub(r'[^\w\s-]', '', clean_text).replace(' ', '_').lower()
            element_id = f"heading_{normalized_path}_{level}_{safe_text}_{line_number}"

            # Extract content section
            content_section = self._extract_content_section(heading_info, all_headings, heading_index)

            # Prepare metadata with heading-specific information
            metadata = ElementMetadata(
                language="markdown",
                complexity=1,
                lines_of_code=len(content_section.split('\n')) if content_section else 1
            )

            # Get parent heading ID if exists (for potential future use in dependencies)
            parent_heading_id = None
            if heading_index in hierarchy and hierarchy[heading_index] is not None:
                parent_index = hierarchy[heading_index]
                parent_heading = all_headings[parent_index]
                parent_safe_text = re.sub(r'[^\w\s-]', '', parent_heading['clean_text']).replace(' ', '_').lower()
                parent_heading_id = f"heading_{normalized_path}_{parent_heading['level']}_{parent_safe_text}_{parent_heading['line_number']}"

            # Create the element
            element = CodeElement(
                id=element_id,
                type=element_type,
                name=clean_text,
                content=f"{heading_info['text']}\n\n{content_section}",
                file_path=self.current_file_path,
                location=SourceLocation(
                    line_start=line_number,
                    line_end=line_number,
                    column_start=0,
                    column_end=len(heading_info['text'])
                ),
                metadata=metadata,
                dependencies=[parent_heading_id] if parent_heading_id else []
            )

            return element

        except Exception as e:
            logger.warning(f"Failed to create heading element: {e}")
            return None
