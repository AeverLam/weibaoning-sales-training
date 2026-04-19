"""
维宝宁销售培训机器人 - 完整修复版
修复三个问题：
1. 追问机制：语义级质量评估，不是纯模板轮换
2. 评分机制：打破长度决定分数，引入真实质量维度
3. 医生角色：回复承接用户说的话，而非模板化泛泛而谈
"""

import os
import json
import re
import uuid
import threading
import requests
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============ 配置 ============
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")

# 存储
sessions = {}
user_sessions = {}
processed_messages = set()

# ============ 持久化消息去重 ============
PROCESSED_MESSAGES_FILE = "/tmp/processed_messages.json"
PROCESSED_MESSAGES_LOCK = threading.Lock()

def load_processed_messages():
    """从文件加载已处理的消息ID"""
    global processed_messages
    try:
        if os.path.exists(PROCESSED_MESSAGES_FILE):
            with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cutoff_time = datetime.now().timestamp() - 7 * 24 * 3600
                processed_messages = {
                    msg_id for msg_id, timestamp in data.items()
                    if timestamp > cutoff_time
                }
                print(f"Loaded {len(processed_messages)} processed messages from file")
    except Exception as e:
        print(f"Error loading processed messages: {e}")
        processed_messages = set()

def save_processed_message(message_id):
    """保存已处理的消息ID到文件"""
    try:
        with PROCESSED_MESSAGES_LOCK:
            data = {}
            if os.path.exists(PROCESSED_MESSAGES_FILE):
                with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data[message_id] = datetime.now().timestamp()
            cutoff_time = datetime.now().timestamp() - 7 * 24 * 3600
            data = {k: v for k, v in data.items() if v > cutoff_time}
            with open(PROCESSED_MESSAGES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving processed message: {e}")

load_processed_messages()

# ============ 医生角色配置 ============
DOCTOR_PROFILES = {
    "主任级专家": {
        "name": "陈教授",
        "title": "主任级专家",
        "difficulty": 5,
        "strictness": 0.95,
        "personality": "学术型、严谨、注重循证医学证据，对数据要求高，不轻易被说服",
        "opening_style": "严肃专业，直接问重点"
    },
    "科室主任": {
        "name": "刘主任",
        "title": "科室主任",
        "difficulty": 4,
        "strictness": 0.8,
        "personality": "管理型、务实、时间紧，关注科室效益和患者满意度",
        "opening_style": "礼貌但直接，关心实用性"
    },
    "主治医师": {
        "name": "张医生",
        "title": "主治医师",
        "difficulty": 3,
        "strictness": 0.6,
        "personality": "实用型、经验导向，关注临床实际效果",
        "opening_style": "友好开放，愿意交流"
    },
    "住院医师": {
        "name": "王医生",
        "title": "住院医师",
        "difficulty": 2,
        "strictness": 0.4,
        "personality": "学习型、听从上级，对新产品好奇但缺乏经验",
        "opening_style": "谦虚好学，主动提问"
    },
    "带组专家": {
        "name": "李教授",
        "title": "带组专家",
        "difficulty": 5,
        "strictness": 0.9,
        "personality": "影响力型、决策权高，一言九鼎，注重品牌和口碑",
        "opening_style": "威严但礼貌，试探对方实力"
    }
}

# ============ 对话场景配置 ============
DIALOGUE_SCENARIOS = [
    {
        "round": 1,
        "topic": "开场建立关系",
        "goal": "建立信任，了解医生对子宫内膜异位症的诊疗观点",
        "key_points": ["礼貌问候", "了解现状", "寻找痛点"],
        "opening": "你好，请问有什么事吗？"
    },
    {
        "round": 2,
        "topic": "产品引入",
        "goal": "自然引入维宝宁，引起医生兴趣",
        "key_points": ["产品定位", "核心优势", "差异化特点"],
        "opening": "说到产品，维宝宁在这方面有什么特点？"
    },
    {
        "round": 3,
        "topic": "机制与循证",
        "goal": "阐述维宝宁的作用机制和临床证据",
        "key_points": ["作用机制", "临床数据", "指南推荐"],
        "opening": "维宝宁的具体作用机制是什么？有相关的临床数据支持吗？"
    },
    {
        "round": 4,
        "topic": "临床应用",
        "goal": "探讨维宝宁在具体临床场景中的应用",
        "key_points": ["适用人群", "用药时机", "联合用药"],
        "opening": "在实际临床中，维宝宁适合哪些患者使用？"
    },
    {
        "round": 5,
        "topic": "安全性与耐受性",
        "goal": "解答医生对药物安全性的顾虑",
        "key_points": ["不良反应", "禁忌症", "特殊人群"],
        "opening": "患者比较关心药物的安全性，维宝宁在这方面的表现如何？"
    },
    {
        "round": 6,
        "topic": "竞品对比",
        "goal": "客观比较维宝宁与竞品的差异",
        "key_points": ["与GnRH对比", "与避孕药对比", "与手术对比"],
        "opening": "相比其他治疗方案，维宝宁有什么独特之处？"
    },
    {
        "round": 7,
        "topic": "处理异议",
        "goal": "有效应对医生的疑虑和反对意见",
        "key_points": ["价格异议", "疗效质疑", "使用习惯"],
        "opening": "有些医生觉得维宝宁价格偏高，你怎么看待这个问题？"
    },
    {
        "round": 8,
        "topic": "达成共识与后续",
        "goal": "促成试用或进一步交流",
        "key_points": ["试用邀请", "资料提供", "后续跟进"],
        "opening": "基于我们今天的交流，您愿意让合适的患者试用维宝宁吗？"
    }
]

# ===== 话题关键词映射（用于评估用户回答是否触及本轮主题）=====
TOPIC_KEYWORDS = {
    "开场建立关系": ["子宫内膜异位症", "内异症", "巧克力囊肿", "腺肌症", "痛经", "不孕", "患者", "科室", "治疗", "新产品", "维宝宁", "产品", "介绍", "聊", "了解"],
    "产品引入": ["维宝宁", "地诺孕素", "孕激素", "GnRH", "唯散宁", "疗效", "数据", "适应症", "上市", "进口", "医保", "特点", "优势", "独特"],
    "机制与循证": ["机制", "作用", "原理", "孕激素", "内膜萎缩", "病灶", "临床试验", "研究", "证据", "指南", "共识", "推荐", "随机", "对照"],
    "临床应用": ["患者", "剂量", "用法", "联合", "手术", "复发", "生育", "备孕", "月经", "疗程", "停药", "处方", "适合"],
    "安全性与耐受性": ["副作用", "不良反应", "出血", "肝功能", "肾功能", "闭经", "骨质", "耐受", "停药", "安全性", "禁忌", "长期"],
    "竞品对比": ["达菲林", "抑那通", "亮丙", "GnRH-a", "避孕药", "地屈孕酮", "手术", "对比", "差异", "优势", "缺点", "仿制药"],
    "处理异议": ["价格", "医保", "费用", "担心", "顾虑", "不好", "没用过", "没听过", "贵", "依从性", "患者经济", "报销"],
    "达成共识与后续": ["试用", "先试试", "合适的患者", "可以", "愿意", "跟进", "资料", "约定", "下次", "联系", "拜访"],
}

# ============================================================
# 修复1：追问机制——语义级质量评估，不再只看长度
# ============================================================
def assess_user_answer_quality(user_message, scenario_topic, exchange_count):
    """
    多维度评估用户回答质量：
    - 维度1：信息密度（字数 + 句数）
    - 维度2：内容空洞度（模板句/纯语气词检测）
    - 维度3：关键词命中（是否触及本轮话题）
    - 维度4：轮次惩罚（被追问次数越多质量越低）
    返回质量等级 + 是否应追问 + 是否应推进
    """
    text = user_message.strip()
    word_count = len(text)

    # --- 维度1：信息密度 ---
    # 统计实际句子数（以句号/问号/感叹号结尾）
    sentences = re.findall(r'[^。！？\n]+[。！？\n]?', text)
    meaningful_sentences = [s for s in sentences if len(s.strip()) > 3]
    sentence_count = len(meaningful_sentences)

    if word_count >= 50 and sentence_count >= 2:
        density_level = 3  # 充实
    elif word_count >= 25 and sentence_count >= 1:
        density_level = 2  # 合格
    elif word_count >= 10:
        density_level = 1  # 偏少
    else:
        density_level = 0  # 空洞

    # --- 维度2：内容空洞度检测 ---
    vagueness_patterns = [
        (r'^(这个|那个|嗯|哦|好吧|好的|行|OK|嗯嗯)[。,，、\s]*$', "纯语气词/代词开场无实质"),
        (r'^.{0,10}[的|得|地][^，,]{0,15}$', "仅一个不完整句子"),
        (r'这个[^，,]{0,30}的[^，,]*$', "以「这个...的」结尾无展开"),
        (r'^(还行|不错|可以|还好|好吧)[。]?$', "仅模糊肯定无展开"),
        (r'^[?\？\！\…\.]+$', "纯标点"),
        (r'^(好的|知道了|了解)[。]?$', "仅表态无内容"),
        (r'^(请问|我想问)[^，,]{0,10}$', "问句开头但未展开"),
    ]

    vagueness_flags = []
    for pattern, label in vagueness_patterns:
        if re.search(pattern, text):
            vagueness_flags.append(label)

    has_vagueness = bool(vagueness_flags)

    # --- 维度3：关键词命中 ---
    keywords = TOPIC_KEYWORDS.get(scenario_topic, [])
    keyword_hits = sum(1 for kw in keywords if kw in text)

    # --- 维度4：轮次惩罚 ---
    repeat_penalty = exchange_count  # 被追问次数越多说明前面回答越差

    # --- 综合判定 ---
    # 核心原则：空洞内容无论多长都是低质量；有关键词且有实质内容才是高质量
    if density_level == 0 or (not text):
        quality = "poor"
        reason = "无实质内容"
    elif has_vagueness and density_level <= 1:
        quality = "poor"
        reason = f"内容空洞：{vagueness_flags[0]}"
    elif density_level >= 2 and keyword_hits >= 1:
        quality = "good"
        reason = f"内容充实（{sentence_count}句）且命中{keyword_hits}个关键词"
    elif density_level >= 2 and keyword_hits == 0:
        quality = "acceptable"
        reason = "有内容但未触及本轮话题关键词"
    elif has_vagueness or density_level == 1:
        quality = "vague"
        reason = f"内容单薄或空洞：{'/'.join(vagueness_flags) if vagueness_flags else '字数不足'}"
    else:
        quality = "acceptable"
        reason = "基本合格"

    # 追问/推进判断
    # poor 或 vague：exchange < 3 则追问；>= 3 必须推进
    # good：直接推进
    # acceptable：exchange == 1 可追问；>= 2 推进
    if quality == "good":
        should_follow_up = False
        should_advance = True
    elif quality in ("poor", "vague"):
        should_follow_up = (exchange_count < 3)
        should_advance = (exchange_count >= 3)
    else:  # acceptable
        should_follow_up = (exchange_count < 2)
        should_advance = (exchange_count >= 2)

    # 轮次惩罚也影响推进概率：exchange 越多越倾向推进
    if exchange_count >= 4:
        should_advance = True
        should_follow_up = False

    return {
        "quality": quality,
        "reason": reason,
        "keyword_hits": keyword_hits,
        "density_level": density_level,
        "sentence_count": sentence_count,
        "vagueness_flags": vagueness_flags,
        "repeat_penalty": repeat_penalty,
        "should_follow_up": should_follow_up,
        "should_advance": should_advance,
    }


def should_advance_round(doctor_reply, exchange_count, quality_result):
    """基于质量评估决定是否推进轮次，不再只看 exchange_count"""
    # 医生回复带推进标记 → 推进
    if "【推进到下一轮】" in doctor_reply:
        return True
    # 质量好 → 推进
    if quality_result["should_advance"]:
        return True
    # 轮次过多 → 强制推进
    if exchange_count >= 4:
        return True
    return False


# ============================================================
# 修复2：医生角色——回复承接用户说的话，不走模板
# ============================================================
def generate_doctor_reply(user_message, session, current_round):
    doctor_type = session["doctor_type"]
    doctor = DOCTOR_PROFILES[doctor_type]
    scenario = DIALOGUE_SCENARIOS[current_round - 1]
    round_data = session["current_round_data"]
    exchange_count = round_data["exchange_count"]

    # --- 构建对话历史 ---
    full_history = ""
    if "all_rounds_messages" in session:
        for round_num, round_messages in session["all_rounds_messages"].items():
            if int(round_num) < current_round:
                full_history += f"\n===== 第{round_num}轮 =====\n"
                for msg in round_messages:
                    if msg["role"] == "user":
                        full_history += f"医药代表：{msg['content'][:100]}...\n"
                    else:
                        full_history += f"{doctor['name']}：{msg['content'][:100]}...\n"

    full_history += f"\n===== 第{current_round}轮（当前）=====\n"
    for msg in round_data["messages"]:
        if msg["role"] == "user":
            full_history += f"医药代表：{msg['content']}\n"
        else:
            full_history += f"{doctor['name']}：{msg['content']}\n"

    # --- 核心：质量评估 ---
    quality_result = assess_user_answer_quality(user_message, scenario['topic'], exchange_count)
    quality = quality_result["quality"]
    reason = quality_result["reason"]
    keyword_hits = quality_result["keyword_hits"]
    vagueness_flags = quality_result["vagueness_flags"]

    # --- 根据质量决定回复策略，并写入 system prompt ---
    if quality == "good":
        strategy = "GOOD"
        strategy_instruction = """【策略：认可并推进】
用户回答质量好。你要：
1. 认可用户说的具体内容（必须提到用户说过的某个具体点，不能空泛说"很好"）
2. 抛出一个与下一场景相关的问题，自然过渡到下一轮
3. 末尾必须添加【推进到下一轮】
示例："刚才提到的那组数据印象很深。关于维宝宁在围手术期的应用，您这边有使用经验吗？【推进到下一轮】" """
    elif quality == "vague":
        strategy = "VAGUE"
        vagueness_desc = '/'.join(vagueness_flags) if vagueness_flags else '内容空泛'
        strategy_instruction = f"""【策略：精准追问（用户回答质量问题：{vagueness_desc}）】
用户说了「{user_message}」，但内容空泛或缺乏具体信息。
追问要求：
1. 必须从用户说的内容里找一个具体点来追问——不能泛泛问"能详细说说吗"
2. 医生的问题是真实的临床疑惑，不是表演性的套路
3. 追问要有具体指向，例如：
   - 用户说"效果不错"→ "是疼痛控制好，还是影像学上病灶缩小了？"
   - 用户说"有点担心"→ "您主要担心哪方面？出血还是对卵巢功能的影响？"
   - 用户说"没怎么用过"→ "内异症手术后的患者您一般用什么方案管理？"
4. 不要推进轮次"""
    else:  # poor 或 acceptable
        if quality == "poor":
            strategy = "POOR"
            strategy_instruction = f"""【策略：追问（用户回答质量差：「{user_message}」）】
用户几乎没有提供有用信息。医生需要：
1. 问一个具体的、能引发思考的问题
2. 问题要与当前场景「{scenario['topic']}」直接相关
3. 禁止：问"详细说说""能具体点吗"——这些不算有效追问
4. 可以结合用户说的零星内容，从具体角度切入"""
        else:
            strategy = "ACCEPTABLE"
            strategy_instruction = """【策略：视情况追问或推进（用户回答质量一般）】
用户有一定内容但不完整或不深入。
1. 如果是第一次交换：追问一个具体缺口
2. 如果已交换过：可以推进到下一轮
3. 追问要承接用户说的具体内容"""

    # --- System Prompt：完整构建 ---
    system_prompt = f"""你是{doctor['title']} {doctor['name']}，真实地扮演一位有血有肉的医生，不是背诵台词的机器人。

【性格】
{doctor['personality']}
说话风格：简短有力（30-60字），像真实医生说话，不啰嗦。

【当前轮次】
第{current_round}轮/共8轮：{scenario['topic']}
本轮目标：{scenario['goal']}

【对话历史】
{full_history}

【本轮对话分析】
- 医药代表刚才说：「{user_message}」
- 质量评估：{quality} — {reason}
- 关键词命中数：{keyword_hits} 个
- 本轮已对话次数：{exchange_count}次

{strategy_instruction}

【关键约束】
- 回复 30-60 字，不要长篇大论
- 禁止问"老师们都怎么说""大家都觉得""你们产品怎么样"这种泛泛的问题
- 禁止重复之前问过的问题（请看对话历史）
- 禁止问完之后自己回答自己
- 追问时问题要具体；推进时要有认可+过渡

回复格式：直接输出医生的话，不要加角色名前缀。"""

    if ZHIPU_API_KEY:
        try:
            url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            headers = {
                "Authorization": f"Bearer {ZHIPU_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "glm-4",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"医药代表说：「{user_message}」"}
                ],
                "temperature": 0.8,
                "max_tokens": 120,
                "top_p": 0.9
            }
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                reply = result["choices"][0]["message"]["content"].strip()
                # 清理可能的角色名前缀
                reply = re.sub(rf'^{re.escape(doctor["name"])}[:：]\s*', '', reply)
                reply = re.sub(rf'^{re.escape(doctor["title"])}[:：]\s*', '', reply)
                reply = reply.strip('"').strip()
                return reply
        except Exception as e:
            print(f"Zhipu API error: {e}")

    # ===== API 不可用时的降级逻辑（仍基于质量评估，不走纯模板）=====
    return generate_fallback_reply(user_message, doctor, scenario, exchange_count, quality, quality_result, current_round)


