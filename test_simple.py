import requests, json, sys, time

BASE = 'http://127.0.0.1:8000/api/v1'
results = []

def check(label, resp, expect=200):
    ok = resp.status_code == expect
    results.append((label, ok, resp.status_code))
    print(f"{'[OK]' if ok else '[FAIL]'} {label}: {resp.status_code}")
    if not ok:
        print(f"  → {resp.text[:200]}")
    return ok

# 1. Create interview
print("\n=== 1. 创建访谈 ===")
r = requests.post(f'{BASE}/interviews', json={
    'theme': '如何在大客户销售中建立信任关系',
    'background': '拥有15年大客户销售经验，年均签约额过亿',
    'expert_role': '资深销售总监',
    'expected_duration': 45,
    'target_output_format': 'script_card'
})
if not check('创建访谈', r, 201):
    sys.exit(1)
interview = r.json()
id = interview['id']
print(f"  ID: {id}")
print(f"  状态: {interview['status']}")
print(f"  当前阶段: {interview['current_state']}")

# 2. Generate blueprint
print("\n=== 2. 生成蓝图 ===")
r = requests.post(f'{BASE}/interviews/{id}/blueprint/generate')
check('生成蓝图', r)
if r.status_code == 200:
    bp = r.json()
    print(f"  状态: {bp.get('status')}")

# 3. Confirm blueprint
print("\n=== 3. 确认蓝图 ===")
r = requests.post(f'{BASE}/interviews/{id}/blueprint/confirm', json={'confirmed': True})
check('确认蓝图', r)

# 4. Send messages
print("\n=== 4. 发送消息（多轮对话） ===")
msgs = [
    '我曾在一次与某大型制造集团的合作中，通过三次深度拜访建立了初步信任。',
    '第一次拜访我花了2小时了解他们的产线痛点，第二次带了针对性的解决方案，第三次邀请了技术专家一起参与。',
    '最大的障碍是客户内部决策链很长，我通过找到关键影响者来突破。',
    '我使用的核心工具是客户决策地图和价值量化表。'
]
for i, msg in enumerate(msgs, 1):
    r = requests.post(f'{BASE}/interviews/{id}/messages', json={'content': msg})
    check(f'发送消息 #{i}', r)
    if r.status_code == 200:
        ai = r.json().get('ai_response', '')
        print(f"    AI回复: {ai[:60]}...")
    time.sleep(0.3)

# 5. Get messages
print("\n=== 5. 获取消息历史 ===")
r = requests.get(f'{BASE}/interviews/{id}/messages')
check('获取消息', r)
if r.status_code == 200:
    print(f"  总消息数: {len(r.json())}")

# 6. Get structured content
print("\n=== 6. 获取结构化内容 ===")
r = requests.get(f'{BASE}/interviews/{id}/structured-content')
check('结构化内容', r)
if r.status_code == 200:
    sc = r.json()
    print(f"  阶段: {sc.get('current_stage')}")
    print(f"  经验点: {len(sc.get('key_experiences', []))}")
    print(f"  方法论: {len(sc.get('methodologies', []))}")

# 7. Complete interview
print("\n=== 7. 完成访谈 ===")
r = requests.post(f'{BASE}/interviews/{id}/complete')
check('完成访谈', r)

# 8. Get output
print("\n=== 8. 获取最终输出 ===")
r = requests.get(f'{BASE}/interviews/{id}/output')
check('最终输出', r)
if r.status_code == 200:
    out = r.json()
    print(f"  类型: {out.get('output_type')}")
    print(f"  长度: {len(out.get('content', ''))} 字符")

# Summary
print("\n=== 测试总结 ===")
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"通过: {passed}/{total}")
for label, ok, code in results:
    status = '通过' if ok else '失败'
    print(f"  [{status}] {label} (HTTP {code})")
