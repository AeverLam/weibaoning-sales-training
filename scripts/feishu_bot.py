#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 飞书机器人消息处理器
部署在服务器上接收飞书消息并处理对练请求
"""

import json
import sys
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from start_practice import start_practice, load_session, save_session, DOCTOR_PROFILES, SCENARIOS
from evaluate_response import evaluate_response, generate_feedback

class FeishuMessageHandler:
    """飞书消息处理器"""
    
    def __init__(self):
        self.active_sessions = {}  # user_id -> session_id
        self.user_states = {}  # user_id -> state (idle/selecting/practicing)
        
    def parse_message(self, message_text: str, user_id: str) -> Dict:
        """解析用户消息，识别意图"""
        message_text = message_text.strip()
        
        # 意图识别规则
        patterns = {
            'start_practice': r'^(开始练习|开始对练|开始训练|start)$',
            'select_doctor': r'^(选择|选)?\s*([主任级专家|科室主任|主治医师|住院医师|带组专家|\d])',
            'query_knowledge': r'^(查询|知识|什么是|怎么|如何).+',
            'end_session': r'^(结束|退出|stop|quit)$',
            'view_report': r'^(查看报告|学习报告|我的成绩|report)$',
            'help': r'^(帮助|help|菜单|menu|指令)$',
        }
        
        for intent, pattern in patterns.items():
            if re.match(pattern, message_text, re.IGNORECASE):
                return {'intent': intent, 'text': message_text}
        
        # 默认：如果是练习状态，视为用户回答
        if self.user_states.get(user_id) == 'practicing':
            return {'intent': 'user_response', 'text': message_text}
        
        return {'intent': 'unknown', 'text': message_text}
    
    def handle_message(self, message_text: str, user_id: str, user_name: str = "") -> str:
        """处理用户消息并返回回复"""
        
        parsed = self.parse_message(message_text, user_id)
        intent = parsed['intent']
        text = parsed['text']
        
        # 路由到对应处理器
        handlers = {
            'start_practice': self._handle_start_practice,
            'select_doctor': self._handle_select_doctor,
            'user_response': self._handle_user_response,
            'query_knowledge': self._handle_query_knowledge,
            'end_session': self._handle_end_session,
            'view_report': self._handle_view_report,
            'help': self._handle_help,
            'unknown': self._handle_unknown,
        }
        
        handler = handlers.get(intent, self._handle_unknown)
        return handler(user_id, user_name, text)
    
    def _handle_start_practice(self, user_id: str, user_name: str, text: str) -> str:
        """处理开始练习指令"""
        self.user_states[user_id] = 'selecting'
        
        doctor_list = []
        for i, (key, profile) in enumerate(DOCTOR_PROFILES.items(), 1):
            difficulty_stars = '⭐' * profile['difficulty']
            doctor_list.append(
                f"{i}. 【{key}】{profile['title']}\n"
                f"   类型：{profile['type']} | 难度：{difficulty_stars}"
            )
        
        doctor_list_text = '\n\n'.join(doctor_list)
        return f"""👋 您好{user_name}！欢迎开始维宝宁销售话术对练。

请选择要练习的医生角色（回复数字或名称）：

{doctor_list_text}

💡 提示：建议从难度3星的【主治医师】开始练习"""
    
    def _handle_select_doctor(self, user_id: str, user_name: str, text: str) -> str:
        """处理选择医生指令"""
        # 解析医生类型
        doctor_types = list(DOCTOR_PROFILES.keys())
        
        # 尝试匹配数字
        number_match = re.search(r'(\d)', text)
        if number_match:
            idx = int(number_match.group(1)) - 1
            if 0 <= idx < len(doctor_types):
                doctor_type = doctor_types[idx]
            else:
                return "❌ 无效选择，请回复数字1-5选择医生角色"
        else:
            # 尝试匹配名称
            matched = False
            for dt in doctor_types:
                if dt in text:
                    doctor_type = dt
                    matched = True
                    break
            if not matched:
                return "❌ 无法识别医生类型，请回复数字1-5或医生名称"
        
        # 创建会话
        result = start_practice(doctor_type, "完整拜访流程", user_id)
        
        if result.get('success'):
            session_id = result['session_id']
            self.active_sessions[user_id] = session_id
            self.user_states[user_id] = 'practicing'
            
            doctor_profile = result['doctor_profile']
            
            return f"""✅ 对练开始！