def generate_fallback_reply(user_message, doctor, scenario, exchange_count, quality, quality_result, current_round=1):
    """降级回复：没有 API 时，基于质量评估生成有针对性的 fallback，不再纯模板轮换"""

    vagueness_flags = quality_result.get("vagueness_flags", [])
    vagueness_desc = '/'.join(vagueness_flags) if vagueness_flags else ''

    if quality == "good":
        transitions = [
            f"这个了解。说到{scenario['topic']}，维宝宁在这方面有什么具体数据？【推进到下一轮】",
            f"有道理。在实际临床上，{scenario['topic']}这块您遇到过哪些情况？【推进到下一轮】",
            f"明白了。这样的话，维宝宁在{scenario['topic']}上有什么优势？【推进到下一轮】"
        ]
        return transitions[min(exchange_count, len(transitions) - 1)]

    elif quality == "vague":
        # 有针对性：用户说"效果不错"，医生追问"哪方面的效果"
        vague_followups = [
            f"「{user_message[:15]}……」能举个例子具体说说吗？",
            f"刚才说的，具体是哪方面的情况？",
            f"您提到{scenario['topic']}，目前科里这类患者多吗？"
        ]
        return vague_followups[min(exchange_count, len(vague_followups) - 1)]

    elif quality == "poor":
        poor_followups = [
            f"关于{scenario['topic']}，您目前用的是什么方案？",
            f"能具体说说是哪类患者吗？",
            f"这类药物您有使用经验吗？"
        ]
        return poor_followups[min(exchange_count, len(poor_followups) - 1)]

    else:  # acceptable
        if exchange_count >= 2:
            transitions = [
                f"了解了。说到{scenario['topic']}，维宝宁有什么特点？【推进到下一轮】",
                f"知道了。那在{scenario['topic']}上，您有什么顾虑吗？【推进到下一轮】"
            ]
            return transitions[min(exchange_count - 2, len(transitions) - 1)]
        else:
            continues = ["嗯，具体怎么用的？", "还有呢？", "您接着说。"]
            return continues[exchange_count % len(continues)]


