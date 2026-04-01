#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - AI智能对话引擎
使用LLM生成医生回复、实时评估、个性化反馈
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
        """
        使用LLM生成医生回复
        """
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
        """
        调用LLM API
        支持多种模型：OpenAI、Claude、Kimi、MiniMax等
        """
        # 获取环境变量中的API配置
        model = os.environ.get('LLM_MODEL', 'moonshot/kimi-k2.5')
        api_key = os.environ.get('LLM_API_KEY', '')
        
        # 这里使用OpenClaw的模型调用方式
        # 实际部署时可以通过环境变量配置
        try:
            # 尝试使用OpenAI API
            if 'openai' in model or 'gpt' in model:
                return self._call_openai(messages, api_key)
            # 尝试使用Claude API
            elif 'claude' in model:
                return self._call_claude(messages, api_key)
            # 尝试使用MiniMax API
            elif 'minimax' in model.lower():
                return self._call_minimax(messages, api_key)
            # 默认使用Kimi/Moonshot
            else:
                return self._call_kimi(messages, api_key)
        except Exception as e:
            # 如果API调用失败，返回模拟回复
            return self._simulate_doctor_response(messages)
    
    def _call_openai(self, messages, api_key):
        """调用OpenAI API"""
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            return response.choices[0].message.content
        except ImportError:
            raise Exception("OpenAI模块未安装，请运行: pip install openai")
    
    def _call_claude(self, messages, api_key):
        """调用Claude API"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            
            # 提取system prompt
            system_msg = ""
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)
            
            response = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=200,
                system=system_msg,
                messages=user_messages
            )
            return response.content[0].text
        except ImportError:
            raise Exception("Anthropic模块未安装，请运行: pip install anthropic")
    
    def _call_kimi(self, messages, api_key):
        """调用Kimi/Moonshot API"""
        try:
            import openai
            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.moonshot.cn/v1"
            )
            response = client.chat.completions.create(
                model="moonshot-v1-8k",
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            return response.choices[0].message.content
        except ImportError:
            # 如果openai模块未安装，使用模拟回复
            return self._simulate_doctor_response(messages)
    
    def _call_minimax(self, messages, api_key):
        """调用MiniMax API"""
        import requests
        
        # MiniMax API配置
        group_id = os.environ.get('MINIMAX_GROUP_ID', '')
        url = f"https://api.minimax.chat/v1/text/chatcompletion_v2"
        
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
        """
        模拟医生回复（当API不可用时使用）
        基于角色特征和对话上下文生成合理回复
        """
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
        """
        eval_prompt = f"""你是一位销售培训专家，正在评估医药代表的回答质量。

**当前场景**：{self.scenario_info['description']}
**当前轮次**：第{self.round}轮
**医生角色**：{self.doctor_type}

**医生的问题/陈述**：
{doctor_context}

**医药代表的回答**：
{user_message}

**评估维度**（每项0-10分）：
1. 产品知识：是否准确传递了产品信息
2. 话术规范：是否使用了FAB、SPIN等技巧
3. 异议处理：是否有效回应了医生的顾虑
4. 沟通礼仪：称呼、语气是否得体
5. 专业形象：术语使用、自信度

**评分标准**：
- 9-10分：优秀，可以作为标杆
- 7-8分：良好，小有瑕疵
- 5-6分：合格，需要改进
- 0-4分：待提升，明显不足

请输出JSON格式：
{{
  "product_knowledge": 分数,
  "script_standard": 分数,
  "objection_handling": 分数,
  "communication": 分数,
  "professional": 分数,
  "total_score": 总分,
  "grade": "等级(A/B/C/D/F)",
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
            # 尝试从回复中提取JSON
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
        """
        基于规则的评分（当LLM不可用时使用）
        """
        score = 6  # 基础分
        
        # 关键词匹配加分
        keywords = {
            'product_knowledge': ['E2', '去势率', '97%', '微球', '亮丙瑞林', '子宫内膜异位症', '妊娠率', '87.3%'],
            'script_standard': ['优势', '特点', '效果', '数据', '临床'],
            'objection_handling': ['理解', '确实', '但是', '不过', '其实'],
            'communication': ['您', '主任', '教授', '打扰', '感谢'],
            'professional': ['适应症', '禁忌症', '不良反应', '用法用量']
        }
        
        strengths = []
        weaknesses = []
        
        for dimension, words in keywords.items():
            matches = sum(1 for w in words if w in user_message)
            if matches >= 2:
                score += 1
                if dimension == 'product_knowledge':
                    strengths.append("产品知识掌握扎实")
                elif dimension == 'script_standard':
                    strengths.append("话术运用得当")
                elif dimension == 'objection_handling':
                    strengths.append("异议处理技巧良好")
                elif dimension == 'communication':
                    strengths.append("沟通礼仪得体")
                elif dimension == 'professional':
                    strengths.append("专业形象良好")
        
        # 限制最高分
        score = min(score, 10)
        
        # 生成反馈
        if score >= 9:
            feedback = "🌟 表现优秀！话术专业、逻辑清晰，充分展示了产品价值。"
            grade = "A"
        elif score >= 7:
            feedback = "👍 表现良好，掌握了基本技巧，但在某些细节上可以更精进。"
            grade = "B"
        elif score >= 5:
            feedback = "💡 表现一般，建议加强对产品知识和话术技巧的学习。"
            grade = "C"
        else:
            feedback = "📝 需要改进！建议系统学习销售话术，从基础开始逐步提升。"
            grade = "D"
        
        if not strengths:
            weaknesses.append("建议多使用产品关键数据")
        
        return {
            "product_knowledge": min(score, 10),
            "script_standard": min(score - 1, 10),
            "objection_handling": min(score - 1, 10),
            "communication": min(score, 10),
            "professional": min(score - 1, 10),
            "total_score": score,
            "grade": grade,
            "strengths": strengths if strengths else ["态度积极"],
            "weaknesses": weaknesses if weaknesses else ["可以更加自信"],
            "feedback": feedback
        }
    
    def process_turn(self, user_message):
        """
        处理一轮对话
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
        
        # 4. 记录医生回复
        self.messages.append({
            "role": "doctor",
            "content": doctor_response,
            "round": self.round,
            "timestamp": datetime.now().isoformat()
        })
        
        # 5. 记录评分
        self.scores.append(evaluation)
        
        # 6. 增加轮数
        self.round += 1
        
        return {
            "doctor_response": doctor_response,
            "evaluation": evaluation,
            "round": self.round - 1,
            "is_complete": self.round > 8
        }
    
    def generate_final_report(self):
        """
        生成最终总结报告
        """
        if not self.scores:
            return {"error": "还没有评分记录"}
        
        # 计算平均分
        avg_score = sum(s['total_score'] for s in self.scores) / len(self.scores)
        
        # 各维度平均分
        dimensions = ['product_knowledge', 'script_standard', 'objection_handling', 'communication', 'professional']
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
        elif avg_score >= 7:
            overall = "🥈 良好！你掌握了基本的销售话术技巧，但在某些环节还有提升空间。多加练习会更出色！"
        elif avg_score >= 5:
            overall = "🥉 及格！你对产品有一定了解，但话术需要更加熟练。建议针对薄弱项进行专项训练。"
        else:
            overall = "📚 需改进！建议系统学习销售话术技巧，从基础开始逐步提升。不要气馁，多练习就会进步！"
        
        # 生成学习建议
        suggestions = []
        if dim_scores['product_knowledge'] < 7:
            suggestions.append("加强产品知识学习，熟记关键数据")
        if dim_scores['script_standard'] < 7:
            suggestions.append("练习FAB法则和SPIN技巧")
        if dim_scores['objection_handling'] < 7:
            suggestions.append("学习异议处理框架（APRC法则）")
        if dim_scores['communication'] < 7:
            suggestions.append("注意沟通礼仪和称呼规范")
        if dim_scores['professional'] < 7:
            suggestions.append("提升专业术语使用准确性")
        
        if not suggestions:
            suggestions.append("继续保持，可以尝试更高难度的医生角色")
        
        return {
            "overall_score": round(avg_score, 1),
            "grade": self._score_to_grade(avg_score),
            "dimension_scores": {k: round(v, 1) for k, v in dim_scores.items()},
            "strengths": top_strengths,
            "weaknesses": top_weaknesses,
            "overall_feedback": overall,
            "suggestions": suggestions,
            "total_rounds": len(self.scores)
        }
    
    def _score_to_grade(self, score):
        """分数转等级"""
        if score >= 9:
            return "A"
        elif score >= 7:
            return "B"
        elif score >= 5:
            return "C"
        elif score >= 4:
            return "D"
        else:
            return "F"


