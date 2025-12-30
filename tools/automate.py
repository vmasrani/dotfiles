import asyncio
import os
from tabstack import Tabstack
from pydantic import BaseModel, Field
from typing import List
import json
from dotenv import load_dotenv
from rich import print_json, print
import requests
load_dotenv()

class Article(BaseModel):
    headline: str
    author: str
    date: str

class ArticlesResponse(BaseModel):
    title: str = Field(description="The main title of the blog post")
    articles: List[Article]

def get_schema_from_pydantic(model: type[BaseModel]) -> dict:
    return model.model_json_schema()


async def main():
    result = None
    async with Tabstack(api_key=os.getenv('TABSTACK_API_KEY')) as tabs:
        async for event in tabs.agent.automate(
            task='Find all articles mentioning "increments podcast" or "vaden masrani" or "ben chugg" on substack. Produce an exhaustive bulleted list of all keyword mentions and their links. Make follow all the google links, not just the ones on the first page. Ensure to only extract articles that mention the full keyword phrase, and not just individual words like "increments" or "podcast". Search substack using the google query ie \' "vaden masrani" site:substack.com \'.',
            url='https://www.google.com/',
            schema=get_schema_from_pydantic(ArticlesResponse),
            # guardrails='browse and extract only the articles that mention the keywords'
        ):
            print(f"Event: {event.type}, {event.data}")
            if event.type == 'task:completed':
                print('Automation completed')
                result = event.data.get('finalAnswer')
                break
    return result

result = asyncio.run(main())
print(result)

# Save results to markdown file
if result:
    with open('automation_results.md', 'w') as f:
        f.write('# Automation Results\n\n')
        if isinstance(result, dict):
            f.write(json.dumps(result, indent=2))
        else:
            f.write(str(result))
    print("\n✅ Results saved to automation_results.md")
