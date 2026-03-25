#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练机器人 - DA优化版
融入完整DA资料，提升对话专业性和临床深度
"""
import json, os, threading, requests, random
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
app = Flask(__name__)
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a938ac2a24391bcb')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')
# 内存存储 + 文件持久化
users = {}
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)
# 医生角色 - 增加角色特点描述
ROLES = {
    '1': ('主任级专家', '⭐⭐⭐⭐⭐', '对临床数据要求高，关注长期疗效和安全性证据'),
    '2': ('科室主任', '⭐⭐⭐⭐', '关注科室用药规范、患者管理流程和医保政策'),
    '3': ('主治医师', '⭐⭐⭐', '关注临床操作便利性、患者反馈和不良反应处理'),
    '4': ('住院医师', '⭐⭐', '正在学习内异症诊疗规范，需要基础产品知识'),
    '5': ('带组专家', '⭐⭐⭐⭐⭐', '关注手术联合药物治疗方案，重视生育力保护')
}
# 8个销售阶段 - 对应DA逻辑
STAGES = ['开场白', '探询需求', '产品介绍', '临床数据', '竞品对比', '处理异议', '促成成交', '结束']
# 医生对话库 - 基于DA内容设计，每个阶段多组备选
DIALOGUE = {
    1: [  # 开场白
        "你好，有什么事吗？我一会儿还有台手术。",
        "你是哪个公司的？找我有什么事？",
        "我现在有点忙，你长话短说。",
        "又是推销药的？你们这月来了好几拨了。"
    ],
    2: [  # 探询需求 - 对应"三大难题"
        "我们科室确实有不少内异症患者，现在主要用亮丙瑞林。你说的这个维宝宁有什么特别的？",
        "内异症患者确实多，疼痛、复发、不孕这三大难题你们有什么解决方案？",
        "我们科室每个月大概20-30个内异症手术，术后用药你们有什么方案？",
        "现在内异症患者术后复发率太高了，你们产品能解决这个问题吗？"
    ],
    3: [  # 产品介绍 - 对应"金标准"
        "维宝宁？没听说过，是国产的吗？成分是什么？",
        "醋酸曲普瑞林微球？和达菲林不是一样的成分吗？为什么要换？",
        "3.75mg，每4周一次，这和达菲林用法一样啊，有什么优势？",
        "GnRH-a是内异症的金标准我知道，但你们这个和进口的有啥区别？"
    ],
    4: [  # 临床数据 - 对应"III期临床数据"
        "E2去势率97%？这个数据不错，有III期临床数据支持吗？",
        "疼痛缓解数据怎么样？痛经和慢性盆腔痛能缓解多少？",
        "生育力保护方面有什么数据？很多患者关心停药后多久能备孕。",
        "囊肿缩小效果怎么样？对卵巢储备功能有影响吗？"
    ],
    5: [  # 竞品对比 - 对应"Meta分析"
        "达菲林用了这么多年了，我们为什么要换国产的？",
        "和亮丙瑞林比怎么样？我们有些患者用亮丙瑞林效果也不错。",
        "我看你们说是曲普瑞林，和戈舍瑞林比有什么优势？",
        "价格怎么样？达菲林现在集采后价格也不贵，你们有优势吗？"
    ],
    6: [  # 处理异议 - 对应"技术优势"
        "国产的微球制剂工艺能行吗？稳定性怎么样？",
        "注射部位反应怎么样？有些患者打完达菲林会痛，还有硬结。",
        "不良反应发生率具体多少？潮热、骨质疏松这些和达菲林比怎么样？",
        "突释效应控制怎么样？有些患者用药初期反应很大。"
    ],
    7: [  # 促成成交
        "听起来不错，要不你先放几份样品，我给几个患者试试。",
        "可以先申请进院吗？我们走个临采试试。",
        "你能给我一些临床文献吗？我想看看具体的III期数据。",
        "这个月的药事会已经过了，下个月我帮你提单试试。"
    ],
    8: [  # 结束
        "今天的交流很有收获，维宝宁的数据确实令人信服。",
        "好的，我会考虑的，有需要的患者我会试用。",
        "谢谢你的介绍，我们保持联系，有消息通知你。"
    ]
}
# 评分关键词 - 从DA完整提取，按重要性加权
SCORING_KEYWORDS = {
    # 产品基础（权重1）
    '醋酸曲普瑞林': 1, '微球': 1, '3.75mg': 1, '每4周': 1, '月经1-5天': 1,
    '注射用': 1, '微球制剂': 1, '臀部肌肉注射': 1,
    
    # 核心临床数据（权重2）
    'E2去势率': 2, '97%': 2, '97.45%': 2, '去势': 1, '低雌激素': 1,
    '痛经': 1, 'VAS': 2, '99%': 2, '疼痛缓解': 1, '慢性盆腔痛': 1,
    '盆腔痛': 1, '75%': 2, '非经期盆腔痛': 1,
    '异位囊肿': 1, '囊肿缩小': 2, '5mm': 1, '卵巢储备': 1,
    '月经恢复': 2, '缩短12天': 2, '生育力': 2, '备孕': 1, '黄金时间窗': 1,
    '69天': 1, '77天': 1, '89天': 1, '101天': 1,
    
    # 技术优势（权重2）
    '突释': 2, '1/5': 2, '稳定释放': 1, 'PLGA': 2, '1/6': 2,
    '微球专利': 1, '制备工艺': 1, '粒径均一': 1, '圆整致密': 1,
    'I期药代': 1, '血药浓度': 1, '匀速释放': 1,
    
    # 安全性数据（权重2）
    '注射部位痛': 2, '1.53%': 2, '硬结': 2, '0.51%': 2, '4.08%': 1, '3.06%': 1,
    '不良反应': 1, '更低': 1, '安全性': 1, '注射体验': 1,
    '炎症': 1, '蓄积': 1, '辅料少': 1,
    
    # 竞品对比（权重2）
    '达菲林': 1, '亮丙瑞林': 1, '戈舍瑞林': 1, '优于': 1, '进口': 1,
    '妊娠率': 2, '87.3%': 2, '复发率': 2, '28.5%': 1, '更低': 1,
    '有效率': 2, '77%': 1, 'Meta分析': 2, '94项RCT': 2, '9620例': 1,
    '网状Meta': 1, '疗效更佳': 1, '双重平衡': 1,
    
    # 指南推荐（权重2）
    '金标准': 2, 'GnRH-a': 1, '指南推荐': 1, '专家共识': 1,
    '2021诊治指南': 1, '2022生育力共识': 1, '2022深部浸润共识': 1,
    '2024疼痛管理': 1, '2025GnRH-a共识': 1,
    '复发防治': 1, '生育力保护': 1, '长期管理': 1, '序贯治疗': 1,
    
    # 三大难题（权重1）
    '疼痛': 1, '复发': 1, '不孕': 1, '不死的癌症': 1,
    '70-80%': 1, '20%': 1, '50%': 1, '2年复发': 1, '5年复发': 1,
    '20-50%': 1, '生活质量': 1, '焦虑': 1, '抑郁': 1,
    
    # 主题理念（权重1）
    '告别异痛': 1, '维守芳华': 1, '平稳强效': 1, '激素管控': 1,
    
    # 价格政策（权重1）
    '1000元': 1, '支付标准': 1, '医保': 1, '集采': 1, '进院': 1,
}
def get_token():
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
        return resp.json().get("tenant_access_token")
    except:
        return None
def send_msg(open_id, msg_id, text):
    def do():
        try:
            token = get_token()
            if not token: return
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if msg_id:
                url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
                data = {"msg_type": "text", "content": json.dumps({"text": text})}
            else:
                url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
                data = {"receive_id": open_id, "msg_type": "text", "content": json.dumps({"text": text})}
            requests.post(url, headers=headers, json=data, timeout=10)
        except: pass
    threading.Thread(target=do, daemon=True).start()

def save_user(user_id, data):
    try:
        filepath = os.path.join(DATA_DIR, f'{user_id}.json')
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except: pass

def load_user(user_id):
    try:
        filepath = os.path.join(DATA_DIR, f'{user_id}.json')
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                last_time = data.get('last_time', 0)
                if datetime.now().timestamp() - last_time < 1800:
                    return data
    except: pass
    return None

def get_feedback(score, stage_name, text):
    """根据得分、阶段和用户回答给出针对性反馈"""
    
    # 检查是否提到关键数据
    has_key_data = any(kw in text for kw in ['97%', '99%', '1/5', '1/6', '12天', '87.3%', '94项'])
    
    feedback_map = {
        '开场白': {
            'high': '🌟 开场白简洁有力，快速建立信任，为后续对话奠定基础。',
            'medium': '💡 开场白可以更简洁，建议先自报家门，说明来意，快速抓住医生注意力。',
            'low': '📝 建议：开场白避免过于冗长，控制在30秒内，重点突出维宝宁的差异化价值。'
        },
        '探询需求': {
            'high': '🌟 善于提问，准确把握科室用药现状和医生对"疼痛、复发、不孕"三大难题的关注。',
            'medium': '💡 探询需求时可以更深入，了解医生对现有GnRH-a药物的具体不满。',
            'low': '📝 建议：使用SPIN提问法，先了解现状，再探询痛点（疼痛/复发/不孕），最后确认需求。'
        },
        '产品介绍': {
            'high': '🌟 产品介绍清晰准确，突出维宝宁微球制剂的技术优势（突释低、PLGA少）。',
            'medium': '💡 产品介绍建议用FAB法则：特性(Feature)-优势(Advantage)-利益(Benefit)。',
            'low': '📝 建议：重点强调维宝宁的差异化：醋酸曲普瑞林微球、突释1/5、PLGA 1/6、注射体验佳。'
        },
        '临床数据': {
            'high': '🌟 数据引用准确！97.45%去势率、99%痛经缓解、缩短12天等核心数据突出。',
            'medium': '💡 临床数据建议更具体，引用III期临床试验结果（VAS评分、囊肿缩小5mm等）。',
            'low': '📝 建议：熟记核心数据：E2去势率97.45%、痛经缓解99%、盆腔痛缓解75%、月经恢复缩短12天。'
        },
        '竞品对比': {
            'high': '🌟 竞品对比客观专业！94项RCT Meta分析、妊娠率87.3%、复发率28.5%等数据运用得当。',
            'medium': '💡 竞品对比可以更全面，不仅比疗效，还要比安全性（注射痛1.53% vs 4.08%）。',
            'low': '📝 建议：对比达菲林时强调：突释1/5、PLGA 1/6、注射痛降低62%、硬结降低83%。'
        },
        '处理异议': {
            'high': '🌟 异议处理得当！先认同再回应，用I期药代数据（突释1/5）和注射部位数据化解疑虑。',
            'medium': '💡 处理异议建议用APRC法则：认同(Acknowledge)-探询(Probe)-回应(Respond)-确认(Confirm)。',
            'low': '📝 建议：常见异议（国产质量、不良反应、价格）提前准备标准话术，用数据说话。'
        },
        '促成成交': {
            'high': '🌟 成交信号把握准确，适时提出试用、进院申请或提供文献资料。',
            'medium': '💡 促成成交时可以更主动，提供样品、III期文献、进院支持等具体方案。',
            'low': '📝 建议：识别成交信号（如"听起来不错"）时，立即提出下一步行动（样品/进院/文献）。'
        },
        '结束': {
            'high': '🌟 结束得体，总结要点，为后续跟进留下空间。',
            'medium': '💡 结束语可以更具体，约定下次拜访时间或跟进事项。',
            'low': '📝 建议：结束时要总结维宝宁三大优势（疼痛缓解/复发控制/生育保护），感谢时间，明确下一步。'
        }
    }
    
    stage_fb = feedback_map.get(stage_name, {
        'high': '🌟 表现优秀！话术专业、逻辑清晰。',
        'medium': '👍 表现良好，掌握了基本技巧。',
        'low': '💡 表现一般，还有提升空间。'
    })
    
    # 根据得分和是否提到关键数据给出反馈
    if score >= 9 or (score >= 8 and has_key_data):
        return stage_fb['high']
    elif score >= 6:
        return stage_fb['medium']
    else:
        return stage_fb['low']

def get_final_feedback(scores):
    """总结反馈"""
    avg = sum(scores) / len(scores)
    if avg >= 9:
        return "🏆 优秀！你对维宝宁的产品知识和销售话术掌握得非常扎实，能够灵活运用DA中的临床数据（97.45%去势率、99%疼痛缓解、94项RCT等），专业应对各种场景。"
    elif avg >= 7:
        return "🥈 良好！你掌握了维宝宁的核心卖点和销售技巧，建议在III期临床数据引用和竞品对比（突释1/5、PLGA 1/6）方面继续加强。"
    elif avg >= 5:
        return "🥉 及格！你对维宝宁有基本了解，建议系统学习DA资料，熟记核心临床数据（97.45%、99%、12天、87.3%等）。"
    else:
        return "📚 需改进！建议重新学习维宝宁DA资料，重点掌握三大优势（疼痛缓解/复发控制/生育保护）和核心数据。"

def calculate_score(text, stage):
    """计算得分 - 基于关键词匹配"""
    score = 6  # 基础分
    matches = 0
    
    for keyword, weight in SCORING_KEYWORDS.items():
        if keyword in text:
            matches += weight
    
    # 根据匹配数计算得分
    if matches >= 10:
        score = 10
    elif matches >= 7:
        score = 9
    elif matches >= 4:
        score = 8
    elif matches >= 2:
        score = 7
    else:
        score = 6
    
    return min(score, 10)
def handle_msg(text, user_id):
    text = text.strip()
    
    # 尝试从文件恢复用户状态
    if user_id not in users:
        loaded = load_user(user_id)
        if loaded:
            users[user_id] = loaded
    
    # 开始练习
    if text in ['开始练习', 'start', '开始']:
        users[user_id] = {
            'step': 0,
            'role': None,
            'role_name': None,
            'scores': [],
            'last_time': datetime.now().timestamp()
        }
        save_user(user_id, users[user_id])
        return """👋 欢迎开始维宝宁销售话术对练！

