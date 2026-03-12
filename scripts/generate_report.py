#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维宝宁销售话术对练 - 生成学习报告
统计用户学习进度和成绩
"""

import json
import os
import glob
from datetime import datetime, timedelta


def generate_report(user_id="anonymous", days=30):
    """
    生成用户学习报告
    """
    data_dir = os.path.expanduser("~/.openclaw/workspace/skills/weibaoning-sales-training/data/sessions")
    
    if not os.path.exists(data_dir):
        return {
            "error": "暂无学习记录",
            "user_id": user_id
        }
    
    # 加载用户的所有会话
    sessions = []
    pattern = os.path.join(data_dir, f"{user_id}_*.json")
    
    for session_file in glob.glob(pattern):
        with open(session_file, 'r', encoding='utf-8') as f:
            session = json.load(f)
            sessions.append(session)
    
    if not sessions:
        return {
            "error": "暂无学习记录",
            "user_id": user_id
        }
    
    # 按时间排序
    sessions.sort(key=lambda x: x.get("start_time", ""))
    
    # 统计信息
    total_practices = len(sessions)
    completed_practices = len([s for s in sessions if s.get("status") == "completed"])
    
    # 成绩统计
    scores = []
    for s in sessions:
        eval_data = s.get("evaluation", {})
        if "total_score" in eval_data:
            scores.append(eval_data["total_score"])
    
    if scores:
        average_score = sum(scores) / len(scores)
        max_score = max(scores)
        min_score = min(scores)
    else:
        average_score = max_score = min_score = 0
    
    # 维度分析
    dimension_scores = {
        "product_knowledge": [],
        "script_standard": [],
        "objection_handling": [],
        "communication": [],
        "professional": []
    }
    
    for s in sessions:
        eval_data = s.get("evaluation", {})
        scores_data = eval_data.get("scores", {})
        for key in dimension_scores:
            if key in scores_data:
                dimension_scores[key].append(scores_data[key])
    
    # 计算各维度平均分
    dimension_averages = {}
    for key, values in dimension_scores.items():
        if values:
            dimension_averages[key] = sum(values) / len(values)
        else:
            dimension_averages[key] = 0
    
    # 找出薄弱维度
    weak_dimensions = []
    dimension_names = {
        "product_knowledge": "产品知识",
        "script_standard": "话术规范",
        "objection_handling": "异议处理",
        "communication": "沟通礼仪",
        "professional": "专业形象"
    }
    
    for key, avg_score in dimension_averages.items():
        if avg_score < 70:
            weak_dimensions.append(dimension_names.get(key, key))
    
    # 计算进步趋势
    if len(scores) >= 2:
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        if second_avg > first_avg + 5:
            trend = "up"
            trend_desc = "进步明显"
        elif second_avg < first_avg - 5:
            trend = "down"
            trend_desc = "有所退步"
        else:
            trend = "stable"
            trend_desc = "保持稳定"
    else:
        trend = "stable"
        trend_desc = "数据不足"
    
    # 医生类型分布
    doctor_types = {}
    for s in sessions:
        doc_type = s.get("doctor_type", "未知")
        doctor_types[doc_type] = doctor_types.get(doc_type, 0) + 1
    
    # 场景分布
    scenarios = {}
    for s in sessions:
        scenario = s.get("scenario", "未知")
        scenarios[scenario] = scenarios.get(scenario, 0) + 1
    
    # 生成报告
    report = {
        "user_id": user_id,
        "generated_at": datetime.now().isoformat(),
        "period_days": days,
        "summary": {
            "total_practices": total_practices,
            "completed_practices": completed_practices,
            "completion_rate": round(completed_practices / total_practices * 100, 1) if total_practices > 0 else 0,
            "average_score": round(average_score, 1),
            "max_score": round(max_score, 1),
            "min_score": round(min_score, 1),
            "trend": trend,
            "trend_desc": trend_desc
        },
        "dimension_scores": {
            dimension_names.get(k, k): round(v, 1) 
            for k, v in dimension_averages.items()
        },
        "weak_dimensions": weak_dimensions,
        "doctor_type_distribution": doctor_types,
        "scenario_distribution": scenarios,
        "recent_sessions": [
            {
                "date": s.get("start_time", "")[:10],
                "doctor_type": s.get("doctor_type", ""),
                "scenario": s.get("scenario", ""),
                "score": round(s.get("evaluation", {}).get("total_score", 0), 1),
                "grade": s.get("evaluation", {}).get("grade", "N/A")
            }
            for s in sessions[-5:]  # 最近5次
        ],
        "recommendations": generate_study_recommendations(weak_dimensions, trend)
    }
    
    # 保存报告
    save_report(user_id, report)
    
    return report


def save_report(user_id, report):
    """保存报告"""
    report_dir = os.path.expanduser("~/.openclaw/workspace/skills/weibaoning-sales-training/data/reports")
    os.makedirs(report_dir, exist_ok=True)
    
    report_file = os.path.join(report_dir, f"{user_id}_report_{datetime.now().strftime('%Y%m%d')}.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def generate_study_recommendations(weak_dimensions, trend):
    """生成学习建议"""
    recommendations = []
    
    if weak_dimensions:
        recommendations.append(f"针对薄弱项进行专项训练：{', '.join(weak_dimensions)}")
    
    if trend == "down":
        recommendations.append("近期成绩有所下滑，建议加强练习频率")
    elif trend == "stable":
        recommendations.append("建议增加练习难度，挑战更高等级的医生角色")
    else:
        recommendations.append("继续保持学习热情，建议尝试新的对练场景")
    
    recommendations.extend([
        "每天至少进行一次对练练习",
        "重点关注产品知识和异议处理两大核心能力",
        "多进行不同类型的医生角色扮演",
        "定期回顾和总结每次对练的经验教训"
    ])
    
    return recommendations


def format_report_text(report):
    """格式化报告为文本"""
    if "error" in report:
        return report["error"]
    
    summary = report["summary"]
    
    text = f"""# 📊 维宝宁销售话术对练学习报告

