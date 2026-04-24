import logging
import os

import redis
import requests
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Redis 连接
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

# Celery 配置
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')
app = Celery('tasks', broker=CELERY_BROKER_URL)

# 企业微信 API 配置
WECHAT_API_URL = os.getenv('WECHAT_API_URL', 'https://qyapi.weixin.qq.com/cgi-bin/message/send')
wx_token_key = os.getenv('WECHAT_ACCESS_TOKEN_KEY', 'wechat_access_token')

# Dify API 的 URL（替换为你的实际 URL）
DIFY_API_URL = os.getenv('DIFY_API_URL', 'http://xxx/v1/chat-messages')
DIFY_API_KEY = os.getenv('DIFY_API_KEY', 'xxx')


@app.task
def process_ai_request(userid, content, msg_id, agent_id, to_user_name):
    """
    处理 AI 请求，并将结果发送到企业微信
    """
    user_uuid = redis_client.get(userid)
    if not user_uuid:
        user_uuid = ""
    else:
        user_uuid = user_uuid.decode('utf-8')
        redis_client.expire(userid, 3600)  # 更新过期时间

    # 调用 Dify API
    payload = {
        "inputs": {},
        "query": f"{content}",
        "response_mode": "blocking",
        "conversation_id": f"{user_uuid}",
        "user": f"{userid}",
        "files": []
    }
    response = requests.post(DIFY_API_URL, headers={
        'Authorization': f'Bearer {DIFY_API_KEY}'
    }, json=payload)
    if response.status_code != 200:
        raise ValueError("Failed to call Dify API")
    ai_res = response.json()
    user_uuid = str(ai_res.get('conversation_id'))
    redis_client.set(userid, user_uuid, ex=3600)  # 设置 1 小时过期
    if ai_res.get('answer'):
        raw_answer = ai_res.get('answer')
        answer_parts = raw_answer.split("</think>", 1)
        if len(answer_parts) == 2:
            answer = answer_parts[1].strip()
        else:
            logging.warning("Dify answer missing </think> tag, using raw answer")
            answer = raw_answer.strip()
    else:
        answer = "服务器繁忙，请稍后再试"

    # 将消息和 userid 放入消息队列
    process_message.delay(userid, answer, agent_id)


@app.task
def process_message(userid, message, agent_id):
    """
    处理消息队列中的消息，并发送到企业微信
    """
    access_token = redis_client.get(wx_token_key)
    if not access_token:
        raise ValueError("Access token not found in Redis")

    access_token = access_token.decode('utf-8')
    payload = {
        "touser": userid,
        "msgtype": "text",
        "agentid": int(agent_id),
        "text": {
            "content": message
        },
    }
    params = {"access_token": access_token}
    response = requests.post(WECHAT_API_URL, params=params, json=payload)
    if response.status_code != 200:
        raise ValueError(f"Failed to send message to WeChat: HTTP {response.status_code}, {response.text}")

    response_data = response.json()
    if response_data.get("errcode") != 0:
        raise ValueError(
            "Failed to send message to WeChat: "
            f"errcode={response_data.get('errcode')}, errmsg={response_data.get('errmsg')}"
        )

    logging.warning(
        "Message sent to WeChat for user %s with agent_id %s",
        userid,
        agent_id,
    )