👨‍⚕️ 【医生角色】{doctor_type}
🎭 【类型】{doctor_profile['type']}
⭐ 【难度】{'⭐' * result['difficulty']}
📋 【场景】完整拜访流程

---

👨‍⚕️ 医生："你是哪个公司的？找我有什么事？我只有2分钟时间。"

💬 请回复您的开场白："""
        else:
            return f"❌ 创建会话失败：{result.get('error', '未知错误')}"
    
    def _handle_user_response(self, user_id: str, user_name: str, text: str) -> str:
        """处理用户回答"""
        session_id = self.active_sessions.get(user_id)
        if not session_id:
            return '❌ 您还没有开始对练，请发送"开始练习"'
        
        # 评估回答
        eval_result = evaluate_response(session_id, text)
        
        if eval_result.get('error'):
            return f"❌ 评估失败：{eval_result['error']}"
        
        # 生成医生反馈（基于评估结果）
        session = load_session(session_id)
        if not session:
            return "❌ 会话已过期，请重新开始"
        
        doctor_type = session.get('doctor_type', '科室主任')
        round_num = len(session.get('messages', [])) + 1
        
        # 根据回答质量生成不同反馈
        evaluation_framework = eval_result.get('evaluation_framework', {})
        
        # 生成医生回复
        if round_num < 6:
            doctor_replies = {
                '科室主任': [
                    "你说这个产品疗效好，有什么临床数据支持吗？",
                    "价格怎么样？医保能报吗？",
                    "患者依从性如何？不良反应多不多？",
                    "用了这个能减轻我的工作负担吗？",
                    "行，我知道了。先开几盒试试看吧。"
                ],
                '主任级专家': [
                    "你们这个III期临床样本量有多大？",
                    "发表在什么期刊上？影响因子多少？",
                    "作用机制是什么？能详细说说吗？",
                    "和进口产品比有什么优势？",
                    "数据看起来还可以，我考虑一下。"
                ],
                '主治医师': [
                    "其他医院用得怎么样？",
                    "患者反馈如何？",
                    "使用起来方便吗？",
                    "适合我这类患者吗？",
                    "好，我先试用看看效果。"
                ]
            }
            
            default_replies = ["嗯，继续说说看。", "还有呢？", "你说的这些我了解了。", "那价格方面呢？", "可以考虑试用一下。"]
            replies = doctor_replies.get(doctor_type, default_replies)
            
            if round_num <= len(replies):
                doctor_reply = replies[round_num - 1]
            else:
                doctor_reply = "好的，今天的交流就到这里。"
        else:
            doctor_reply = "好的，今天的交流就到这里。谢谢你的介绍，我会考虑的。"
            # 结束会话并生成报告
            return self._handle_end_session(user_id, user_name, "结束")
        
        # 返回医生回复 + 评估反馈
        return f"""👨‍⚕️ 医生："{doctor_reply}"

💬 请继续回复：

---
📊 本轮评估（参考）：
请继续保持专业、自信的回答！"""
    
    def _handle_end_session(self, user_id: str, user_name: str, text: str) -> str:
        """处理结束会话"""
        session_id = self.active_sessions.get(user_id)
        if not session_id:
            return "您当前没有进行中的对练。"
        
        # 生成最终报告
        session = load_session(session_id)
        if session:
            messages = session.get('messages', [])
            round_count = len(messages)
            
            # 清理状态
            del self.active_sessions[user_id]
            self.user_states[user_id] = 'idle'
            
            return f"""📊 本次对练已结束！

📝 练习总结：
• 医生角色：{session.get('doctor_type', '未知')}
• 对话轮次：{round_count}轮
• 练习时长：约{round_count * 2}分钟

💡 建议：
• 多练习不同医生角色
• 重点关注异议处理技巧
• 熟记产品核心数据

