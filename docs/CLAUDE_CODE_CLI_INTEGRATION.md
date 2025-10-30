# Claude Code CLI Integration Guide

이 문서는 prism-insight에서 Claude Code CLI를 LLM provider로 사용하는 방법을 설명합니다.

## 목차
- [개요](#개요)
- [사전 준비](#사전-준비)
- [설정 방법](#설정-방법)
- [사용 예제](#사용-예제)
- [마이그레이션 가이드](#마이그레이션-가이드)
- [트러블슈팅](#트러블슈팅)

---

## 개요

Claude Code CLI Integration은 Claude Code CLI 도구를 prism-insight의 LLM provider로 사용할 수 있게 해주는 어댑터입니다.

### 왜 필요한가?

- **로컬 실행**: Claude Code CLI는 로컬에서 실행되어 프로젝트 컨텍스트에 직접 접근할 수 있습니다.
- **전용 워크스페이스**: API 키 없이 Claude Code 전용 워크스페이스를 사용할 수 있습니다.
- **프로젝트 인식**: `-p` 옵션으로 프로젝트 루트를 지정하여 코드베이스를 이해할 수 있습니다.
- **통합**: 기존 prism-insight 코드를 최소한으로 수정하여 CLI를 사용할 수 있습니다.

### 아키텍처

```
prism-insight Agent
       ↓
ClaudeCodeCLIAugmentedLLM (mcp-agent 호환 wrapper)
       ↓
ClaudeCodeCLIProvider (subprocess 실행)
       ↓
claude CLI (로컬 실행)
```

---

## 사전 준비

### 1. Claude Code CLI 설치

Claude Code CLI가 시스템에 설치되어 있어야 합니다.

```bash
# 설치 방법은 공식 문서 참조
# https://docs.anthropic.com/claude/docs/claude-code
```

### 2. Claude Code CLI 인증

```bash
claude auth login
```

### 3. 설치 확인

```bash
# CLI가 정상 작동하는지 확인
claude --version

# 간단한 테스트
echo "Hello Claude" | claude --print
```

---

## 설정 방법

### 1. 환경변수 설정

`.env` 파일을 생성하고 다음 내용을 추가하세요:

```bash
# LLM Provider 선택
PRISM_LLM_PROVIDER=claude-code-cli

# Claude CLI 설정
CLAUDE_CLI_PATH=claude                           # claude 실행 파일 경로
CLAUDE_CLI_PROJECT=/home/user/prism-insight      # 프로젝트 루트 경로 (-p 옵션)
CLAUDE_CLI_MODEL=claude-3-5-sonnet-20241022      # 사용할 모델
CLAUDE_CLI_EXTRA_ARGS=--output-format stream-json --print
CLAUDE_CLI_TIMEOUT=180                           # 타임아웃 (초)
```

### 2. 설정 확인

Python에서 설정을 확인할 수 있습니다:

```python
from cores.llm_factory import get_provider_info, log_provider_config

# 설정 정보 출력
info = get_provider_info()
print(info)

# 또는 로그로 출력
log_provider_config()
```

---

## 사용 예제

### 예제 1: 기본 사용 (팩토리 함수 사용)

환경변수 설정만으로 자동으로 적절한 provider를 사용합니다:

```python
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm import RequestParams
from cores.llm_factory import get_default_llm_provider

async def analyze_stock():
    # Agent 생성
    agent = Agent(
        name="stock_analyzer",
        instruction="You are a stock analysis expert...",
        server_names=["kospi_kosdaq", "perplexity"]
    )

    # Provider 자동 선택 (환경변수 기반)
    provider_class = get_default_llm_provider()
    llm = await agent.attach_llm(provider_class)

    # 분석 실행
    report = await llm.generate_str(
        message="삼성전자(005930) 분석 보고서를 작성해주세요.",
        request_params=RequestParams(
            model="claude-3-5-sonnet-20241022",
            maxTokens=16000
        )
    )

    return report
```

### 예제 2: 직접 Provider 지정

```python
from mcp_agent.agents.agent import Agent
from cores.providers.claude_code_cli_augmented import ClaudeCodeCLIAugmentedLLM

async def analyze_with_cli():
    agent = Agent(
        name="analyzer",
        instruction="Analyze Korean stocks..."
    )

    # Claude CLI Provider 직접 사용
    llm = await agent.attach_llm(ClaudeCodeCLIAugmentedLLM)

    response = await llm.generate_str(
        message="시장 분석을 해주세요."
    )

    return response
```

### 예제 3: Provider 동적 선택

```python
from cores.llm_factory import get_llm_provider_class

async def analyze_with_fallback(use_cli=False):
    agent = Agent(name="analyzer", instruction="...")

    # CLI 사용 여부에 따라 선택
    provider_name = "claude-code-cli" if use_cli else "openai"
    provider_class = get_llm_provider_class(provider_name)

    llm = await agent.attach_llm(provider_class)
    response = await llm.generate_str(message="분석...")

    return response
```

---

## 마이그레이션 가이드

기존 코드를 Claude Code CLI provider로 마이그레이션하는 방법입니다.

### 방법 1: 환경변수만 변경 (권장)

**기존 코드 수정 없이** 환경변수만 변경하면 됩니다.

#### 1단계: 코드를 팩토리 함수로 변경

**변경 전:**
```python
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

llm = await agent.attach_llm(OpenAIAugmentedLLM)
```

**변경 후:**
```python
from cores.llm_factory import get_default_llm_provider

provider_class = get_default_llm_provider()
llm = await agent.attach_llm(provider_class)
```

#### 2단계: 환경변수 설정

`.env` 파일에서 `PRISM_LLM_PROVIDER`를 변경하면 자동으로 다른 provider 사용:

```bash
# OpenAI 사용
PRISM_LLM_PROVIDER=openai

# Claude Code CLI 사용
PRISM_LLM_PROVIDER=claude-code-cli
```

### 방법 2: 직접 Provider 지정

특정 파일/함수에서만 CLI를 사용하고 싶다면:

**변경 전:**
```python
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

llm = await agent.attach_llm(OpenAIAugmentedLLM)
```

**변경 후:**
```python
from cores.providers.claude_code_cli_augmented import ClaudeCodeCLIAugmentedLLM

llm = await agent.attach_llm(ClaudeCodeCLIAugmentedLLM)
```

### 실제 파일 마이그레이션 예제

**파일:** `cores/report_generation.py`

```python
# 변경 전
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

async def generate_report(agent, section, company_name, company_code, reference_date, logger):
    llm = await agent.attach_llm(OpenAIAugmentedLLM)
    report = await llm.generate_str(...)
```

```python
# 변경 후 (방법 1: 환경변수 기반)
from cores.llm_factory import get_default_llm_provider

async def generate_report(agent, section, company_name, company_code, reference_date, logger):
    provider_class = get_default_llm_provider()
    llm = await agent.attach_llm(provider_class)
    report = await llm.generate_str(...)
```

---

## 트러블슈팅

### 문제 1: "claude: command not found"

**원인:** Claude CLI가 설치되지 않았거나 PATH에 없음

**해결:**
```bash
# claude 실행 파일 경로 확인
which claude

# 절대 경로로 설정
export CLAUDE_CLI_PATH=/usr/local/bin/claude
```

### 문제 2: "Please login first"

**원인:** Claude CLI 인증이 안 됨

**해결:**
```bash
claude auth login
```

### 문제 3: Timeout 오류

**원인:** 분석 작업이 너무 오래 걸림

**해결:**
```bash
# .env에서 타임아웃 증가
CLAUDE_CLI_TIMEOUT=300
```

### 문제 4: 프로젝트 컨텍스트가 인식되지 않음

**원인:** `-p` 옵션 경로가 잘못됨

**해결:**
```bash
# 절대 경로로 설정
CLAUDE_CLI_PROJECT=/home/user/prism-insight
```

### 문제 5: JSON 파싱 오류

**원인:** CLI 출력이 JSON 형식이 아님

**해결:**
```bash
# stream-json 형식 명시
CLAUDE_CLI_EXTRA_ARGS=--output-format stream-json --print
```

또는 코드에서 fallback 처리됨 (plain text로 자동 처리)

### 문제 6: Import 오류

**원인:** mcp-agent 또는 관련 라이브러리 미설치

**해결:**
```bash
pip install -r requirements.txt
```

### 디버깅 팁

로깅을 활성화하여 상세 정보 확인:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from cores.llm_factory import log_provider_config
log_provider_config()
```

---

## 추가 정보

### 성능 고려사항

- **CLI 오버헤드**: subprocess 실행으로 인한 약간의 오버헤드가 있습니다 (일반적으로 무시할 수 있는 수준).
- **동시 실행**: 여러 CLI 프로세스를 동시에 실행할 수 있지만, 시스템 리소스를 고려하세요.
- **타임아웃**: 긴 분석 작업의 경우 타임아웃을 적절히 설정하세요.

### 보안 고려사항

- **API 키 불필요**: Claude Code CLI는 자체 인증을 사용하므로 API 키를 코드에 넣을 필요가 없습니다.
- **로컬 실행**: 모든 처리가 로컬에서 이루어지므로 민감한 데이터가 외부로 전송되지 않습니다.

### 제한사항

- **스트리밍**: 현재 구현은 전체 응답을 한 번에 받습니다. 실시간 스트리밍이 필요한 경우 추가 구현이 필요합니다.
- **도구 호출**: mcp-agent의 도구 호출 기능은 현재 제한적으로 지원됩니다.

---

## 참고 자료

- [Claude Code 공식 문서](https://docs.anthropic.com/claude/docs/claude-code)
- [mcp-agent 문서](https://github.com/anthropics/mcp-agent)
- [prism-insight README](../README.md)

---

## 기여

버그 리포트나 개선 제안은 GitHub Issues를 통해 제출해주세요.

## 라이선스

이 통합은 prism-insight의 라이선스를 따릅니다.