# 全局会话存储
ai_sessions = {}


def create_session(user_id, doctor_type, scenario, style_tags=None):
    """创建新会话"""
    session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    engine = AI_DialogueEngine(session_id, doctor_type, scenario, style_tags)
    ai_sessions[session_id] = engine
    
    return session_id, engine


def get_session(session_id):
    """获取会话"""
    return ai_sessions.get(session_id)


def process_message(session_id, user_message):
    """处理用户消息"""
    engine = get_session(session_id)
    if not engine:
        return {"error": "会话不存在或已过期"}
    
    result = engine.process_turn(user_message)
    
    # 如果完成了8轮，生成最终报告
    if result['is_complete']:
        result['final_report'] = engine.generate_final_report()
        # 清理会话
        del ai_sessions[session_id]
    
    return result


if __name__ == "__main__":
    # 测试
    session_id, engine = create_session("test_user", "科室主任", "完整拜访流程")
    print(f"会话创建: {session_id}")
    print(f"系统Prompt:\n{engine.system_prompt[:500]}...")
    
    # 模拟对话
    test_messages = [
        "主任您好，我是丽珠医药的小王，打扰您几分钟。",
        "我们新推出的维宝宁是注射用醋酸亮丙瑞林微球，E2去势率达到97.45%。",
        "是的，我们有III期临床数据支持，网状Meta分析涵盖了94项RCT研究。",
        "价格方面，维宝宁约1000元/支，虽然比竞品略高，但疗效更确切，患者依从性更好。",
        "不良反应发生率很低，长期安全性数据也很充分。",
        "我可以先给您带几份样品，您给几个患者试用一下。",
        "非常感谢主任的支持，我会定期来跟进患者用药情况的。",
        "谢谢主任，祝您工作顺利！"
    ]
    
    for msg in test_messages:
        print(f"\n用户: {msg}")
        result = process_message(session_id, msg)
        print(f"医生: {result['doctor_response']}")
        print(f"评分: {result['evaluation']['total_score']}/10 - {result['evaluation']['grade']}")
        print(f"反馈: {result['evaluation']['feedback']}")
        
        if result.get('final_report'):
            print(f"\n{'='*50}")
            print("最终报告:")
            print(json.dumps(result['final_report'], ensure_ascii=False, indent=2))
            break