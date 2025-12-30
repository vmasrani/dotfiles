"""Rendering functions for URL summary data"""

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.columns import Columns


def render_overview(data: dict, console: Console):
    """Compact overview - essential information only"""
    console.print(f"\n[bold cyan]═══ {data.get('title', 'Unknown')} ═══[/bold cyan]\n")
    console.print(f"[dim]{data.get('url')}[/dim]")
    if data.get('author'):
        console.print(f"[dim]By {data.get('author')}[/dim]", end="")
        if data.get('publish_date'):
            console.print(f" [dim]• {data.get('publish_date')}[/dim]")
        else:
            console.print()
    console.print()

    console.print("[bold]📝 Summary:[/bold]")
    console.print(f"  {data.get('two_sentence_summary', 'N/A')}\n")

    console.print("[bold]📋 Key Takeaways:[/bold]")
    for point in data.get("key_takeaways", [])[:5]:
        console.print(f"  • {point}")
    console.print()

    console.print("[bold]🏷️  Topics:[/bold]")
    console.print(f"  {', '.join(data.get('main_topics', [])[:8])}\n")

    people = data.get("people", [])
    if people:
        console.print("[bold]👤 People:[/bold]")
        console.print(f"  {', '.join(people[:5])}\n")

    facts = data.get("key_facts", [])
    if facts:
        console.print("[bold]📌 Key Facts:[/bold]")
        for f in facts[:5]:
            console.print(f"  • {f}")
        console.print()


def render_one_pager(data: dict, console: Console):
    """One-page comprehensive summary"""
    # Header
    console.print(f"\n[bold cyan]{'═' * 80}[/bold cyan]")
    console.print(f"[bold cyan]{data.get('title', 'Unknown').center(80)}[/bold cyan]")
    console.print(f"[bold cyan]{'═' * 80}[/bold cyan]\n")

    # Metadata
    meta_parts = []
    meta_parts.append(f"[dim]🔗 {data.get('url')}[/dim]")
    if data.get('author'):
        meta_parts.append(f"[dim]✍️  {data.get('author')}[/dim]")
    if data.get('publish_date'):
        meta_parts.append(f"[dim]📅 {data.get('publish_date')}[/dim]")
    meta_parts.append(f"[dim]📄 {data.get('content_type', 'unknown')}[/dim]")
    if data.get('word_count'):
        meta_parts.append(f"[dim]📊 ~{data.get('word_count')} words[/dim]")

    console.print(" | ".join(meta_parts))
    console.print()

    # Comprehensive Summary
    console.print("[bold white on blue] COMPREHENSIVE SUMMARY [/bold white on blue]\n")
    summary = data.get('comprehensive_summary', data.get('two_sentence_summary', 'N/A'))
    console.print(Panel(summary, border_style="blue", padding=(1, 2)))
    console.print()

    # Key Takeaways
    console.print("[bold white on green] KEY TAKEAWAYS [/bold white on green]\n")
    for i, point in enumerate(data.get("key_takeaways", []), 1):
        console.print(f"  [bold green]{i}.[/bold green] {point}")
    console.print()

    # Topics & Keywords
    console.print("[bold white on magenta] MAIN TOPICS [/bold white on magenta]")
    topics = data.get('main_topics', [])
    if topics:
        console.print(f"  {' • '.join(topics)}\n")

    keywords = data.get('keywords', [])
    if keywords:
        console.print("[bold]🔖 Keywords:[/bold]")
        console.print(f"  {', '.join(keywords[:15])}\n")

    # People, Organizations, Locations
    people = data.get("people", [])
    orgs = data.get("organizations", [])
    locations = data.get("locations", [])

    if people or orgs or locations:
        console.print("[bold white on yellow] ENTITIES MENTIONED [/bold white on yellow]\n")

        if people:
            console.print("[bold]👤 People:[/bold]")
            for p in people[:8]:
                console.print(f"  • {p}")
            console.print()

        if orgs:
            console.print("[bold]🏢 Organizations:[/bold]")
            for o in orgs[:8]:
                console.print(f"  • {o}")
            console.print()

        if locations:
            console.print("[bold]📍 Locations:[/bold]")
            console.print(f"  {', '.join(locations[:10])}\n")

    # Key Facts & Statistics
    facts = data.get("key_facts", [])
    stats = data.get("statistics", [])

    if facts or stats:
        console.print("[bold white on red] KEY FACTS & DATA [/bold white on red]\n")

        if facts:
            console.print("[bold]📌 Facts:[/bold]")
            for f in facts[:8]:
                console.print(f"  • {f}")
            console.print()

        if stats:
            console.print("[bold]📊 Statistics:[/bold]")
            for s in stats[:8]:
                console.print(f"  • {s}")
            console.print()

    # Sentiment & Tone
    console.print(f"[bold]🎭 Tone & Sentiment:[/bold] {data.get('tone', 'N/A')} • {data.get('sentiment', 'N/A')}\n")