# ============================================================
# 修复3：评分机制——打破长度决定分数，引入真实质量维度
# ============================================================
def evaluate_round(session, current_round, user_message="", doctor_reply=""):
    """
    多维度评分：
    - 内容准确性（关键词命中 + 句子完整性）
    - 表达清晰度（句子结构 + 标点）
    - 客户需求匹配（关键词命中数）
    - 专业度（是否使用专业术语）
    - 追问惩罚（exchange_count 越多扣越多）
    不再：纯长度决定一切
    """
    round_data = session["current_round_data"]
    exchange_count = round_data["exchange_count"]
    doctor_type = session["doctor_type"]
    doctor = DOCTOR_PROFILES[doctor_type]
    scenario = DIALOGUE_SCENARIOS[current_round - 1]

    text = user_message.strip()

    # --- 维度A：内容准确性（关键词命中）---
    keywords = TOPIC_KEYWORDS.get(scenario['topic'], [])
    keyword_hits = sum(1 for kw in keywords if kw in text)

    # 句子完整性：有没有完整的陈述句或问句
    full_sentences = re.findall(r'[^。！？\n]{8,}[。！？\n]', text)
    sentence_score = min(len(full_sentences), 3)  # 最多3分

    if keyword_hits >= 2 and sentence_score >= 2:
        accuracy = 2.5
    elif keyword_hits >= 1 and sentence_score >= 1:
        accuracy = 2.0
    elif keyword_hits >= 1 or sentence_score >= 1:
        accuracy = 1.5
    elif keyword_hits == 0 and len(text) < 10:
        accuracy = 0.5
    else:
        accuracy = 1.0

    # --- 维度B：表达清晰度 ---
    clarity = 1.5 if sentence_score >= 2 else (1.0 if sentence_score == 1 else 0.5)

    # --- 维度C：客户需求匹配（关键词命中率换算）---
    # 命中越多说明越切题
    if keyword_hits >= 3:
        match = 2.5
    elif keyword_hits == 2:
        match = 2.0
    elif keyword_hits == 1:
        match = 1.5
    elif keyword_hits == 0 and len(text) > 0:
        match = 1.0  # 没命中但有内容
    else:
        match = 0.5

    # --- 维度D：专业度 ---
    medical_terms = [
        "子宫内膜异位症", "内异症", "巧克力囊肿", "腺肌症",
        "GnRH", "地诺孕素", "孕激素", "GnRH-a",
        "病灶", "复发率", "缓解率", "循证", "指南",
        "月经", "痛经", "不孕", "手术", "联合",
        "副作用", "不良反应", "安全性", "耐受性",
        "剂量", "疗程", "处方", "医保", "适应症"
    ]
    medical_hit = sum(1 for term in medical_terms if term in text)

    if medical_hit >= 2:
        professionalism = 2.0
    elif medical_hit == 1:
        professionalism = 1.5
    elif medical_hit == 0 and len(text) > 20:
        professionalism = 1.0
    else:
        professionalism = 0.5

    # --- 加分项 ---
    bonus = 0.0
    # 提及具体数据/研究加分
    if re.search(r'\d+[%％例]', text):
        bonus += 0.5
    # 提及竞品/对比加分
    competitors = ["达菲林", "抑那通", "亮丙瑞林", "避孕药", "地屈孕酮"]
    if any(c in text for c in competitors):
        bonus += 0.5
    # 提及指南/共识加分
    if any(kw in text for kw in ["指南", "共识", "推荐", "循证"]):
        bonus += 0.5

    # --- 追问惩罚（核心：被追问次数越多分数越低）---
    if exchange_count == 1:
        penalty = 0.0       # 一次性说清，0惩罚
    elif exchange_count == 2:
        penalty = 1.0       # 被追问1次，轻惩罚
    elif exchange_count == 3:
        penalty = 2.0       # 被追问2次，中惩罚
    else:
        penalty = 3.0       # 被追问3次以上，重惩罚

    # --- 总分 ---
    total_score = accuracy + clarity + match + professionalism + bonus - penalty
    # 分数范围限制在 0-10
    total_score = max(0.0, min(10.0, round(total_score, 1)))

    # --- 反馈文字 ---
    if total_score >= 9:
        feedback = "回答非常出色！内容专业、逻辑清晰、切中要害，一次性回应了医生的关切。"
    elif total_score >= 7.5:
        feedback = "回答良好，有实质性内容，但还有细节可以深化。"
    elif total_score >= 6:
        feedback = "回答基本合格，内容有所欠缺，建议补充具体数据或案例支撑。"
    elif total_score >= 4:
        feedback = "回答需要改进，内容较空泛或偏离话题，建议加强产品知识和话术准备。"
    else:
        feedback = "回答较差，需要大幅提升。建议重新梳理本轮场景的核心信息点。"

    # --- 优点和不足 ---
    strengths = []
    improvements = []

    if accuracy >= 2.0:
        strengths.append("内容准确、切中要害")
    elif accuracy < 1.5:
        improvements.append("内容偏离主题或缺乏关键词")

    if clarity >= 1.5:
        strengths.append("表达清晰有逻辑")
    else:
        improvements.append("表达不够清晰，句子结构散乱")

    if match >= 2.0:
        strengths.append("精准回应医生关切")
    elif match < 1.5:
        improvements.append("未有效回应本轮话题")

    if penalty == 0:
        strengths.append("一次性回答到位")
    elif penalty >= 2.0:
        improvements.append(f"被追问{exchange_count - 1}次，信息不完整")

    if medical_hit >= 2:
        strengths.append("专业术语运用得当")

    if bonus >= 1.0:
        strengths.append("引用了数据或对比分析")

    return {
        "round": current_round,
        "topic": scenario['topic'],
        "score": total_score,
        "exchange_count": exchange_count,
        "details": {
            "内容准确性": accuracy,
            "表达清晰度": clarity,
            "客户需求匹配": match,
            "专业度": professionalism,
            "加分项": bonus,
            "追问惩罚": -penalty
        },
        "feedback": feedback,
        "strengths": strengths,
        "improvements": improvements
    }


