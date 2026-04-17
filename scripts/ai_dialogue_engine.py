#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - AI智能对话引擎（修复版）
使用LLM生成医生回复、实时评估、智能追问、个性化反馈
"""

import json
import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入医生角色库
from scripts.start_practice import DOCTOR_PROFILES, SCENARIOS, OBJECTIONS


class AI_DialogueEngine:
    """AI智能对话引擎"""
    
    def __init__(self, session_id, doctor_type, scenario, style_tags=None):
        self.session_id = session_id
        self.doctor_type = doctor_type
        self.scenario = scenario
        self.style_tags = style_tags or []
        self.round = 1
        self.messages = []
        self.scores = []
        self.follow_up_count = 0  # 当前轮追问次数
        self.max_follow_up = 3    # 最多追问3次
        
        # 获取医生档案
        self.profile = DOCTOR_PROFILES.get(doctor_type, DOCTOR_PROFILES["科室主任"])
        self.scenario_info = SCENARIOS.get(scenario, SCENARIOS["完整拜访流程"])
        
        # 生成系统Prompt
        self.system_prompt = self._generate_system_prompt()
        
    def _generate_system_prompt(self):
        """生成医生角色系统Prompt"""
        characteristics = "、".join(self.profile["characteristics"])
        concerns = "、".join(self.profile["concerns"])
        typical_questions = "\n- ".join(self.profile["typical_questions"])
        
        style_desc = ""
        if self.style_tags:
            style_desc = f"\n**当前状态**：{'、'.join(self.style_tags)}"
        
        prompt = f"""你是一位{self.profile['title']}（{self.profile['type']}），{self.profile['age']}。

**你的性格特点**：{characteristics}

**你最关注的问题**：{concerns}{style_desc}

**你常问的问题**：
- {typical_questions}

**当前场景**：{self.scenario_info['description']}

**角色扮演要求**：
1. 全程保持医生角色，用第一人称"我"回答
2. 回答要符合你的身份、性格和当前场景
3. 根据对练难度提出相应级别的挑战
4. 适时提出异议或质疑，帮助对方练习应对技巧
5. 如果对方的回答专业且有说服力，态度可以逐渐软化
6. 不要使用"作为医生"这样的前缀，直接回答
7. 每次回复控制在2-3句话，保持对话节奏
8. 根据对话进展自然推进，不要按固定脚本

**对练目标**：帮助医药代表练习{self.scenario_info.get('focus', '销售话术')}技巧

**维宝宁产品知识参考**：
- 通用名：注射用醋酸亮丙瑞林微球
- 适应症：子宫内膜异位症、子宫肌瘤、中枢性性早熟、前列腺癌、乳腺癌
- 特点：E2去势率97.45%，网状Meta分析94项RCT，妊娠率87.3%
- 规格：3.75mg/支
- 价格：约1000元/支

