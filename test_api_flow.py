import requests, json, time, sys

BASE = 'http://127.0.0.1:8000/api/v1'
log_file = open('test_api_flow.log', 'w', encoding='utf-8')

def log(msg):
    print(msg)
    log_file.write(str(msg) + '\n')
    log_file.flush()

log('=== 经验萃取AI系统 - 全流程API测试 ===')

# Step 1: 创建访谈
print('\n[1/8] 创建访谈...')
resp = requests.post(f'{BASE}/interviews', json={
    'theme': '如何在大客户销售中建立信任关系',
    'background': '拥有15年大客户销售经验，年均签约额过亿',
    'expert_role': '资深销售总监',
    'expected_duration': 45,
    'target_output_format': 'script_card'
})
print(f'状态: {resp.status_code}')
if resp.status_code != 200:
    print(f'错误: {resp.text}')
    sys.exit(1)
interview = resp.json()
id = interview['id']
print(f'访谈ID: {id}')
print(f'状态: {interview["status"]}')

# Step 2: 生成蓝图
print('\n[2/8] 生成访谈蓝图...')
resp = requests.post(f'{BASE}/interviews/{id}/blueprint/generate')
print(f'状态: {resp.status_code}')
if resp.status_code == 200:
    bp = resp.json()
    print(f'蓝图状态: {bp["status"]}')
    print(f'章节数: {len(bp.get("sections", []))}')
else:
    print(f'响应: {resp.text}')

# Step 3: 确认蓝图
print('\n[3/8] 确认蓝图...')
resp = requests.post(f'{BASE}/interviews/{id}/blueprint/confirm', json={'confirmed': True})
print(f'状态: {resp.status_code}')
print(f'响应: {resp.json()}')

# Step 4: 发送专家回答（多轮对话）
messages = [
    '我曾在一次与某大型制造集团的合作中，通过三次深度拜访建立了初步信任。',
    '第一次拜访我花了2小时了解他们的产线痛点，第二次带了针对性的解决方案，第三次邀请了技术专家一起参与。',
    '最大的障碍是客户内部决策链很长，我通过找到关键影响者——生产部副总来突破。',
    '我使用的核心工具是"客户决策地图"和"价值量化表"。'
]
for i, msg in enumerate(messages, 1):
    print(f'\n[4.{i}/8] 发送消息 #{i}...')
    resp = requests.post(f'{BASE}/interviews/{id}/messages', json={'content': msg, 'role': 'user'})
    print(f'状态: {resp.status_code}')
    if resp.status_code == 200:
        data = resp.json()
        ai = data.get('ai_response', '')
        print(f'AI回复: {ai[:100]}...' if len(ai) > 100 else f'AI回复: {ai}')
    else:
        print(f'错误: {resp.text}')
    time.sleep(0.5)

# Step 5: 获取消息历史
print('\n[5/8] 获取消息历史...')
resp = requests.get(f'{BASE}/interviews/{id}/messages')
print(f'状态: {resp.status_code}')
if resp.status_code == 200:
    msgs = resp.json()
    print(f'总消息数: {len(msgs)}')

# Step 6: 获取结构化内容
print('\n[6/8] 获取结构化内容...')
resp = requests.get(f'{BASE}/interviews/{id}/structured-content')
print(f'状态: {resp.status_code}')
if resp.status_code == 200:
    sc = resp.json()
    print(f'当前阶段: {sc.get("current_stage")}')
    print(f'核心经验点: {len(sc.get("key_experiences", []))}')
    print(f'方法论: {len(sc.get("methodologies", []))}')

# Step 7: 完成访谈
print('\n[7/8] 完成访谈...')
resp = requests.post(f'{BASE}/interviews/{id}/complete')
print(f'状态: {resp.status_code}')
print(f'响应: {resp.json()}')

# Step 8: 获取输出
print('\n[8/8] 获取最终输出...')
resp = requests.get(f'{BASE}/interviews/{id}/output')
print(f'状态: {resp.status_code}')
if resp.status_code == 200:
    out = resp.json()
    print(f'输出类型: {out.get("output_type")}')
    print(f'内容长度: {len(out.get("content", ""))} 字符')

print('\n=== 测试完成 ===')
