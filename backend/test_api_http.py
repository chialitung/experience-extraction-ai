import requests
import time

interview_id = '38583646-ea87-4d39-9afb-be6c2a0c1af0'
url = f'http://localhost:8000/api/v1/interviews/{interview_id}/messages'

print('Testing POST /messages...')
start = time.time()
try:
    resp = requests.post(
        url,
        json={'content': '我曾经遇到一个客户，对我们产品很感兴趣但一直不下单。后来我通过了解他的真实需求，成功促成了合作。'},
        timeout=60
    )
    elapsed = time.time() - start
    print(f'Status: {resp.status_code}')
    print(f'Elapsed: {elapsed:.1f}s')
    if resp.status_code == 200:
        data = resp.json()
        content = data.get('content', '')
        print(f'AI Reply: {content[:200]}')
    else:
        print(f'Error: {resp.text[:500]}')
except Exception as e:
    print(f'Exception: {type(e).__name__}: {e}')