现在开始对话，请等待医药代表开场。"""
        
        return prompt
    
    def get_doctor_response(self, user_message):
        """使用LLM生成医生回复"""
        # 构建对话历史
        conversation_history = []
        for msg in self.messages:
            conversation_history.append({
                "role": "assistant" if msg["role"] == "doctor" else "user",
                "content": msg["content"]
            })
        
        # 构建完整prompt
        messages = [
            {"role": "system", "content": self.system_prompt}
        ] + conversation_history + [
            {"role": "user", "content": user_message}
        ]
        
        # 调用LLM生成医生回复
        try:
            doctor_reply = self._call_llm(messages)
            return doctor_reply
        except Exception as e:
            # 如果LLM调用失败，使用备用回复
            return self._get_fallback_response()
    
    def _call_llm(self, messages):
        """调用LLM API"""
        # 获取环境变量中的API配置
        model = os.environ.get('LLM_MODEL', 'minimax/abab6.5-chat')
        api_key = os.environ.get('MINIMAX_API_KEY', '')
        
        try:
            if 'minimax' in model.lower():
                return self._call_minimax(messages, api_key)
            else:
                return self._call_minimax(messages, api_key)  # 默认使用MiniMax
        except Exception as e:
            return self._simulate_doctor_response(messages)
    
    def _call_minimax(self, messages, api_key):
        """调用MiniMax API"""
        import requests
        
        url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        
        # 提取system prompt
        system_content = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                user_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "abab6.5-chat",
            "messages": [
                {"role": "system", "content": system_content}
            ] + user_messages,
            "temperature": 0.7,
            "max_tokens": 200
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        else:
            raise Exception(f"MiniMax API error: {result}")
    
    def _simulate_doctor_response(self, messages):
        """模拟医生回复（当API不可用时使用）"""
        user_msg = messages[-1]["content"] if messages else ""
        
        # 根据医生类型和轮数生成回复
        responses = {
            "主任级专家": [
                "这个产品的III期临床数据怎么样？样本量多大？",
                "作用机制是什么？有分子层面的研究吗？",
                "指南推荐级别是什么？有A级证据吗？",
                "长期安全性数据如何？随访了多久？",
                "如果数据确实可靠，可以考虑在科室推广。"
            ],
            "科室主任": [
                "疗效确切吗？不良反应多不多？",
                "价格怎么样？医保能报吗？",
                "患者依从性如何？需要长期随访吗？",
                "性价比如何？和现有产品比有优势吗？",
                "听起来不错，可以先试用看看效果。"
            ],
            "主治医师": [
                "其他医院用得怎么样？有反馈吗？",
                "使用起来方便吗？需要特殊培训吗？",
                "适合我这类患者吗？适应症匹配吗？",
                "有没有试用装？我想先给几个患者试试。",
                "如果效果好，我会推荐给主任的。"
            ],
            "住院医师": [
                "这个药主要治什么？适应症有哪些？",
                "用法用量是怎样的？需要注意什么？",
                "有哪些禁忌症？不良反应怎么处理？",
                "有学习资料吗？我想多了解一下。",
                "谢谢你的介绍，我会向上级医师汇报的。"
            ],
            "带组专家": [
                "这个产品在学科发展中有什么价值？",
                "适合带教使用吗？有教学价值吗？",
                "有没有学术合作的机会？",
                "对学科影响力有什么帮助？",
                "如果确实有价值，我可以在学术会议上介绍。"
            ]
        }
        
        # 根据轮数选择回复
        type_responses = responses.get(self.doctor_type, responses["科室主任"])
        idx = min(self.round - 1, len(type_responses) - 1)
        return type_responses[idx]
    
    def _get_fallback_response(self):
        """备用回复"""
        return "嗯，继续说，我在听。"
    
    def evaluate_response(self, user_message, doctor_context):
        """
        使用LLM实时评估用户回答质量
        新评分标准：每轮10分制
        """
        eval_prompt = f"""你是一位销售培训专家，正在评估医药代表的回答质量。

**当前场景**：{self.scenario_info['description']}
**当前轮次**：第{self.round}轮
**医生角色**：{self.doctor_type}

**医生的问题/陈述**：
{doctor_context}

**医药代表的回答**：
{user_message}

**评估维度**（总分10分）：
1. 内容准确性（0-3分）：信息是否正确、专业，数据是否准确
2. 表达清晰度（0-2分）：逻辑是否清晰、易懂，结构是否合理
3. 客户需求匹配（0-2分）：是否回应了医生的关切和问题
4. 专业度（0-2分）：是否体现专业素养，术语使用是否得当
5. 加分项（0-1分）：是否有超出预期的亮点

**评分标准**：
- 9-10分：优秀
- 7-8分：良好
- 5-6分：合格
- 0-4分：待提升

**追问判断**：
如果回答得分低于6分或过于简短（少于20字），应该追问。追问时保持医生角色，用疑问句引导对方补充信息。

