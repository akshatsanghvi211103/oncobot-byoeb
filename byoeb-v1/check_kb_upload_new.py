"""
Updated script to check KB2 and KB3 upload status with new source identifiers
"""
import asyncio
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient

# Configuration
INDEX_NAME = "oncobot_index"
SEARCH_SERVICE = "byoeb-search"

search_endpoint = f"https://{SEARCH_SERVICE}.search.windows.net"
credential = AzureCliCredential()
search_client = SearchClient(endpoint=search_endpoint, index_name=INDEX_NAME, credential=credential)

print("=== CHECKING KB2 CONTENT (kb2_content source) ===")

# KB2-specific terms that should only be found in knowledge_base_2.md
kb2_specific_terms = [
    "Multidisciplinary Tumour Board on Wednesday", 
    "Mould room visit- mask made",
    "soda bicarbonate mouth washes",
    "linear accelerator",
    "brachytherapy",
    "radiotherapy process follows these sequential steps"
]

for term in kb2_specific_terms:
    print(f'\n--- Searching for: "{term}" in KB2 ---')
    results = search_client.search(
        search_text=term,
        filter="source eq 'kb2_content'",
        top=3,
        select=['question', 'answer'],
        include_total_count=True
    )
    
    count = results.get_count()
    print(f'Found {count} results in KB2:')
    
    for i, result in enumerate(results, 1):
        headers = result.get('question', '')[:80]
        content = result.get('answer', '')[:150]
        print(f'  {i}. Headers: {headers}...')
        print(f'     Content: {content}...')

print('\n=== ALL KB2 CONTENT HEADERS ===')
kb2_results = search_client.search(
    search_text="*",
    filter="source eq 'kb2_content'",
    select=['question'],
    include_total_count=True,
    top=50
)

kb2_count = kb2_results.get_count()
print(f'Total KB2 sections found: {kb2_count}')

print('\nKB2 headers:')
for i, result in enumerate(kb2_results, 1):
    headers = result.get('question', '')
    print(f'  {i}. {headers}')

print('\n=== ALL KB3 CONTENT HEADERS ===')
kb3_results = search_client.search(
    search_text="*",
    filter="source eq 'kb3_content'",
    select=['question'],
    include_total_count=True,
    top=50
)

kb3_count = kb3_results.get_count()
print(f'Total KB3 sections found: {kb3_count}')

print('\nKB3 headers (first 10):')
for i, result in enumerate(kb3_results, 1):
    if i <= 10:  # Show first 10 only
        headers = result.get('question', '')
        print(f'  {i}. {headers}')
    else:
        break

print(f'\n=== SUMMARY ===')
print(f'KB2 (kb2_content): {kb2_count} sections')
print(f'KB3 (kb3_content): {kb3_count} sections')
print(f'Total markdown content: {kb2_count + kb3_count} sections')