📋 维宝宁®（注射用醋酸曲普瑞林微球）
        • 成分：醋酸曲普瑞林 3.75mg
        • 适应症：子宫内膜异位症（I-IV期）- 被称为"不死的癌症"
        • 用法：每4周肌肉注射1次，月经1-5天开始
        • 主题：告别异痛，维守芳华

🎯 内异症三大难题：疼痛、复发、不孕
        • 70-80%患者有疼痛症状
        • 2年复发率20%，5年复发率50%
        • 20-50%患者合并不孕

请选择医生角色（回复数字）：
1. 主任级专家 ⭐⭐⭐⭐⭐ - 对数据要求高
2. 科室主任 ⭐⭐⭐⭐ - 关注用药规范
3. 主治医师 ⭐⭐⭐⭐ - 关注临床操作
4. 住院医师 ⭐⭐ - 正在学习诊疗
5. 带组专家 ⭐⭐⭐⭐⭐ - 关注手术联合用药"""        
    # 结束练习
    if text in ['结束', 'stop']:
        if user_id in users:
            del users[user_id]
            save_user(user_id, {'step': -1})
        return "对练已结束。发送【开始练习】重新开始"

    u = users.get(user_id)
    if not u or u.get('step', -1) < 0:
        return "发送【开始练习】开始"
    # 选择角色
    if u['step'] == 0:
        if text in ROLES:
            role_name, stars, desc = ROLES[text]
            u['role'] = text
            u['role_name'] = role_name
            u['step'] = 1
            u['scores'] = [6]
            u['last_time'] = datetime.now().timestamp()
            save_user(user_id, u)
            
            doctor_text = random.choice(DIALOGUE[1])
            return f"""✅ 已选择：{role_name} {stars}
