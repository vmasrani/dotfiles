import dspy
import ipdb
import os
from rich import print

# from dotenv import load_dotenv

# load_dotenv()

lm = dspy.LM("openai/gpt-4.1-nano", api_key=os.getenv("OPENAI_API_KEY"))
dspy.configure(lm=lm)

class Outline(dspy.Signature):
    """Outline a thorough overview of a topic."""

    topic: str = dspy.InputField()
    title: str = dspy.OutputField()
    sections: list[str] = dspy.OutputField()
    section_subheadings: dict[str, list[str]] = dspy.OutputField(desc="mapping from section headings to subheadings")

class DraftSection(dspy.Signature):
    """Draft a top-level section of an article."""

    topic: str = dspy.InputField()
    section_heading: str = dspy.InputField()
    section_subheadings: list[str] = dspy.InputField()
    content: str = dspy.OutputField(desc="markdown-formatted section")

class DraftArticle(dspy.Module):
    def __init__(self):
        self.build_outline = dspy.ChainOfThought(Outline)
        self.draft_section = dspy.ChainOfThought(DraftSection)

    def forward(self, topic):

        outline = self.build_outline(topic=topic)

        sections = []
        for i, (heading, subheadings) in enumerate(outline.section_subheadings.items()):
            print(f"Drafting section {i+1} of {len(outline.section_subheadings)}")
            print(f"Heading: {heading}")
            print(f"Subheadings: {subheadings}")
            section, subheadings = f"## {heading}", [f"### {subheading}" for subheading in subheadings]
            section = self.draft_section(topic=outline.title, section_heading=section, section_subheadings=subheadings)
            sections.append(section.content)

        return dspy.Prediction(title=outline.title, sections=sections)

draft_article = DraftArticle()
article = draft_article(topic="The history of the world")
print(article)