发送"查看报告"查看详细学习报告
发送"开始练习"开始新的对练"""
        
        return "对练已结束。"
    
    def _handle_query_knowledge(self, user_id: str, user_name: str, text: str) -> str:
        """处理知识查询"""
        # 提取查询关键词
        keywords = text.replace('查询', '').replace('知识', '').replace('什么是', '').strip()
        
        # 从知识库搜索（简化版本）
        knowledge_base = {
            '维宝宁': '维宝宁®是首个国产长效曲普瑞林微球，用于前列腺癌和子宫内膜异位症治疗。',
            '去势率': '维宝宁III期临床去势率：第1月95.1%，第2-3月100%。',
            'psa': '维宝宁PSA应答率达96.55%，与亮丙瑞林疗效相当。',
            '不良反应': '常见不良反应：潮热、多汗、性欲减退等，多为1-2级。',
            '价格': '维宝宁1000元/支，已纳入医保乙类。',
            '用法': '3.75mg，臀部肌肉注射，每4周一次。',
        }
        
        for key, value in knowledge_base.items():
            if key in keywords or keywords in key:
                return f"📚 {key}：{value}\n\n更多知识请查阅完整知识库。"
        
        return f'📚 关于"{keywords}"的知识暂未找到，建议发送"开始练习"进行实战训练。'
    
    def _handle_view_report(self, user_id: str, user_name: str, text: str) -> str:
        """处理查看报告"""
        # 生成学习报告（简化版本）
        return f"""📊 {user_name}的学习报告

🎯 总体表现：
• 已完成对练：{len([s for s in self.active_sessions.values() if s])}次
• 平均得分：待计算
• 薄弱项：异议处理、竞品对比

📚 学习建议：
1. 加强APRC异议处理法则练习
2. 熟记维宝宁vs竞品的对比数据
3. 多练习高难度医生角色

💪 继续努力！"""
    
    def _handle_help(self, user_id: str, user_name: str, text: str) -> str:
        """处理帮助请求"""
        return """🤖 维宝宁销售话术对练助手 - 指令菜单

📋 常用指令：
• 开始练习 - 开始新的销售话术对练
• 结束 - 结束当前对练
• 查看报告 - 查看学习报告
• 帮助 - 显示本菜单

💡 练习流程：
1. 发送"开始练习"
2. 选择医生角色（1-5）
3. 根据医生提问回复销售话术
4. 系统自动评估并给出反馈
5. 发送"结束"查看学习报告

📚 知识查询：
• 可以直接提问，如"维宝宁的价格是多少？"
• 系统会从知识库中查找答案

🎯 提示：
• 建议每天练习15-20分钟
• 多练习不同医生角色
• 重点关注异议处理技巧"""
    
    def _handle_unknown(self, user_id: str, user_name: str, text: str) -> str:
        """处理未知指令"""
        return f"""🤔 不太理解您的意思："{text}"

请发送以下指令：
• "开始练习" - 开始销售话术对练
• "帮助" - 查看完整菜单

或者您可以直接提问维宝宁相关问题。"""


# 飞书消息处理入口
def handle_feishu_message(message_data: Dict) -> str:
    """飞书消息处理入口函数"""
    handler = FeishuMessageHandler()
    
    # 提取消息信息
    message_text = message_data.get('text', '')
    user_id = message_data.get('user_id', '')
    user_name = message_data.get('user_name', '')
    
    # 处理消息
    reply = handler.handle_message(message_text, user_id, user_name)
    
    return reply


# 本地测试入口
if __name__ == "__main__":
    # 测试用例
    handler = FeishuMessageHandler()
    test_user_id = "test_user_001"
    test_user_name = "测试用户"
    
    print("=" * 60)
    print("维宝宁销售话术对练 - 飞书机器人测试")
    print("=" * 60)
    
    # 测试场景1：开始练习
    print("\n【测试1】用户：开始练习")
    reply = handler.handle_message("开始练习", test_user_id, test_user_name)
    print(f"机器人：{reply[:200]}...")
    
    # 测试场景2：选择医生
    print("\n【测试2】用户：选择科室主任")
    reply = handler.handle_message("选择科室主任", test_user_id, test_user_name)
    print(f"机器人：{reply[:200]}...")
    
    # 测试场景3：用户回答
    print("\n【测试3】用户：销售回答")
    reply = handler.handle_message("主任您好，我是丽珠医药的小李，今天来向您介绍一下维宝宁...", test_user_id, test_user_name)
    print(f"机器人：{reply[:200]}...")
    
    # 测试场景4：帮助
    print("\n【测试4】用户：帮助")
    reply = handler.handle_message("帮助", test_user_id, test_user_name)
    print(f"机器人：{reply[:200]}...")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
