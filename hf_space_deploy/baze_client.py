"""Project-only BAZE multimodal client. Does not modify agent or global settings."""
import json
import os
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent
BASE_URL = 'https://factchat-cloud.mindlogic.ai/v1/gateway'
DEFAULT_MODEL = 'gpt-6.1-sol'


def settings():
    # Narrow dotenv format: literal KEY=value, optional quotes, no shell execution.
    values = {}
    env_file = ROOT / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name, sep, value = line.partition('=')
            name, value = name.strip(), value.strip()
            if sep and name in ('BAZE_API_KEY', 'BAZE_MODEL'):
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                values[name] = value
    key = os.environ.get('BAZE_API_KEY', values.get('BAZE_API_KEY', '')).strip()
    model = os.environ.get('BAZE_MODEL', values.get('BAZE_MODEL', DEFAULT_MODEL)).strip()
    if not key:
        raise RuntimeError('프로젝트 .env 파일에 BAZE_API_KEY를 입력하세요.')
    if not model or any(c in model for c in '/:?\\'):
        raise ValueError('BAZE_MODEL에 유효한 모델 ID를 입력하세요.')
    return key, model


def request_json(method, path, payload=None, timeout=60):
    key, _ = settings()
    try:
        response = requests.request(method, BASE_URL + path,
            headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
            json=payload, timeout=timeout, allow_redirects=False)
    except requests.RequestException:
        raise RuntimeError('BAZE 네트워크 요청 실패. 연결 상태를 확인하세요.') from None
    if response.status_code != 200:
        hints = {401: '키 또는 BAZE 발급 배포를 확인하세요.',
                 403: '모델 권한 또는 계정 상태를 확인하세요.',
                 429: '호출 한도에 도달했습니다. 잠시 후 재시도하세요.'}
        raise RuntimeError(f'BAZE HTTP {response.status_code}: ' + hints.get(response.status_code, '요청 형식 또는 서비스 상태를 확인하세요.'))
    try:
        return response.json()
    except ValueError:
        raise RuntimeError('BAZE가 유효한 JSON 응답을 반환하지 않았습니다.') from None


def to_messages(contents):
    """Translate existing text/image few-shot contents without changing prompt text."""
    messages = []
    for turn in contents:
        role = 'assistant' if turn['role'] == 'model' else turn['role']
        blocks = []
        for part in turn['parts']:
            if 'text' in part:
                blocks.append({'type': 'text', 'text': part['text']})
            elif 'inline_data' in part:
                item = part['inline_data']
                blocks.append({'type': 'image_url', 'image_url': {
                    'url': f"data:{item['mime_type']};base64,{item['data']}"}})
            else:
                raise ValueError('Unsupported multimodal part')
        messages.append({'role': role, 'content': blocks})
    return messages


def parse_json_object(answer):
    try:
        result = json.loads(answer)
        if isinstance(result, dict):
            return result
        raise ValueError('Expected object')
    except json.JSONDecodeError:
        pass
    # Some providers prepend an explanation. Accept exactly one complete JSON
    # object; never synthesize coordinates or choose among competing answers.
    decoder = json.JSONDecoder()
    objects = []
    position = 0
    while position < len(answer):
        start = answer.find('{', position)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(answer[start:])
        except json.JSONDecodeError:
            position = start + 1
            continue
        if isinstance(value, dict):
            objects.append(value)
        position = start + end
    if len(objects) != 1:
        raise ValueError('Expected exactly one JSON object')
    return objects[0]


def call_baze_json(contents, generation_config=None, timeout=120, *, model=None,
                   max_tokens=16000):
    if generation_config and set(generation_config) - {'response_mime_type'}:
        raise ValueError('Unsupported generation configuration')
    if model is None:
        _, model = settings()
    payload = dict(model=model, messages=to_messages(contents), stream=False,
                   max_tokens=max_tokens)
    # JSON is requested in the shared prompt. Avoid provider-specific JSON-mode
    # or reasoning options so all three providers receive identical instructions.
    data = request_json('POST', '/chat/completions/', payload, timeout)
    usage = data.get('usage') or {}
    normalized = dict(promptTokenCount=usage.get('prompt_tokens'),
                      candidatesTokenCount=usage.get('completion_tokens'),
                      totalTokenCount=usage.get('total_tokens'), raw=usage)
    try:
        choice = data['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise ValueError('Incomplete output')
        answer = choice['message']['content']
        if isinstance(answer, list):
            answer = ''.join(p.get('text', '') for p in answer)
        answer = answer.strip()
        if answer.startswith('```') and answer.endswith('```'):
            answer = answer.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        result = parse_json_object(answer)
        if not isinstance(result, dict):
            raise ValueError('Expected object')
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        raise BazeOutputError('BAZE 모델이 완전한 JSON 객체를 반환하지 않았습니다.', normalized) from None
    return result, normalized


class BazeOutputError(RuntimeError):
    def __init__(self, message, usage):
        super().__init__(message)
        self.usage = usage


if __name__ == '__main__':
    # Auth/model-list check only; no guitar image is uploaded.
    data = request_json('GET', '/models/?type=llm')
    ids = [m['id'] for m in data.get('data', [])]
    print('Available LLM models:')
    for model in ids:
        print(model)
    _, selected = settings()
    if selected not in ids:
        raise SystemExit('Configured BAZE_MODEL is not available; update .env.')
    print('BAZE authentication and configured model: OK')