💭 {desc}

👨‍⚕️ 医生说："{doctor_text}"

💡 提示：快速自报家门，说明来意，控制在30秒内
💬 请回复你的开场白..."""
        return "请选择 1-5"
    
    step = u['step']
    
    # 计算得分
    user_score = calculate_score(text, step)
    u['scores'].append(user_score)
    
    current_stage = STAGES[step - 1] if step > 0 else STAGES[0]
    feedback = get_feedback(user_score, current_stage, text)
    
    # 完成8轮 - 显示总结报告
    if step >= 7:
        avg = sum(u['scores']) / len(u['scores'])
        final_feedback = get_final_feedback(u['scores'])
        
        # 生成得分图表
        lines = []
        for i, s in enumerate(u['scores']):
            name = STAGES[i] if i < len(STAGES) else f"第{i+1}轮"
            bar = '█' * (s // 2) + '░' * (5 - s // 2)
            emoji = '🌟' if s >= 9 else '👍' if s >= 7 else '💡' if s >= 5 else '📝'
            lines.append(f"{emoji} {i+1}. {name}: {bar} {s}/10")
        
        result = f"""🎉 对练完成！

📊 综合评分：{avg:.1f}/10

📋 各轮得分：
{chr(10).join(lines)}

💬 本轮反馈：
{feedback}

