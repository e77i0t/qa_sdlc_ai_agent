import re
import logging
from bs4 import BeautifulSoup
import streamlit as st
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

def optimize_prd_content(html_content: str, optimization_level: str = "medium") -> str:
    """
    Optimize PRD HTML content to reduce token count while preserving context.

    Args:
        html_content: Original HTML content
        optimization_level: Level of optimization (low, medium, high)

    Returns:
        Optimized HTML content
    """
    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for element in soup(["script", "style"]):
            element.decompose()

        # Remove comments
        for comment in soup.find_all(text=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()

        # Apply optimization based on level
        if optimization_level == "low":
            # Minimal optimization: just remove scripts, styles, and comments
            pass

        elif optimization_level == "medium":
            # Medium optimization: also simplify HTML structure

            # Remove unnecessary attributes
            for tag in soup.find_all(True):
                attrs_to_keep = ['id', 'class', 'href', 'src', 'alt']
                attrs_to_remove = [attr for attr in tag.attrs if attr not in attrs_to_keep]
                for attr in attrs_to_remove:
                    del tag.attrs[attr]

            # Simplify whitespace
            for tag in soup.find_all(text=True):
                if tag.parent.name not in ['pre', 'code']:
                    tag.replace_with(re.sub(r'\s+', ' ', tag.strip()))

        elif optimization_level == "high":
            # High optimization: more aggressive content reduction

            # Remove all attributes except href for links
            for tag in soup.find_all(True):
                attrs_to_keep = ['href'] if tag.name == 'a' else []
                attrs_to_remove = [attr for attr in tag.attrs if attr not in attrs_to_keep]
                for attr in attrs_to_remove:
                    del tag.attrs[attr]

            # Convert divs and spans to simpler tags
            for tag in soup.find_all(['div', 'span']):
                tag.name = 'p' if tag.name == 'div' else 'span'

            # Replace complex lists with simple bullet points
            for ul in soup.find_all('ul'):
                items = ul.find_all('li')
                bullet_list = soup.new_tag('p')
                for i, item in enumerate(items):
                    bullet_text = f"• {item.get_text().strip()}"
                    if i > 0:
                        bullet_list.append("\n")
                    bullet_list.append(bullet_text)
                ul.replace_with(bullet_list)

            # Replace tables with simplified text
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                table_text = soup.new_tag('div')

                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    row_text = " | ".join(cell.get_text().strip() for cell in cells)
                    row_p = soup.new_tag('p')
                    row_p.string = row_text
                    table_text.append(row_p)

                table.replace_with(table_text)

        # Get optimized HTML
        optimized_html = str(soup)

        # Calculate token reduction (rough estimate)
        original_tokens = len(html_content) / 4  # Rough token estimate
        optimized_tokens = len(optimized_html) / 4
        reduction = (1 - (optimized_tokens / original_tokens)) * 100

        logger.info(f"PRD optimization: {reduction:.1f}% token reduction")

        return optimized_html

    except Exception as e:
        logger.error(f"Error optimizing PRD: {e}")
        return html_content  # Return original if optimization fails

def strip_all_html(html_content: str) -> str:
    """
    Strip all HTML tags and return only the text content.

    Args:
        html_content: HTML content to strip

    Returns:
        Plain text content
    """
    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for element in soup(["script", "style"]):
            element.decompose()

        # Extract text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        # Calculate reduction
        original_tokens = len(html_content) / 4
        text_tokens = len(text) / 4
        reduction = (1 - (text_tokens / original_tokens)) * 100

        logger.info(f"HTML stripping: {reduction:.1f}% token reduction")

        return text

    except Exception as e:
        logger.error(f"Error stripping HTML: {e}")
        return html_content

def optimize_prd_for_llm(html_content: str, strategy: str = "optimize") -> str:
    """
    Main function to optimize PRD content based on the selected strategy.

    Args:
        html_content: Original HTML content
        strategy: Optimization strategy:
                  - "optimize": Clean and optimize HTML
                  - "strip_html": Strip all HTML tags and return text only

    Returns:
        Optimized content
    """
    try:
        if strategy == "optimize":
            return optimize_prd_content(html_content, "medium")
        elif strategy == "strip_html":
            return strip_all_html(html_content)
        else:
            return html_content
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        return html_content

def display_optimization_options(html_content: str) -> Tuple[str, bool]:
    """
    Display optimization options in Streamlit UI and return the optimized content.

    Args:
        html_content: Original HTML content

    Returns:
        Tuple of (optimized_content, was_optimized)
    """
    with st.expander("🚀 PRD Optimization Options", expanded=False):
        st.info("Optimize the PRD to reduce token usage with the LLM")

        strategy = st.radio(
            "Optimization Strategy",
            options=["No optimization", "Basic optimization", "Strip all HTML"],
            index=1
        )

        # Preview mode to see the effect of optimization
        preview = st.checkbox("Preview optimized content", value=False)

        if strategy == "No optimization":
            if preview:
                st.text_area("Original Content Preview", html_content[:1000] + "...", height=200)
            return html_content, False

        # Map strategy selections to internal strategy names
        strategy_map = {
            "Basic optimization": "optimize",
            "Strip all HTML": "strip_html"
        }

        # Perform optimization
        optimized = optimize_prd_for_llm(html_content, strategy_map.get(strategy, "optimize"))

        # Calculate size reduction
        original_size = len(html_content)
        optimized_size = len(optimized)
        reduction = (1 - (optimized_size / original_size)) * 100

        st.success(f"Reduced by approximately {reduction:.1f}% ({original_size:,} → {optimized_size:,} characters)")

        if preview:
            col1, col2 = st.columns(2)
            with col1:
                st.text_area("Original Content Preview", html_content[:1000] + "...", height=200)
            with col2:
                st.text_area("Optimized Content Preview", optimized[:1000] + "...", height=200)

        return optimized, True