def generate_summary(session_data):
    evaluations = session_data.get("evaluations", [])
    total_score = sum(e.get("score", 0) for e in evaluations)
    max_score = len(evaluations) * 10 if evaluations else 80
    avg_score = total_score / len(evaluations) if evaluations else 0

    doctor = DOCTOR_PROFILES[session_data["doctor_type"]]

    if avg_score >= 9:
        level = "优秀"
        level_emoji = "🏆"
    elif avg_score >= 7.5:
        level = "良好"
        level_emoji = "👍"
    elif avg_score >= 6:
        level = "及格"
        level_emoji = "📖"
    else:
        level = "需改进"
        level_emoji = "💪"

    summary = f"""{level_emoji} 拜访演练总结报告

📊 总体表现
• 医生角色：{doctor['title']} {doctor['name']}
• 难度等级：{"⭐" * doctor['difficulty']}
• 总得分：{total_score:.1f}/{max_score}
• 平均分：{avg_score:.1f}/10
• 综合评级：{level}

📝 各轮表现
"""

    for i, eval_data in enumerate(evaluations, 1):
        scenario = DIALOGUE_SCENARIOS[i-1]
        score = eval_data.get('score', 0)
        stars = "⭐" * int(score // 2)
        if score % 2 >= 1:
            stars += "✨"

        summary += f"""
第{i}轮：{scenario['topic']}
得分：{score}/10 {stars}
对话次数：{eval_data.get('exchange_count', 1)}次
评价：{eval_data.get('feedback', '无')[:60]}...
"""

    all_strengths = []
    all_improvements = []
    for e in evaluations:
        all_strengths.extend(e.get('strengths', []))
        all_improvements.extend(e.get('improvements', []))

    unique_strengths = list(dict.fromkeys(all_strengths))[:3]
    unique_improvements = list(dict.fromkeys(all_improvements))[:3]

    summary += """
💡 总体建议

继续保持：
"""
    for s in unique_strengths:
        summary += f"• {s}\n"

    summary += """
重点提升：
"""
    for i in unique_improvements:
        summary += f"• {i}\n"

    summary += f"""
下次目标：争取总分达到 {min(total_score + 15, max_score):.1f} 分以上

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    return summary


def send_feishu_message(open_id, user_id, reply_text):
    try:
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_resp = requests.post(
            token_url,
            json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
            timeout=10
        )
        token_data = token_resp.json()

        token = token_data.get("tenant_access_token")
        if not token:
            print(f"Failed to get token: {token_data}")
            return

        send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        receive_id = open_id if open_id else user_id
        clean_reply = reply_text.replace("【推进到下一轮】", "")

        max_length = 3000
        if len(clean_reply) > max_length:
            parts = [clean_reply[i:i+max_length] for i in range(0, len(clean_reply), max_length)]
            for part in parts:
                payload = {
                    "receive_id": receive_id,
                    "content": json.dumps({"text": part}, ensure_ascii=False),
                    "msg_type": "text"
                }
                requests.post(send_url, headers=headers, json=payload, timeout=10)
        else:
            payload = {
                "receive_id": receive_id,
                "content": json.dumps({"text": clean_reply}, ensure_ascii=False),
                "msg_type": "text"
            }
            requests.post(send_url, headers=headers, json=payload, timeout=10)

    except Exception as e:
        print(f"Send feishu message error: {e}")


def process_message_async(open_id, user_id, text, message_id):
    try:
        if message_id in processed_messages:
            print(f"Message {message_id} already processed (memory)")
            return

        try:
            if os.path.exists(PROCESSED_MESSAGES_FILE):
                with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if message_id in data:
                        print(f"Message {message_id} already processed (file)")
                        return
        except:
            pass

        processed_messages.add(message_id)
        save_processed_message(message_id)

        reply_text = generate_reply(open_id, user_id, text)

        if not reply_text:
            reply_text = "抱歉，系统处理出错，请发送'开始'重新训练。"

        send_feishu_message(open_id, user_id, reply_text)
    except Exception as e:
        print(f"ERROR in process_message_async: {e}")
        import traceback
        traceback.print_exc()
        try:
            send_feishu_message(open_id, user_id, f"系统错误: {str(e)[:50]}。请发送'开始'重新训练。")
        except:
            pass


def generate_reply(open_id, user_id, text):
    try:
        return _do_generate_reply(open_id, user_id, text)
    except Exception as e:
        print(f"ERROR in generate_reply: {e}")
        import traceback
        traceback.print_exc()
        return f"系统错误: {str(e)[:50]}。请发送'开始'重新训练。"


def _do_generate_reply(open_id, user_id, text):
    if text in ["/start", "开始", "开始训练", "开始练习"]:
        reply_text = """🎯 请选择医生角色开始训练：

1️⃣ 主任级专家 ⭐⭐⭐⭐⭐
   学术型、严谨、注重循证医学证据

2️⃣ 科室主任 ⭐⭐⭐⭐
   管理型、务实、关注科室效益

3️⃣ 主治医师 ⭐⭐⭐
   实用型、经验导向

4️⃣ 住院医师 ⭐⭐
   学习型、听从上级

5️⃣ 带组专家 ⭐⭐⭐⭐⭐
   影响力型、决策权高

请回复数字 1-5 选择医生"""
        user_sessions[user_id] = "selecting_doctor"
        return reply_text

    elif text in ["1", "2", "3", "4", "5"] and user_sessions.get(user_id) == "selecting_doctor":
        doctor_map = {"1": "主任级专家", "2": "科室主任", "3": "主治医师", "4": "住院医师", "5": "带组专家"}
        doctor_type = doctor_map.get(text, "副主任医师")

        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "doctor_type": doctor_type,
            "current_round": 1,
            "current_round_data": {
                "exchange_count": 0,
                "messages": [],
                "evaluated": False
            },
            "all_rounds_messages": {},
            "evaluations": [],
            "start_time": datetime.now().isoformat(),
            "status": "active"
        }
        sessions[session_id] = session_data
        user_sessions[user_id] = session_id

        scenario = DIALOGUE_SCENARIOS[0]
        doctor = DOCTOR_PROFILES[doctor_type]
        opening = scenario['opening']

        session_data["current_round_data"]["messages"].append({
            "role": "doctor",
            "content": opening
        })

        return f"""🎯 销售话术对练开始！

👨‍⚕️ 医生角色：{doctor['title']} {doctor['name']}
难度：{'⭐' * doctor['difficulty']}

{doctor['name']}：{opening}

💡 第1轮/共8轮：{scenario['topic']}
🎯 目标：{scenario['goal']}"""

    elif text in ["/help", "帮助", "?", "？"]:
        return """🎯 维宝宁销售培训机器人

【训练说明】
• 共8轮对话，每轮可以有多轮交流
• 医生会根据你的回答质量决定是否追问
• 每轮结束给一次评分（满分10分）
• 追问次数会影响评分（被追问越多，扣分越多）
• 完成后生成总结报告

发送「开始」即可开始训练！"""

    elif user_sessions.get(user_id) == "selecting_doctor":
        return "请选择医生：回复 1-5 选择医生角色"

    elif user_id in user_sessions:
        session_id = user_sessions[user_id]

        if session_id in ["selecting_doctor", None]:
            return "会话异常，请发送「开始」重新开始"

        if session_id not in sessions:
            del user_sessions[user_id]
            return "会话已过期，请发送「开始」重新开始"

        session = sessions[session_id]
        current_round = session["current_round"]
        round_data = session["current_round_data"]

        if current_round > 8:
            summary = generate_summary(session)
            del user_sessions[user_id]
            return summary + "\n\n🎉 训练结束！发送「开始」可重新练习。"

        round_data["exchange_count"] += 1
        round_data["messages"].append({
            "role": "user",
            "content": text,
            "exchange": round_data["exchange_count"]
        })

        # 生成医生回复（含质量评估）
        doctor_reply = generate_doctor_reply(text, session, current_round)

        round_data["messages"].append({
            "role": "doctor",
            "content": doctor_reply,
            "exchange": round_data["exchange_count"]
        })

        if "all_rounds_messages" not in session:
            session["all_rounds_messages"] = {}
        session["all_rounds_messages"][str(current_round)] = round_data["messages"].copy()

        # 质量评估结果同步传给推进判断
        quality_result = assess_user_answer_quality(text, DIALOGUE_SCENARIOS[current_round - 1]['topic'], round_data["exchange_count"])
        should_advance = should_advance_round(doctor_reply, round_data["exchange_count"], quality_result)

        if should_advance:
            evaluation = evaluate_round(session, current_round, text, doctor_reply)
            session["evaluations"].append(evaluation)

            clean_doctor_reply = doctor_reply.replace("【推进到下一轮】", "").strip()
            if clean_doctor_reply.endswith(("?", "？")):
                for i in range(len(clean_doctor_reply) - 1, -1, -1):
                    if clean_doctor_reply[i] in "。.！!":
                        clean_doctor_reply = clean_doctor_reply[:i+1]
                        break

            session["current_round"] = current_round + 1
            session["current_round_data"] = {
                "exchange_count": 0,
                "messages": [],
                "evaluated": False
            }

            if current_round == 8:
                summary = generate_summary(session)
                del user_sessions[user_id]
                score = evaluation.get('score', 0)
                feedback = evaluation.get('feedback', '')[:80]

                return f"""👨‍⚕️ {clean_doctor_reply}

📊 第8轮评分：{score}/10
💬 反馈：{feedback}

{summary}

🎉 训练结束！发送「开始」可重新练习。"""
            else:
                next_round = session["current_round"]
                next_scenario = DIALOGUE_SCENARIOS[next_round - 1]
                score = evaluation.get('score', 0)
                feedback = evaluation.get('feedback', '')[:80]

                return f"""👨‍⚕️ {clean_doctor_reply}

📊 第{current_round}轮评分：{score}/10
💬 反馈：{feedback}

💡 第{next_round}轮/共8轮：{next_scenario['topic']}
🎯 目标：{next_scenario['goal']}"""
        else:
            scenario = DIALOGUE_SCENARIOS[current_round - 1]
            exchange_info = f"（第{round_data['exchange_count']}次对话）" if round_data['exchange_count'] > 1 else ""

            clean_doctor_reply = doctor_reply.replace("【推进到下一轮】", "").strip()

            return f"""👨‍⚕️ {clean_doctor_reply}

💡 第{current_round}轮/共8轮：{scenario['topic']} {exchange_info}
🎯 目标：{scenario['goal']}"""

    else:
        return "请先发送「开始」或「/start」开始训练"


@app.route("/webhook/feishu", methods=["POST"])
def feishu_webhook():
    return feishu_chat()


@app.route("/api/feishu/chat", methods=["POST"])
def feishu_chat():
    raw_data = request.get_data(as_text=True)
    data = json.loads(raw_data) if raw_data else {}

    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    event = data.get("event", {})
    message = event.get("message", {})
    sender = event.get("sender", {})
    sender_id = sender.get("sender_id", {})
    user_id = sender_id.get("user_id", "")
    open_id = sender_id.get("open_id", "")
    message_id = message.get("message_id", "")

    content_str = message.get("content", "{}")
    try:
        content = json.loads(content_str) if isinstance(content_str, str) else content_str
    except:
        content = {}
    text = content.get("text", "").strip()

    if message_id in processed_messages:
        print(f"Duplicate message blocked (memory): {message_id}")
        return jsonify({"code": 0, "msg": "success"})

    try:
        if os.path.exists(PROCESSED_MESSAGES_FILE):
            with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
                if message_id in file_data:
                    print(f"Duplicate message blocked (file): {message_id}")
                    processed_messages.add(message_id)
                    return jsonify({"code": 0, "msg": "success"})
    except Exception as e:
        print(f"Error checking processed messages file: {e}")

    thread = threading.Thread(
        target=process_message_async,
        args=(open_id, user_id, text, message_id)
    )
    thread.daemon = True
    thread.start()

    return jsonify({"code": 0, "msg": "success"})


@app.route("/api/start", methods=["POST"])
def start_session():
    data = request.json or {}
    user_id = data.get("user_id", "anonymous")
    doctor_type = data.get("doctor_type", "副主任医师")

    if doctor_type not in DOCTOR_PROFILES:
        doctor_type = "副主任医师"

    session_id = str(uuid.uuid4())
    session_data = {
        "session_id": session_id,
        "user_id": user_id,
        "doctor_type": doctor_type,
        "current_round": 1,
        "current_round_data": {
            "exchange_count": 0,
            "messages": [],
            "evaluated": False
        },
        "evaluations": [],
        "start_time": datetime.now().isoformat(),
        "status": "active"
    }
    sessions[session_id] = session_data

    scenario = DIALOGUE_SCENARIOS[0]
    doctor = DOCTOR_PROFILES[doctor_type]
    opening = scenario['opening']

    session_data["current_round_data"]["messages"].append({
        "role": "doctor",
        "content": opening
    })

    return jsonify({
        "session_id": session_id,
        "message": f"{doctor['name']}：{opening}",
        "round": 1,
        "topic": scenario['topic'],
        "goal": scenario['goal']
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    session_id = data.get("session_id")
    user_message = data.get("message", "")

    if not session_id or session_id not in sessions:
        return jsonify({"error": "会话不存在"}), 400

    session = sessions[session_id]
    current_round = session["current_round"]
    round_data = session["current_round_data"]

    if current_round > 8:
        return jsonify({"error": "对话已完成"}), 400

    round_data["exchange_count"] += 1
    round_data["messages"].append({
        "role": "user",
        "content": user_message,
        "exchange": round_data["exchange_count"]
    })

    doctor_reply = generate_doctor_reply(user_message, session, current_round)

    round_data["messages"].append({
        "role": "doctor",
        "content": doctor_reply,
        "exchange": round_data["exchange_count"]
    })

    quality_result = assess_user_answer_quality(user_message, DIALOGUE_SCENARIOS[current_round - 1]['topic'], round_data["exchange_count"])
    should_advance = should_advance_round(doctor_reply, round_data["exchange_count"], quality_result)

    result = {
        "session_id": session_id,
        "round": current_round,
        "doctor_reply": doctor_reply.replace("【推进到下一轮】", "").strip(),
        "exchange_count": round_data["exchange_count"],
        "advanced": should_advance
    }

    if should_advance:
        evaluation = evaluate_round(session, current_round)
        session["evaluations"].append(evaluation)

        result["evaluation"] = evaluation

        session["current_round"] = current_round + 1
        session["current_round_data"] = {
            "exchange_count": 0,
            "messages": [],
            "evaluated": False
        }

        if current_round == 8:
            session["status"] = "completed"
            result["completed"] = True
            result["summary"] = generate_summary(session)
        else:
            next_scenario = DIALOGUE_SCENARIOS[session["current_round"] - 1]
            result["next_topic"] = next_scenario["topic"]
            result["next_goal"] = next_scenario["goal"]

    return jsonify(result)


@app.route("/api/summary/<session_id>", methods=["GET"])
def get_summary(session_id):
    if session_id not in sessions:
        return jsonify({"error": "会话不存在"}), 404

    session = sessions[session_id]
    summary = generate_summary(session)

    return jsonify({
        "session_id": session_id,
        "summary": summary,
        "evaluations": session.get("evaluations", [])
    })


@app.route("/api/doctors", methods=["GET"])
def list_doctors():
    doctors = []
    for key, profile in DOCTOR_PROFILES.items():
        doctors.append({
            "type": key,
            "name": profile["name"],
            "title": profile["title"],
            "difficulty": profile["difficulty"],
            "strictness": profile["strictness"]
        })

    return jsonify({"doctors": doctors})


@app.route("/")
def index():
    return "维宝宁销售培训机器人 - 运行正常"


@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
