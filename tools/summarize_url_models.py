"""Shared Pydantic models and utilities for URL summarization tools"""

from pydantic import BaseModel, Field


SYS_PROMPT = """Extract comprehensive structured information from this webpage.

Be thorough in identifying:
- All people, organizations, and entities mentioned
- All links with their context and whether they're internal/external
- Key facts, statistics, and quotes with proper attribution
- The full content as clean markdown
- Document structure and topics

Return the data according to the provided schema."""


class URLSummaryCompact(BaseModel):
    """Compact structured extraction - essential fields only"""
    title: str = Field(description="Page title")
    url: str = Field(description="The original URL")
    author: str = Field(description="Author if identifiable, empty string if not")
    publish_date: str = Field(description="Publication date if available, empty string if not")
    content_type: str = Field(description="Type: article, product, documentation, blog, news, academic, social, landing_page, forum, video, other")
    two_sentence_summary: str = Field(description="A concise 2-sentence summary capturing the essence")
    key_takeaways: list[str] = Field(description="5-10 bullet points of the most important information")
    main_topics: list[str] = Field(description="Primary topics/themes covered")
    links: list[str] = Field(description="All URLs found on the page (just the hrefs)")
    link_texts: list[str] = Field(description="Anchor text for each link (parallel array to links)")
    people: list[str] = Field(description="Names of people mentioned")
    key_facts: list[str] = Field(description="Important factual statements")


class URLSummaryFull(BaseModel):
    """Comprehensive structured extraction from any URL"""
    # Core
    url: str = Field(description="The original URL")
    domain: str = Field(description="The domain name")
    title: str = Field(description="Page title")
    author: str = Field(description="Author name, empty if not found")
    publish_date: str = Field(description="Publication date, empty if not found")
    content_type: str = Field(description="Type: article, product, documentation, blog, news, academic, social, landing_page, forum, video, other")
    language: str = Field(description="Content language ISO code")
    word_count: int = Field(description="Approximate word count")

    # Summaries
    two_sentence_summary: str = Field(description="A concise 2-sentence summary capturing the essence")
    comprehensive_summary: str = Field(description="A detailed 3-5 paragraph summary covering all main points")
    key_takeaways: list[str] = Field(description="5-10 bullet points of the most important information")

    # Full content
    markdown_text: str = Field(description="The full page content converted to clean markdown")

    # Structure
    main_topics: list[str] = Field(description="Primary topics/themes covered")
    keywords: list[str] = Field(description="Important keywords and phrases for indexing")
    headings: list[str] = Field(description="Document headings in order (e.g. '## Introduction', '### Methods')")

    # Links (parallel arrays)
    links: list[str] = Field(description="All href URLs found on the page")
    link_texts: list[str] = Field(description="Anchor text for each link")
    link_contexts: list[str] = Field(description="Brief context for each link")

    # Entities
    people: list[str] = Field(description="People mentioned (format: 'Name - Role/Context')")
    organizations: list[str] = Field(description="Organizations mentioned (format: 'Name - Type/Context')")
    locations: list[str] = Field(description="Geographic locations mentioned")
    dates: list[str] = Field(description="Dates mentioned (format: 'YYYY-MM-DD: context' or 'date_string: context')")
    products_or_services: list[str] = Field(description="Products, services, or tools mentioned")

    # Facts and data
    key_facts: list[str] = Field(description="Important factual statements that can be verified")
    statistics: list[str] = Field(description="Statistics (format: 'value: context')")
    quotes: list[str] = Field(description="Direct quotes (format: 'quote text' - attribution)")
    claims: list[str] = Field(description="Notable claims or assertions made")

    # Media flags
    has_videos: bool = Field(description="Whether page contains videos")
    has_code_blocks: bool = Field(description="Whether page contains code snippets")
    has_tables: bool = Field(description="Whether page contains data tables")

    # Actions and references
    calls_to_action: list[str] = Field(description="CTAs, signup prompts, purchase links")
    references: list[str] = Field(description="Citations, sources, or bibliography items")

    # Sentiment and tone
    sentiment: str = Field(description="Overall sentiment: positive, negative, neutral, mixed")
    tone: str = Field(description="Writing tone: formal, casual, technical, persuasive, informative, etc.")

    # Quality
    credibility_signals: list[str] = Field(description="Indicators of credibility")
    potential_biases: list[str] = Field(description="Any apparent biases or one-sided perspectives")


def get_schema_from_pydantic(model: type[BaseModel]) -> dict:
    return model.model_json_schema()
