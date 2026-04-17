

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'version': 'ai-v2.0', 'features': ['AI智能对话', '实时评估', '智能追问', '自然过渡', '个性化反馈']})


@app.route('/webhook/feishu', methods=['POST', 'GET'])
def webhook():
    try:
        if request.method == 'GET':
            return jsonify({'status': 'ok'})
        
        data = request.get_json() or {}
        
        # 处理挑战验证
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
                
                # 清理@机器人的内容
                text = text.replace('@_user_1', '').replace('@维宝宁销售训练助手', '').strip()
                
                user_id = sender.get('sender_id', {}).get('open_id', '')
                msg_id = message.get('message_id', '')
                
                if text and user_id:
                    reply = handle_msg(text, user_id, msg_id)
                    
                    # 如果返回的是元组（文本+卡片）
                    if isinstance(reply, tuple):
                        text_reply, card_data = reply
                        send_msg(user_id, msg_id, text_reply)
                        send_card(user_id, msg_id, card_data)
                    else:
                        send_msg(user_id, msg_id, reply)
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/practice/start', methods=['POST'])
def api_start_practice():
    """API：开始对练"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'anonymous')
    doctor_type = data.get('doctor_type', '科室主任')
    scenario = data.get('scenario', '完整拜访流程')
    style_tags = data.get('style_tags', [])
    
    session_id, engine = create_session(user_id, doctor_type, scenario, style_tags)
    user_sessions[user_id] = session_id
    
    # 获取医生开场白
    doctor_opening = engine.get_doctor_response("你好，我是丽珠医药的代表。")
    
    return jsonify({
        'status': 'ok',
        'session_id': session_id,
        'doctor_type': doctor_type,
        'scenario': scenario,
        'doctor_opening': doctor_opening,
        'round': 1,
        'total_rounds': 8
    })


@app.route('/api/practice/message', methods=['POST'])
def api_send_message():
    """API：发送消息"""
    data = request.get_json() or {}
    session_id = data.get('session_id')
    user_message = data.get('message', '')
    
    if not session_id:
        return jsonify({'status': 'error', 'message': '缺少session_id'}), 400
    
    result = process_message(session_id, user_message)
    
    if 'error' in result:
        return jsonify({'status': 'error', 'message': result['error']}), 400
    
    response = {
        'status': 'ok',
        'doctor_response': result['doctor_response'],
        'evaluation': result['evaluation'],
        'round': result['round'],
        'is_follow_up': result.get('is_follow_up', False),
        'transition': result.get('transition', ''),
        'is_complete': result['is_complete']
    }
    
    if result.get('final_report'):
        response['final_report'] = result['final_report']
    
    return jsonify(response)


@app.route('/api/practice/report/<session_id>', methods=['GET'])
def api_get_report(session_id):
    """API：获取报告"""
    from scripts.ai_dialogue_engine import get_session
    
    engine = get_session(session_id)
    if not engine:
        return jsonify({'status': 'error', 'message': '会话不存在'}), 404
    
    report = engine.generate_final_report()
    return jsonify({'status': 'ok', 'report': report})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)