📝 总体评价：
{final_feedback}

---
📚 维宝宁核心数据速记（DA重点）：

【临床疗效】
        • E2去势率：97.45%（vs 达菲林96.94%）
        • 痛经缓解：99%（VAS评分）
        • 盆腔痛缓解：75%
        • 异位囊肿缩小：5mm（vs 达菲林2mm）

【技术优势】
        • 突释峰浓度：仅为达菲林1/5
        • PLGA含量：仅为达菲林1/6
        • 注射部位痛：1.53%（vs 达菲林4.08%）
        • 注射部位硬结：0.51%（vs 达菲林3.06%）

【生育保护】
        • 月经恢复：75%患者缩短12天（89天 vs 101天）
        • 更快恢复排卵，争取受孕"黄金时间窗"

【竞品对比（94项RCT Meta分析）】
        • 有效率：77%（vs 亮丙瑞林高34.5%）
        • 妊娠率：87.3%（vs 亮丙瑞林高48.6%）
        • 复发率：28.5%（vs 亮丙瑞林低47.5%）

【指南推荐】
        • GnRH-a是内异症药物治疗"金标准"
        • 2021-2025年多版指南/共识推荐

发送【开始练习】重新开始"""
        
        del users[user_id]
        save_user(user_id, {'step': -1})
        return result + "\n\n⛔ 本轮练习已结束，发送【开始练习】开始新一轮"

    # 检查是否已结束
    if u.get('step', -1) < 0:
        return "⛔ 本轮练习已结束，发送【开始练习】开始新一轮"

    # 进入下一轮
    u['step'] = step + 1
    u['last_time'] = datetime.now().timestamp()
    save_user(user_id, u)
    
    # 随机选择医生回复
    doctor_text = random.choice(DIALOGUE.get(step + 1, ["继续..."]))
    next_stage = STAGES[step] if step < len(STAGES) else "结束"
    
    # 阶段提示
    stage_hints = {
        '探询需求': '💡 提示：使用SPIN提问法，了解科室用药现状和"疼痛、复发、不孕"三大痛点',
        '产品介绍': '💡 提示：用FAB法则，强调微球制剂优势（突释1/5、PLGA 1/6、注射体验佳）',
        '临床数据': '💡 提示：引用III期数据：97.45%去势率、99%痛经缓解、囊肿缩小5mm、月经恢复缩短12天',
        '竞品对比': '💡 提示：对比达菲林/亮丙瑞林，突出94项RCT Meta分析、妊娠率87.3%、复发率28.5%',
        '处理异议': '💡 提示：用APRC法则，先认同再回应，用I期药代数据（突释1/5）和注射部位数据化解',
        '促成成交': '💡 提示：识别成交信号，主动提出样品试用、进院申请或提供III期文献',
        '结束': '💡 提示：总结三大优势（疼痛缓解/复发控制/生育保护），感谢时间，约定跟进'
    }
    hint = stage_hints.get(next_stage, '')
    
    return f"""👨‍⚕️ 医生说："{doctor_text}"

