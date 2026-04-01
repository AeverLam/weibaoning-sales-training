#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 开始对练
初始化对练会话，选择医生角色和场景
"""
import json
import sys
import os
from datetime import datetime
# 医生角色库
DOCTOR_PROFILES = {
       "主任级专家": {
              "title": "主任医师/教授",
              "age": "50-60岁",
              "type": "学术型",
              "difficulty": 5,
              "characteristics": [
                     "注重循证医学证据",
                     "喜欢讨论作用机制",
                     "对新药持谨慎态度",
                     "重视学术声誉",
                     "决策谨慎但影响力大"
              ],
              "concerns": [
                     "临床试验数据（样本量、终点、统计学意义）",
                     "指南推荐级别",
                     "作用机制的科学性",
                     "长期安全性数据",
                     "学术会议和发表文献"
              ],
              "typical_questions": [
                     "这个研究的样本量有多大？",
                     "有III期临床数据吗？",
                     "作用机制是什么？",
                     "指南是怎么推荐的？",
                     "不良反应的发生率是多少？"
              ],
              "style_tags": ["学术导向", "严谨", "保守型"]
       },
       "科室主任": {
              "title": "科室主任/副主任医师",
              "age": "40-50岁",
              "type": "管理型",
              "difficulty": 4,
              "characteristics": [
                     "注重实际效果",
                     "关心科室运营成本",
                     "时间观念强",
                     "决策果断",
                     "重视患者满意度"
              ],
              "concerns": [
                     "疗效确切性",
                     "安全性/不良反应管理",
                     "性价比",
                     "患者依从性",
                     "医保政策"
              ],
              "typical_questions": [
                     "这个产品疗效确切吗？",
                     "不良反应多不多？",
                     "价格怎么样？医保报吗？",
                     "患者依从性如何？",
                     "用了能减轻我的工作负担吗？"
              ],
              "style_tags": ["务实", "时间紧张", "价格敏感"]
       },
       "主治医师": {
              "title": "主治医师",
              "age": "35-45岁",
              "type": "实用型",
              "difficulty": 3,
              "characteristics": [
                     "注重临床经验",
                     "喜欢听同行反馈",
                     "对新药接受度中等",
                     "重视用药便利性",
                     "愿意尝试新产品"
              ],
              "concerns": [
                     "临床使用便利性",
                     "其他医生的使用经验",
                     "患者反馈",
                     "适应症匹配度",
                     "剂量调整的灵活性"
              ],
              "typical_questions": [
                     "其他医院用得怎么样？",
                     "患者反馈如何？",
                     "使用起来方便吗？",
                     "适合我这类患者吗？",
                     "有没有试用装？"
              ],
              "style_tags": ["临床导向", "开放型"]
       },
       "住院医师": {
              "title": "住院医师/规培生",
              "age": "25-35岁",
              "type": "学习型",
              "difficulty": 2,
              "characteristics": [
                     "学习意愿强",
                     "基础知识扎实但临床经验少",
                     "对新产品好奇",
                     "决策权小但可能成为未来客户",
                     "愿意接受培训"
              ],
              "concerns": [
                     "适应症和禁忌症",
                     "用法用量",
                     "不良反应识别和处理",
                     "与上级医师的沟通",
                     "学习资料和培训机会"
              ],
              "typical_questions": [
                     "这个药主要治什么？",
                     "用法用量是怎样的？",
                     "有哪些禁忌症需要注意？",
                     "出现不良反应怎么处理？",
                     "有学习资料吗？"
              ],
              "style_tags": ["学习热情", "时间充裕"]
       },
       "带组专家": {
              "title": "主任医师/学科带头人",
              "age": "45-55岁",
              "type": "影响力型",
              "difficulty": 5,
              "characteristics": [
                     "学术和临床并重",
                     "带教下级医生",
                     "学术会议演讲嘉宾",
                     "指南编写参与者",
                     "决策影响整个科室"
              ],
              "concerns": [
                     "学术创新性",
                     "临床实用性",
                     "带教价值",
                     "学术合作机会",
                     "学科影响力"
              ],
              "typical_questions": [
                     "这个产品在学科发展中有什么价值？",
                     "适合带教使用吗？",
                     "有没有学术合作的机会？",
                     "对学科发展有什么帮助？",
                     "我可以在学术会议上介绍一下吗？"
              ],
              "style_tags": ["学术导向", "疗效优先", "权威"]
       }
}
# 对练场景库
SCENARIOS = {
       "完整拜访流程": {
              "description": "模拟一次完整的医生拜访，从开场白到跟进服务全流程",
              "rounds": [
                     {"name": "开场白", "time": 2, "goal": "建立关系、获得时间许可"},
                     {"name": "探询需求", "time": 3, "goal": "了解患者类型和未满足需求"},
                     {"name": "产品介绍", "time": 3, "goal": "传递产品价值"},
                     {"name": "处理异议", "time": 3, "goal": "化解顾虑"},
                     {"name": "促成成交", "time": 2, "goal": "获得试用承诺"},
                     {"name": "跟进服务", "time": 2, "goal": "建立长期关系"}
              ],
              "difficulty": 4
       },
       "价格异议处理": {
              "description": "医生对维宝宁价格表示顾虑，需要有效化解",
              "focus": "价格异议处理",
              "key_skills": ["APRC法则", "价值转化", "经济学数据"],
              "difficulty": 3
       },
       "竞品对比应对": {
              "description": "医生对现有竞品满意，需要展示维宝宁的差异化价值",
              "focus": "竞品异议处理",
              "key_skills": ["差异化展示", "不贬低竞品", "定位为互补"],
              "difficulty": 4
       },
       "安全性质疑": {
              "description": "医生对新药安全性有顾虑，需要提供充分证据",
              "focus": "安全性异议",
              "key_skills": ["安全性数据", "机制解释", "风险缓解"],
              "difficulty": 3
       },
       "学术型专家拜访": {
              "description": "面对学术权威，需要充分展示循证医学证据",
              "focus": "学术推广",
              "key_skills": ["临床数据", "作用机制", "指南推荐"],
              "difficulty": 5
       },
       "时间紧张快速拜访": {
              "description": "医生非常忙，需要在极短时间内完成沟通",
              "focus": "快速沟通",
              "key_skills": ["简洁开场", "直击痛点", "快速成交"],
              "difficulty": 4
       }
}
# 异议类型库
OBJECTIONS = {
       "价格异议": [
              "太贵了",
              "比竞品贵不少",
              "医保不报吧？",
              "患者可能接受不了"
       ],
       "竞品异议": [
              "我习惯用XX了",
              "XX用得很好，不想换",
              "你们和XX比有什么优势？",
              "患者点名要XX"
       ],
       "安全性异议": [
              "安全性怎么样？",
              "副作用大吗？",
              "刚上市不久，不敢用",
              "有长期安全性数据吗？"
       ],
       "证据异议": [
              "有指南推荐吗？",
              "证据充分吗？",
              "发表在什么期刊上？",
              "研究质量怎么样？"
       ],
       "习惯异议": [
              "用习惯了，不想换",
              "老药安全性更有把握",
              "换了药患者会问",
              "没必要冒险"
       ],
       "医保异议": [
              "医保不报吧？",
              "集采没中标？",
              "医院进药有限制？",
              "患者嫌贵"
       ]
}
def generate_doctor_prompt(doctor_type, scenario, style_tags=None):
       """
       生成医生角色扮演的系统Prompt
       """
       profile = DOCTOR_PROFILES.get(doctor_type, DOCTOR_PROFILES["科室主任"])
       scenario_info = SCENARIOS.get(scenario, SCENARIOS["完整拜访流程"])
       
       # 构建性格描述
       characteristics = "、".join(profile["characteristics"])
       concerns = "、".join(profile["concerns"])
       typical_questions = "\n- ".join(profile["typical_questions"])
       
       # 风格标签
       style_desc = ""
       if style_tags:
              style_desc = f"\n**当前状态**：{'、'.join(style_tags)}"
       
       prompt = f"""你是一位{profile['title']}（{profile['type']}），{profile['age']}。
       
       **你的性格特点**：{characteristics}
       
       **你最关注的问题**：{concerns}{style_desc}
       
       **你常问的问题**：
       - {typical_questions}
       
       **当前场景**：{scenario_info['description']}
       
       **角色扮演要求**：
       1. 全程保持医生角色，用第一人称"我"回答
       2. 回答要符合你的身份、性格和当前场景
       3. 根据对练难度提出相应级别的挑战
       4. 适时提出异议或质疑，帮助对方练习应对技巧
       5. 如果对方的回答专业且有说服力，态度可以逐渐软化
       6. 不要使用"作为医生"这样的前缀，直接回答
       7. 每次回复控制在2-3句话，保持对话节奏
       
       **对练目标**：帮助医药代表练习{scenario_info.get('focus', '销售话术')}技巧
       
       现在开始对话，请等待医药代表开场。"""
       
       return prompt
def start_practice(doctor_type="科室主任", scenario="完整拜访流程", style_tags=None, user_id="anonymous"):
       """
       开始对练
       """
       if doctor_type not in DOCTOR_PROFILES:
              return {
                     "error": f"未知的医生类型: {doctor_type}",
                     "available_types": list(DOCTOR_PROFILES.keys())
              }
       
       if scenario not in SCENARIOS:
              return {
                     "error": f"未知的场景: {scenario}",
                     "available_scenarios": list(SCENARIOS.keys())
              }
       
       # 生成会话ID
       session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
       
       # 生成医生Prompt
       doctor_prompt = generate_doctor_prompt(doctor_type, scenario, style_tags)
       
       # 构建会话上下文
       session_context = {
              "session_id": session_id,
              "user_id": user_id,
              "doctor_type": doctor_type,
              "scenario": scenario,
              "style_tags": style_tags or [],
              "start_time": datetime.now().isoformat(),
              "status": "active",
              "round": 1,
              "messages": [],
              "doctor_prompt": doctor_prompt,
              "difficulty": DOCTOR_PROFILES[doctor_type]["difficulty"],
              "evaluation": {
                     "scores": {},
                     "feedback": ""
              }
       }
       
       # 保存会话数据
       save_session(session_context)
       
       return {
              "success": True,
              "session_id": session_id,
              "doctor_type": doctor_type,
              "scenario": scenario,
              "difficulty": DOCTOR_PROFILES[doctor_type]["difficulty"],
              "doctor_profile": {
                     "title": DOCTOR_PROFILES[doctor_type]["title"],
                     "type": DOCTOR_PROFILES[doctor_type]["type"],
                     "characteristics": DOCTOR_PROFILES[doctor_type]["characteristics"]
              },
              "message": f"对练开始！你正在拜访一位{doctor_type}，场景是：{scenario}",
              "doctor_prompt": doctor_prompt
       }
def save_session(session_context):
       """
       保存会话数据到文件
       """
       data_dir = os.path.expanduser("~/.openclaw/workspace/skills/weibaoning-sales-training/data/sessions")
       os.makedirs(data_dir, exist_ok=True)
       
       session_file = os.path.join(data_dir, f"{session_context['session_id']}.json")
       with open(session_file, 'w', encoding='utf-8') as f:
              json.dump(session_context, f, ensure_ascii=False, indent=2)
def load_session(session_id):
       """
       加载会话数据
       """
       session_file = os.path.expanduser(f"~/.openclaw/workspace/skills/weibaoning-sales-training/data/sessions/{session_id}.json")
       if os.path.exists(session_file):
              with open(session_file, 'r', encoding='utf-8') as f:
                     return json.load(f)
       return None
if __name__ == "__main__":
       # 命令行参数
       if len(sys.argv) < 2:
              print("用法: python start_practice.py <医生类型> [场景] [用户ID]")
              print(f"\n可选医生类型: {', '.join(DOCTOR_PROFILES.keys())}")
              print(f"\n可选场景: {', '.join(SCENARIOS.keys())}")
              sys.exit(1)
       
       doctor_type = sys.argv[1]
       scenario = sys.argv[2] if len(sys.argv) > 2 else "完整拜访流程"
       user_id = sys.argv[3] if len(sys.argv) > 3 else "anonymous"
       
       result = start_practice(doctor_type, scenario, user_id=user_id)
       print(json.dumps(result, ensure_ascii=False, indent=2))
