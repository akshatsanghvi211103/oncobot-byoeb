"""
Check if KB2 content has been uploaded to the search index
"""
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient

# Setup search client
search_endpoint = 'https://byoeb-search.search.windows.net'
credential = AzureCliCredential()
search_client = SearchClient(endpoint=search_endpoint, index_name='oncobot_index', credential=credential)

print('=== SEARCHING FOR KB2-SPECIFIC CONTENT ===')

# Search for content that should only be in KB2 (knowledge_base_2.md)
kb2_specific_terms = [
    "Multidisciplinary Tumour Board on Wednesday",
    "Mould room visit- mask made",
    "soda bicarbonate mouth washes", 
    "linear accelerator",
    "brachytherapy",
    "Radiation Therapy Guide",
    "radiotherapy process follows these sequential steps"
]

for term in kb2_specific_terms:
    print(f'\n--- Searching for: "{term}" ---')
    results = search_client.search(
        search_text=term,
        filter="source eq 'markdown_knowledge_base'",
        top=3,
        select=['question', 'answer'],
        include_total_count=True
    )
    
    count = results.get_count()
    print(f'Found {count} results:')
    
    for i, result in enumerate(results, 1):
        headers = result.get('question', '')[:80]
        content = result.get('answer', '')[:150]
        print(f'  {i}. Headers: {headers}...')
        print(f'     Content: {content}...')

print('\n=== CHECKING ALL MARKDOWN CONTENT HEADERS ===')
all_md = search_client.search(
    search_text='*',
    filter="source eq 'markdown_knowledge_base'",
    top=50,
    select=['question', 'answer']
)

headers_found = []
for result in all_md:
    header = result.get('question', '')
    if header:
        headers_found.append(header)

print(f'Total markdown sections found: {len(headers_found)}')
print('\nAll headers found:')
for i, header in enumerate(sorted(set(headers_found)), 1):
    print(f'  {i}. {header}')

# Check if any contain KB2-specific keywords
print('\n=== ANALYZING HEADERS FOR KB2 CONTENT ===')
kb2_indicators = ['radiation therapy guide', 'radiotherapy', 'multidisciplinary', 'mould room', 'brachytherapy']
kb2_headers = []

for header in headers_found:
    if any(indicator in header.lower() for indicator in kb2_indicators):
        kb2_headers.append(header)

print(f'Headers that might be from KB2: {len(kb2_headers)}')
for header in kb2_headers:
    print(f'  - {header}')