📊 上轮评分：{user_score}/10
💬 反馈：{feedback}

🎬 第{step+1}轮：{next_stage}
{hint}
💬 请回复..."""

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'version': 'weibaoning-v3-DA'})

@app.route('/webhook/feishu', methods=['POST', 'GET'])
def webhook():
    try:
        if request.method == 'GET':
            return jsonify({'status': 'ok'})
        
        data = request.get_json() or {}
        print(f"[DEBUG] 收到数据: {data}")
        
        if 'challenge' in data:
            return jsonify({'challenge': data['challenge']})
        
        header = data.get('header', {})
        event = data.get('event', {})
        event_type = header.get('event_type', '')
        
        if event_type in ['im.message.receive_v1', 'im.message.p2p_msg']:
            message = event.get('message', {})
            sender = event.get('sender', {})
            
            if message.get('message_type') == 'text':
                try:
                    content = json.loads(message.get('content', '{}'))
                    text = content.get('text', '').strip()
                except:
                    text = str(message.get('content', '')).strip()
                
                text = text.replace('@_user_1', '').replace('@维宝宁销售训练助手', '').strip()
                
                user_id = sender.get('sender_id', {}).get('open_id', '')
                msg_id = message.get('message_id', '')
                
                print(f"[DEBUG] 用户: {user_id}, 消息: {text}")
                
                if text and user_id:
                    reply = handle_msg(text, user_id)
                    print(f"[DEBUG] 回复: {reply[:100]}...")
                    send_msg(user_id, msg_id, reply)
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        import traceback
        print(f"[ERROR] 发生错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