**用户ID**: {report['user_id']}  
**报告时间**: {report['generated_at'][:10]}  
**统计周期**: 最近{report['period_days']}天

---

## 📈 总体表现

| 指标 | 数值 |
|------|------|
| 总练习次数 | {summary['total_practices']}次 |
| 完成次数 | {summary['completed_practices']}次 |
| 完成率 | {summary['completion_rate']}% |
| 平均分 | {summary['average_score']}分 |
| 最高分 | {summary['max_score']}分 |
| 最低分 | {summary['min_score']}分 |
| 进步趋势 | {summary['trend_desc']} |

---

## 📊 各维度得分

| 维度 | 平均分 |
|------|--------|
"""
    
    for dim, score in report['dimension_scores'].items():
        text += f"| {dim} | {score}分 |\n"
    
    if report['weak_dimensions']:
        text += f"""
---

## ⚠️ 薄弱项

{', '.join(report['weak_dimensions'])}
"""
    
    text += """
---

## 📚 学习建议

"""
    for i, rec in enumerate(report['recommendations'], 1):
        text += f"{i}. {rec}\n"
    
    text += """
---

## 📝 最近练习记录

| 日期 | 医生类型 | 场景 | 得分 | 等级 |
|------|---------|------|------|------|
"""
    
    for session in report['recent_sessions']:
        text += f"| {session['date']} | {session['doctor_type']} | {session['scenario']} | {session['score']} | {session['grade']} |\n"
    
    return text


if __name__ == "__main__":
    import sys
    
    user_id = sys.argv[1] if len(sys.argv) > 1 else "anonymous"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    report = generate_report(user_id, days)
    
    if "error" not in report:
        print(format_report_text(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
