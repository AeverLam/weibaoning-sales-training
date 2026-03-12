#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 回答评估
评估用户回答质量并生成反馈
"""

import json
import sys
import os
from start_practice import load_session, save_session


def evaluate_response(session_id, user_response, current_round=1):
    """
    评估用户回答
    """
    session = load_session(session_id)
    if not session:
        return {"error": "会话不存在或已过期"}
    
    doctor_type = session.get("doctor_type", "科室主任")
    scenario = session.get("scenario", "完整拜访流程")
    
    # 评估维度
    evaluation_criteria = {
        "product_knowledge": {
            "name": "产品知识",
            "weight": 25,
            "criteria": [
                "适应症准确",
                "用法用量正确",
                "核心卖点清晰",
                "竞品差异明确",
                "数据引用准确"
            ]
        },
        "script_standard": {
            "name": "话术规范",
            "weight": 20,
            "criteria": [
                "FAB应用得当",
                "SPIN技巧使用",
                "逻辑清晰",
                "结构完整",
                "语言专业"
            ]
        },
        "objection_handling": {
            "name": "异议处理",
            "weight": 25,
            "criteria": [
                "APRC法则应用",
                "倾听和认同",
                "回应有针对性",
                "证据支持",
                "转化成功"
            ]
        },
        "communication": {
            "name": "沟通礼仪",
            "weight": 15,
            "criteria": [
                "称呼得体",
                "语气恰当",
                "时间把握",
                "尊重对方",
                "结束语得当"
            ]
        },
        "professional": {
            "name": "专业形象",
            "weight": 15,
            "criteria": [
                "术语准确",
                "自信度",
                "准备充分",
                "态度积极",
                "专业知识"
            ]
        }
    }
    
    # 模拟评估结果（实际应该由LLM进行评估）
    # 这里返回评估框架，实际评估由调用方完成
    
    evaluation_result = {
        "session_id": session_id,
        "current_round": current_round,
        "user_response": user_response,
        "doctor_type": doctor_type,
        "scenario": scenario,
        "evaluation_framework": evaluation_criteria,
        "status": "pending_evaluation",
        "message": "请使用以下框架对回答进行评估"
    }
    
    # 更新会话
    session["messages"].append({
        "round": current_round,
        "user": user_response,
        "evaluation": evaluation_result
    })
    save_session(session)
    
    return evaluation_result


def generate_feedback(session_id, scores):
    """
    生成评估反馈报告
    """
    session = load_session(session_id)
    if not session:
        return {"error": "会话不存在"}
    
    # 计算总分
    total_score = 0
    max_score = 100
    
    weights = {
        "product_knowledge": 25,
        "script_standard": 20,
        "objection_handling": 25,
        "communication": 15,
        "professional": 15
    }
    
    for key, score in scores.items():
        if key in weights:
            total_score += score * (weights[key] / 100)
    
    # 确定等级
    if total_score >= 90:
        grade = "A"
        grade_desc = "优秀"
    elif total_score >= 80:
        grade = "B"
        grade_desc = "良好"
    elif total_score >= 70:
        grade = "C"
        grade_desc = "合格"
    elif total_score >= 60:
        grade = "D"
        grade_desc = "待提升"
    else:
        grade = "F"
        grade_desc = "需重新培训"
    
    # 找出薄弱点
    weaknesses = []
    for key, score in scores.items():
        if score < 70:
            weaknesses.append(key)
    
    # 生成改进建议
    improvement_suggestions = {
        "product_knowledge": "建议加强产品知识学习，熟记核心卖点和临床数据",
        "script_standard": "建议多练习FAB和SPIN技巧，提高话术规范性",
        "objection_handling": "建议深入学习APRC法则，多进行异议处理演练",
        "communication": "建议注意沟通礼仪，多观察优秀代表的拜访方式",
        "professional": "建议提升专业术语使用准确性，增强自信心"
    }
    
    # 构建反馈报告
    feedback = f"""【总体评价】{grade} ({total_score:.1f}/100) - {grade_desc}

【维度得分】
• 产品知识: {scores.get('product_knowledge', 0)}/25
• 话术规范: {scores.get('script_standard', 0)}/20  
• 异议处理: {scores.get('objection_handling', 0)}/25
• 沟通礼仪: {scores.get('communication', 0)}/15
• 专业形象: {scores.get('professional', 0)}/15

【亮点】
{generate_highlights(scores)}

【改进建议】
{generate_improvements(weaknesses, improvement_suggestions)}

【推荐练习】
{generate_recommendations(weaknesses)}
"""
    
    # 更新会话
    session["evaluation"] = {
        "scores": scores,
        "total_score": total_score,
        "grade": grade,
        "feedback": feedback,
        "weaknesses": weaknesses
    }
    session["status"] = "completed"
    save_session(session)
    
    return {
        "session_id": session_id,
        "total_score": total_score,
        "grade": grade,
        "grade_desc": grade_desc,
        "scores": scores,
        "weaknesses": weaknesses,
        "feedback": feedback
    }


def generate_highlights(scores):
    """生成亮点"""
    highlights = []
    
    if scores.get("product_knowledge", 0) >= 22:
        highlights.append("✓ 产品知识扎实，核心卖点阐述清晰")
    if scores.get("script_standard", 0) >= 18:
        highlights.append("✓ 话术规范，FAB应用得当")
    if scores.get("objection_handling", 0) >= 22:
        highlights.append("✓ 异议处理能力强，能有效化解医生顾虑")
    if scores.get("communication", 0) >= 13:
        highlights.append("✓ 沟通礼仪得体，拜访节奏把握得当")
    if scores.get("professional", 0) >= 13:
        highlights.append("✓ 专业形象良好，术语使用准确")
    
    if not highlights:
        highlights.append("✓ 态度积极，有学习意愿")
    
    return "\n".join(highlights)


def generate_improvements(weaknesses, suggestions):
    """生成改进建议"""
    if not weaknesses:
        return "整体表现良好，继续保持并精益求精"
    
    improvements = []
    for w in weaknesses:
        if w in suggestions:
            improvements.append(f"• {suggestions[w]}")
    
    return "\n".join(improvements)


def generate_recommendations(weaknesses):
    """生成推荐练习"""
    if not weaknesses:
        return "建议尝试更高难度的医生角色和场景"
    
    recommendations = []
    
    if "product_knowledge" in weaknesses:
        recommendations.append("• 产品知识专项训练")
    if "script_standard" in weaknesses:
        recommendations.append("• 开场白和产品介绍专项练习")
    if "objection_handling" in weaknesses:
        recommendations.append("• 异议处理专项训练（价格、竞品、安全性等）")
    if "communication" in weaknesses:
        recommendations.append("• 沟通礼仪和拜访节奏训练")
    if "professional" in weaknesses:
        recommendations.append("• 专业术语和自信心训练")
    
    return "\n".join(recommendations)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python evaluate_response.py <会话ID> <用户回答> [轮次]")
        sys.exit(1)
    
    session_id = sys.argv[1]
    user_response = sys.argv[2]
    current_round = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    
    result = evaluate_response(session_id, user_response, current_round)
    print(json.dumps(result, ensure_ascii=False, indent=2))