def render_report(data: dict, console: Console):
    """Complete comprehensive report with all fields"""
    # Header
    console.print(f"\n[bold cyan]{'═' * 100}[/bold cyan]")
    console.print(f"[bold cyan]{data.get('title', 'Unknown').center(100)}[/bold cyan]")
    console.print(f"[bold cyan]{'═' * 100}[/bold cyan]\n")

    # Metadata Section
    console.print("[bold white on blue] DOCUMENT METADATA [/bold white on blue]\n")
    console.print(f"[bold]URL:[/bold] {data.get('url')}")
    console.print(f"[bold]Domain:[/bold] {data.get('domain', 'N/A')}")
    console.print(f"[bold]Title:[/bold] {data.get('title', 'N/A')}")
    console.print(f"[bold]Author:[/bold] {data.get('author', 'Not specified')}")
    console.print(f"[bold]Published:[/bold] {data.get('publish_date', 'Not specified')}")
    console.print(f"[bold]Content Type:[/bold] {data.get('content_type', 'unknown')}")
    console.print(f"[bold]Language:[/bold] {data.get('language', 'N/A')}")
    console.print(f"[bold]Word Count:[/bold] ~{data.get('word_count', 0)} words")
    console.print()

    # Quick Summary
    console.print("[bold white on green] EXECUTIVE SUMMARY [/bold white on green]\n")
    console.print(Panel(data.get('two_sentence_summary', 'N/A'), border_style="green", padding=(1, 2)))
    console.print()

    # Comprehensive Summary
    console.print("[bold white on blue] DETAILED SUMMARY [/bold white on blue]\n")
    comprehensive = data.get('comprehensive_summary', 'N/A')
    console.print(Panel(comprehensive, border_style="blue", padding=(1, 2)))
    console.print()

    # Key Takeaways
    console.print("[bold white on magenta] KEY TAKEAWAYS [/bold white on magenta]\n")
    for i, point in enumerate(data.get("key_takeaways", []), 1):
        console.print(f"  [bold]{i}.[/bold] {point}")
    console.print()

    # Document Structure
    console.print("[bold white on yellow] DOCUMENT STRUCTURE [/bold white on yellow]\n")

    console.print("[bold]🏷️  Main Topics:[/bold]")
    for topic in data.get('main_topics', []):
        console.print(f"  • {topic}")
    console.print()

    keywords = data.get('keywords', [])
    if keywords:
        console.print("[bold]🔖 Keywords:[/bold]")
        console.print(f"  {', '.join(keywords)}\n")

    headings = data.get('headings', [])
    if headings:
        console.print("[bold]📑 Document Headings:[/bold]")
        for h in headings[:20]:
            console.print(f"  {h}")
        if len(headings) > 20:
            console.print(f"  [dim]... and {len(headings) - 20} more[/dim]")
        console.print()

    # Entities
    console.print("[bold white on cyan] ENTITIES & REFERENCES [/bold white on cyan]\n")

    people = data.get("people", [])
    if people:
        console.print("[bold]👤 People:[/bold]")
        for p in people:
            console.print(f"  • {p}")
        console.print()

    orgs = data.get("organizations", [])
    if orgs:
        console.print("[bold]🏢 Organizations:[/bold]")
        for o in orgs:
            console.print(f"  • {o}")
        console.print()

    locations = data.get("locations", [])
    if locations:
        console.print("[bold]📍 Locations:[/bold]")
        console.print(f"  {', '.join(locations)}\n")

    dates = data.get("dates", [])
    if dates:
        console.print("[bold]📅 Important Dates:[/bold]")
        for d in dates[:10]:
            console.print(f"  • {d}")
        console.print()

    products = data.get("products_or_services", [])
    if products:
        console.print("[bold]🛠️  Products/Services:[/bold]")
        for p in products[:15]:
            console.print(f"  • {p}")
        console.print()

    # Facts & Data
    console.print("[bold white on red] FACTS, DATA & CLAIMS [/bold white on red]\n")

    facts = data.get("key_facts", [])
    if facts:
        console.print("[bold]📌 Key Facts:[/bold]")
        for f in facts:
            console.print(f"  • {f}")
        console.print()

    stats = data.get("statistics", [])
    if stats:
        console.print("[bold]📊 Statistics:[/bold]")
        for s in stats:
            console.print(f"  • {s}")
        console.print()

    quotes = data.get("quotes", [])
    if quotes:
        console.print("[bold]💬 Quotes:[/bold]")
        for q in quotes[:10]:
            console.print(f"  {q}")
        console.print()

    claims = data.get("claims", [])
    if claims:
        console.print("[bold]⚡ Notable Claims:[/bold]")
        for c in claims[:10]:
            console.print(f"  • {c}")
        console.print()

    # Links
    links = data.get("links", [])
    link_texts = data.get("link_texts", [])
    link_contexts = data.get("link_contexts", [])
    if links:
        console.print("[bold white on blue] LINKS FOUND [/bold white on blue]\n")
        console.print(f"[bold]🔗 Total Links:[/bold] {len(links)}\n")
        for i, link in enumerate(links[:15]):
            text = link_texts[i] if i < len(link_texts) else "Link"
            context = link_contexts[i] if i < len(link_contexts) else ""
            console.print(f"  [bold]{text}[/bold]")
            console.print(f"    → {link}")
            if context:
                console.print(f"    [dim]{context}[/dim]")
            console.print()
        if len(links) > 15:
            console.print(f"  [dim]... and {len(links) - 15} more links[/dim]\n")

    # Media & Format
    console.print("[bold white on magenta] CONTENT FEATURES [/bold white on magenta]\n")
    features = []
    if data.get("has_videos"):
        features.append("📹 Contains videos")
    if data.get("has_code_blocks"):
        features.append("💻 Contains code blocks")
    if data.get("has_tables"):
        features.append("📊 Contains tables")

    if features:
        for f in features:
            console.print(f"  • {f}")
        console.print()

    # CTAs and References
    ctas = data.get("calls_to_action", [])
    if ctas:
        console.print("[bold]📣 Calls to Action:[/bold]")
        for cta in ctas:
            console.print(f"  • {cta}")
        console.print()

    refs = data.get("references", [])
    if refs:
        console.print("[bold]📚 References/Citations:[/bold]")
        for ref in refs[:10]:
            console.print(f"  • {ref}")
        console.print()

    # Analysis
    console.print("[bold white on yellow] CONTENT ANALYSIS [/bold white on yellow]\n")
    console.print(f"[bold]🎭 Sentiment:[/bold] {data.get('sentiment', 'N/A')}")
    console.print(f"[bold]✍️  Tone:[/bold] {data.get('tone', 'N/A')}\n")

    cred = data.get("credibility_signals", [])
    if cred:
        console.print("[bold]✅ Credibility Signals:[/bold]")
        for c in cred:
            console.print(f"  • {c}")
        console.print()

    biases = data.get("potential_biases", [])
    if biases:
        console.print("[bold]⚠️  Potential Biases:[/bold]")
        for b in biases:
            console.print(f"  • {b}")
        console.print()

    # Full Markdown Content
    markdown_text = data.get("markdown_text", "")
    if markdown_text:
        console.print("\n[bold white on blue] FULL PAGE CONTENT [/bold white on blue]\n")
        console.print("[dim]Note: Full markdown content follows below[/dim]\n")
        console.print("─" * 100 + "\n")

        # Render as markdown for better readability
        md = Markdown(markdown_text)
        console.print(md)

        console.print("\n" + "─" * 100)
        console.print("[dim]End of full content[/dim]\n")