请输出JSON格式：
{{
  "content_accuracy": 分数,
  "expression_clarity": 分数,
  "customer_match": 分数,
  "professionalism": 分数,
  "bonus": 分数,
  "total_score": 总分,
  "grade": "等级(A/B/C/D/F)",
  "need_follow_up": true/false,
  "follow_up_question": "如果需要追问，写出追问内容",
  "strengths": ["亮点1", "亮点2"],
  "weaknesses": ["改进点1", "改进点2"],
  "feedback": "个性化反馈建议"
}}"""
        
        try:
            # 调用LLM进行评估
            eval_messages = [
                {"role": "system", "content": "你是一位专业的医药销售培训专家。"},
                {"role": "user", "content": eval_prompt}
            ]
            
            eval_result = self._call_llm(eval_messages)
            
            # 解析JSON结果
            import re
            json_match = re.search(r'\{.*\}', eval_result, re.DOTALL)
            if json_match:
                eval_data = json.loads(json_match.group())
            else:
                eval_data = json.loads(eval_result)
            
            return eval_data
            
        except Exception as e:
            # 如果评估失败，使用规则评分
            return self._rule_based_evaluation(user_message)
    
    def _rule_based_evaluation(self, user_message):
        """基于规则的评分（当LLM不可用时使用）"""
        score = 5  # 基础分
        need_follow_up = False
        follow_up_question = ""
        
        # 字数检查
        if len(user_message) < 20:
            score = 2
            need_follow_up = True
            follow_up_question = "能详细说说吗？我想了解更多细节。"
        elif len(user_message) < 50:
            score = 4
            need_follow_up = True
            follow_up_question = "还有吗？我想听听更具体的介绍。"
        
        # 关键词匹配加分
        keywords = ['E2', '去势率', '97%', '微球', '亮丙瑞林', '子宫内膜异位症', '妊娠率', '87.3%']
        matches = sum(1 for w in keywords if w in user_message)
        if matches >= 2:
            score += 2
        elif matches >= 1:
            score += 1
        
        # 限制最高分
        score = min(score, 10)
        
        # 生成反馈
        if score >= 9:
            feedback = "🌟 表现优秀！话术专业、逻辑清晰。"
            grade = "A"
        elif score >= 7:
            feedback = "👍 表现良好，掌握了基本技巧。"
            grade = "B"
        elif score >= 5:
            feedback = "💡 表现一般，建议加强学习。"
            grade = "C"
            if not need_follow_up:
                need_follow_up = True
                follow_up_question = "能再具体说说吗？"
        else:
            feedback = "📝 需要改进！建议系统学习。"
            grade = "D"
            if not need_follow_up:
                need_follow_up = True
                follow_up_question = "我不太明白你的意思，能再解释一下吗？"
        
        return {
            "content_accuracy": min(score * 0.3, 3),
            "expression_clarity": min(score * 0.2, 2),
            "customer_match": min(score * 0.2, 2),
            "professionalism": min(score * 0.2, 2),
            "bonus": 1 if score >= 8 else 0,
            "total_score": score,
            "grade": grade,
            "need_follow_up": need_follow_up,
            "follow_up_question": follow_up_question,
            "strengths": ["态度积极"] if score >= 5 else [],
            "weaknesses": ["可以更加详细"] if score < 7 else [],
            "feedback": feedback
        }
    
    def get_transition_message(self, current_round, next_round_focus):
        """生成自然过渡语"""
        transitions = {
            1: "好的，了解了。那我想问问，这个产品具体是怎么发挥作用的呢？",
            2: "明白了。那在临床使用上，你们有什么数据支持吗？",
            3: "嗯，数据听起来不错。不过我想了解一下安全性方面的情况。",
            4: "安全性我了解了。那具体怎么使用？剂量和疗程是怎样的？",
            5: "用法我清楚了。说实话，我对价格还是有点顾虑...",
            6: "价格我能接受。但我还是有点担心长期使用的风险。",
            7: "好的，我明白了。那最后我想确认一下，如果我想试用，后续怎么跟进？",
        }
        
        return transitions.get(current_round, f"好的，我们继续。接下来聊聊{next_round_focus}。")
    
    def process_turn(self, user_message):
        """
        处理一轮对话（支持智能追问）
        """
        # 1. 记录用户消息
        self.messages.append({
            "role": "user",
            "content": user_message,
            "round": self.round,
            "timestamp": datetime.now().isoformat()
        })
        
        # 2. 获取医生回复
        doctor_response = self.get_doctor_response(user_message)
        
        # 3. 评估用户回答
        evaluation = self.evaluate_response(user_message, doctor_response)
        
        # 4. 检查是否需要追问
        need_follow_up = evaluation.get('need_follow_up', False)
        follow_up_question = evaluation.get('follow_up_question', '')
        
        if need_follow_up and self.follow_up_count < self.max_follow_up and evaluation.get('total_score', 0) < 6:
            # 需要追问
            self.follow_up_count += 1
            
            # 记录追问
            self.messages.append({
                "role": "doctor",
                "content": follow_up_question,
                "round": self.round,
                "is_follow_up": True,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "doctor_response": follow_up_question,
                "evaluation": None,  # 追问时不显示评分
                "round": self.round,
                "is_follow_up": True,
                "is_complete": False
            }
        
        # 5. 记录医生正式回复
        self.messages.append({
            "role": "doctor",
            "content": doctor_response,
            "round": self.round,
            "timestamp": datetime.now().isoformat()
        })
        
        # 6. 记录评分
        self.scores.append(evaluation)
        
        # 7. 重置追问计数
        self.follow_up_count = 0
        
        # 8. 生成自然过渡语（如果不是最后一轮）
        transition = None
        if self.round < 8:
            next_focus = self._get_next_round_focus(self.round + 1)
            transition = self.get_transition_message(self.round, next_focus)
        
        # 9. 增加轮数
        current_round = self.round
        self.round += 1
        
        return {
            "doctor_response": doctor_response,
            "evaluation": evaluation,
            "transition": transition,
            "round": current_round,
            "is_follow_up": False,
            "is_complete": self.round > 8
        }
    
    def _get_next_round_focus(self, round_num):
        """获取下一轮的关注点"""
        focuses = {
            2: "产品引入",
            3: "作用机制",
            4: "临床证据",
            5: "安全性讨论",
            6: "用法用量",
            7: "处理异议",
            8: "缔结与跟进"
        }
        return focuses.get(round_num, "继续讨论")
    
    def generate_final_report(self):
        """生成最终总结报告"""
        if not self.scores:
            return {"error": "还没有评分记录"}
        
        # 计算平均分
        avg_score = sum(s['total_score'] for s in self.scores) / len(self.scores)
        
        # 各维度平均分
        dimensions = ['content_accuracy', 'expression_clarity', 'customer_match', 'professionalism', 'bonus']
        dim_scores = {}
        for dim in dimensions:
            dim_scores[dim] = sum(s.get(dim, 0) for s in self.scores) / len(self.scores)
        
        # 统计亮点和改进点
        all_strengths = []
        all_weaknesses = []
        for s in self.scores:
            all_strengths.extend(s.get('strengths', []))
            all_weaknesses.extend(s.get('weaknesses', []))
        
        # 去重并取最常见的
        from collections import Counter
        top_strengths = [item for item, count in Counter(all_strengths).most_common(3)]
        top_weaknesses = [item for item, count in Counter(all_weaknesses).most_common(3)]
        
        # 生成总体评价
        if avg_score >= 9:
            overall = "🏆 优秀！你的销售话术非常专业，能够灵活应对各种场景。继续保持！"
            grade = "A"
        elif avg_score >= 7:
            overall = "🥈 良好！你掌握了基本的销售话术技巧，但在某些环节还有提升空间。多加练习会更出色！"
            grade = "B"
        elif avg_score >= 5:
            overall = "🥉 合格！你具备了基础的销售能力，建议系统学习产品知识和话术技巧。"
            grade = "C"
        else:
            overall = "📚 待提升！建议从基础开始学习，多观察优秀代表的话术，逐步提升专业能力。"
            grade = "D"
        
        # 生成学习建议
        suggestions = []
        if dim_scores.get('content_accuracy', 0) < 2:
            suggestions.append("加强产品知识学习，熟记关键数据")
        if dim_scores.get('expression_clarity', 0) < 1.5:
            suggestions.append("练习结构化表达，先讲结论再展开")
        if dim_scores.get('customer_match', 0) < 1.5:
            suggestions.append("多倾听医生需求，针对性回应关切")
        if dim_scores.get('professionalism', 0) < 1.5:
            suggestions.append("注意专业术语使用，提升专业形象")
        
        if not suggestions:
            suggestions.append("继续保持，向优秀迈进！")
        
        return {
            "overall_score": round(avg_score, 1),
            "grade": grade,
            "dimension_scores": {
                "内容准确性": round(dim_scores.get('content_accuracy', 0), 1),
                "表达清晰度": round(dim_scores.get('expression_clarity', 0), 1),
                "客户需求匹配": round(dim_scores.get('customer_match', 0), 1),
                "专业度": round(dim_scores.get('professionalism', 0), 1),
                "加分项": round(dim_scores.get('bonus', 0), 1)
            },
            "strengths": top_strengths if top_strengths else ["态度积极"],
            "weaknesses": top_weaknesses if top_weaknesses else ["继续努力"],
            "suggestions": suggestions,
            "overall_feedback": overall
        }


# 全局会话存储
ai_sessions = {}


def create_session(user_id, doctor_type, scenario, style_tags=None):
    """创建新的AI对话会话"""
    session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    engine = AI_DialogueEngine(session_id, doctor_type, scenario, style_tags)
    ai_sessions[session_id] = engine
    return session_id, engine


def process_message(session_id, message):
    """处理用户消息"""
    if session_id not in ai_sessions:
        return {"error": "会话不存在，请重新开始"}
    
    engine = ai_sessions[session_id]
    result = engine.process_turn(message)
    
    # 如果完成了，生成最终报告
    if result.get('is_complete'):
        result['final_report'] = engine.generate_final_report()
    
    return result


def get_session(session_id):
    """获取会话"""
    return ai_sessions.get(session_id)


def delete_session(session_id):
    """删除会话"""
    if session_id in ai_sessions:
        del ai_sessions[session_id]
        return True
    return False