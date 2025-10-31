# LLM Provider 설정 가이드

이 문서는 prism-insight에서 다양한 LLM Provider를 사용하는 방법을 설명합니다.

## 목차

- [개요](#개요)
- [지원되는 Provider](#지원되는-provider)
- [설정 방법](#설정-방법)
- [Provider별 설정](#provider별-설정)
- [문제 해결](#문제-해결)

---

## 개요

prism-insight는 환경 변수를 통해 LLM Provider를 쉽게 교체할 수 있습니다.
**코드 수정 없이** `.env` 파일 설정만으로 다른 LLM을 사용할 수 있습니다.

### 장점

- ✅ **코드 수정 불필요**: 환경 변수만 변경
- ✅ **유연한 전환**: 개발/운영 환경별로 다른 Provider 사용 가능
- ✅ **비용 최적화**: 상황에 맞는 Provider 선택
- ✅ **테스트 용이**: 로컬에서 Claude Code CLI, 운영에서 OpenAI 등

---

## 지원되는 Provider

| Provider | 타입 | 특징 | 사용 사례 |
|----------|------|------|-----------|
| **OpenAI** | API | GPT-4, GPT-4 Turbo 등 | 범용적인 사용, 안정적 |
| **Anthropic** | API | Claude 3 Sonnet, Opus 등 | 긴 컨텍스트, 복잡한 분석 |
| **Claude Code CLI** | CLI | 로컬 실행, 프로젝트 인식 | 개발 환경, 로컬 테스트 |

---

## 설정 방법

### 1. .env 파일 생성

```bash
# .env.example을 복사하여 .env 파일 생성
cp .env.example .env
```

### 2. Provider 선택

`.env` 파일에서 `PRISM_LLM_PROVIDER` 값을 변경:

```bash
# OpenAI 사용 (기본값)
PRISM_LLM_PROVIDER=openai

# 또는 Anthropic 사용
PRISM_LLM_PROVIDER=anthropic

# 또는 Claude Code CLI 사용
PRISM_LLM_PROVIDER=claude-code-cli
```

### 3. 애플리케이션 실행

설정 완료 후 평소처럼 실행하면 자동으로 선택된 Provider를 사용합니다.

---

## Provider별 설정

### OpenAI (기본값)

#### 필수 설정

```bash
# .env
PRISM_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...  # OpenAI API 키
```

#### 특징

- ✅ 가장 안정적이고 범용적
- ✅ 빠른 응답 속도
- ⚠️ API 비용 발생

#### 모델 선택

코드에서 `RequestParams(model="gpt-4.1")` 등으로 지정

---

### Anthropic

#### 필수 설정

```bash
# .env
PRISM_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...  # Anthropic API 키
```

#### 특징

- ✅ 긴 컨텍스트 지원 (최대 200K 토큰)
- ✅ 복잡한 분석에 강점
- ⚠️ API 비용 발생

#### 모델 선택

코드에서 `RequestParams(model="claude-3-5-sonnet-20241022")` 등으로 지정

---

### Claude Code CLI

#### 사전 준비

1. **Claude Code CLI 설치**
   ```bash
   # 설치 방법은 공식 문서 참조
   # https://docs.anthropic.com/claude/docs/claude-code
   ```

2. **인증**
   ```bash
   claude auth login
   ```

3. **설치 확인**
   ```bash
   claude --version
   echo "Hello Claude" | claude --print
   ```

#### 필수 설정

```bash
# .env
PRISM_LLM_PROVIDER=claude-code-cli

# Claude CLI 실행 파일 경로 (PATH에 있으면 기본값 사용)
CLAUDE_CLI_PATH=claude

# 프로젝트 루트 경로 (CLI가 컨텍스트로 사용)
CLAUDE_CLI_PROJECT=/path/to/prism-insight

# 사용할 모델
CLAUDE_CLI_MODEL=claude-3-5-sonnet-20241022

# 타임아웃 (초 단위, 기본값: 180)
CLAUDE_CLI_TIMEOUT=180
```

#### 특징

- ✅ **로컬 실행**: 인터넷 연결 필요하지만 로컬에서 처리
- ✅ **프로젝트 인식**: `-p` 옵션으로 코드베이스 이해
- ✅ **개발 환경에 적합**: 빠른 프로토타이핑, 디버깅
- ⚠️ Claude Code 구독 필요
- ⚠️ OpenAI/Anthropic API 키 불필요

#### 고급 설정

```bash
# 추가 CLI 옵션 (선택사항)
CLAUDE_CLI_EXTRA_ARGS=--print

# Note: --output-format은 자동으로 'json'으로 설정됨
```

---

## 사용 예시

### 시나리오 1: 로컬 개발

```bash
# .env (로컬)
PRISM_LLM_PROVIDER=claude-code-cli
CLAUDE_CLI_PROJECT=/Users/yourname/prism-insight
CLAUDE_CLI_MODEL=claude-3-5-sonnet-20241022
```

**장점**: API 비용 없음, 프로젝트 컨텍스트 활용

### 시나리오 2: 운영 환경

```bash
# .env (운영)
PRISM_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-prod-...
```

**장점**: 안정성, 확장성

### 시나리오 3: 고급 분석

```bash
# .env (분석)
PRISM_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

**장점**: 긴 컨텍스트, 복잡한 추론

---

## Provider 확인 방법

### Python에서 확인

```python
from cores.llm_factory import get_provider_info, log_provider_config

# 현재 설정 확인
info = get_provider_info()
print(info)

# 또는 로그로 출력
log_provider_config()
```

### 출력 예시

```
============================================================
LLM Provider Configuration
============================================================
Provider: claude-code-cli
Is CLI-based: True
CLI Path: claude
CLI Project: /home/user/prism-insight
CLI Model: claude-3-5-sonnet-20241022
CLI Timeout: 180s
============================================================
```

---

## 문제 해결

### 문제 1: "ModuleNotFoundError: No module named 'mcp_agent'"

**원인**: mcp-agent 패키지가 설치되지 않음

**해결**:
```bash
pip install mcp-agent
```

### 문제 2: "OpenAI provider not available"

**원인**: OpenAI 패키지가 설치되지 않음

**해결**:
```bash
pip install openai mcp-agent
```

### 문제 3: "Anthropic provider not available"

**원인**: Anthropic 패키지가 설치되지 않음

**해결**:
```bash
pip install anthropic mcp-agent
```

### 문제 4: "Claude Code CLI provider not available"

**원인**: Claude Code CLI가 설치되지 않았거나 인증되지 않음

**해결**:
```bash
# 1. Claude Code CLI 설치 확인
claude --version

# 2. 인증
claude auth login

# 3. 테스트
echo "Hello" | claude --print
```

### 문제 5: "Unknown provider: xxx"

**원인**: 잘못된 Provider 이름

**해결**:
```bash
# .env에서 정확한 이름 사용
PRISM_LLM_PROVIDER=openai          # ✅
# PRISM_LLM_PROVIDER=gpt-4         # ❌ 잘못된 이름
# PRISM_LLM_PROVIDER=claude        # ❌ 'claude-code-cli' 또는 'anthropic' 사용
```

**유효한 옵션**:
- `openai`
- `anthropic`
- `claude-code-cli` (또는 `claude-cli`, `cli` 별칭 사용 가능)

---

## 고급 사용법

### Provider 오버라이드

코드에서 직접 Provider 지정:

```python
from cores.llm_factory import get_llm_provider_class

# 환경 변수 무시하고 특정 Provider 사용
provider_class = get_llm_provider_class("anthropic")
llm = await agent.attach_llm(provider_class)
```

### CLI 전용 기능

Claude Code CLI는 추가 기능을 지원합니다:

- **세션 관리**: `use_history=True`로 대화 컨텍스트 유지
- **병렬 처리**: `parallel_tool_calls=True`로 효율성 향상
- **최대 턴 제한**: `max_iterations` 설정

```python
response = await llm.generate_str(
    message="분석 요청",
    request_params=RequestParams(
        model="claude-3-5-sonnet-20241022",
        max_iterations=5,
        parallel_tool_calls=True,
        use_history=True
    )
)
```

---

## 참고 자료

- [Claude Code CLI 공식 문서](https://docs.anthropic.com/claude/docs/claude-code)
- [OpenAI API 문서](https://platform.openai.com/docs)
- [Anthropic API 문서](https://docs.anthropic.com/)

---

**작성일**: 2025-10-30
**버전**: 1.0
