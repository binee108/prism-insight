# Claude Code CLI - MCP 기능 지원 개선 계획

**작성일**: 2025-10-30
**목표**: Claude Code CLI에서 max_iterations, parallel_tool_calls, use_history 지원

---

## 📋 Executive Summary

Claude Code CLI는 다음 기능들로 MCP의 고급 기능을 지원할 수 있습니다:
- `--max-turns` → max_iterations 구현
- 프롬프트 수정 → parallel_tool_calls 구현
- `--resume <session_id>` → use_history 구현
- `--output-format json` → 풍부한 메타데이터 활용

---

## 🎯 Phase별 구현 계획

### Phase 1: --max-turns 지원 (간단, 즉시 구현 가능) ⭐

**목표**: max_iterations → --max-turns 매핑

**CLI 옵션**:
```bash
claude -p "query" --max-turns 3
```

**구현**:
```python
# cores/providers/claude_code_cli.py
def _build_command(
    self,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    max_turns: Optional[int] = None  # 추가
) -> List[str]:
    cmd = [self.cli_path]

    if max_turns is not None and max_turns > 0:
        cmd += ["--max-turns", str(max_turns)]

    # ... 기존 코드 ...
```

**변경 사항**:
- ✅ `_build_command()`: max_turns 파라미터 추가
- ✅ `generate()`, `generate_str()`: max_turns 전달
- ✅ `ClaudeCodeCLIAugmentedLLM`: max_iterations → max_turns 매핑

**영향도**: 낮음 (단순 매핑)
**리스크**: 거의 없음
**예상 작업 시간**: 15분

---

### Phase 2: --output-format json 파싱 (중간, 신중한 구현 필요) ⚠️

**목표**: 풍부한 메타데이터 활용 (session_id, usage, cost)

**CLI 출력 예시**:
```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 13559,
  "num_turns": 2,
  "result": "Hello! 👋 ...",
  "session_id": "35cc0414-e91a-4c23-96ce-f18c2553a653",
  "total_cost_usd": 0.0667337,
  "usage": {
    "input_tokens": 3,
    "cache_creation_input_tokens": 11938,
    "cache_read_input_tokens": 22179,
    "output_tokens": 253
  },
  "modelUsage": { ... },
  "uuid": "d49c1e11-a2f7-41e9-99c1-5ae112a9a655"
}
```

**구현 전략**:

#### 옵션 A: 기존 stream-json 유지 + 선택적 json 사용 (권장) ⭐

```python
def _build_command(self, ..., enable_session_tracking: bool = False):
    # ...

    # 세션 추적이 필요하면 json, 아니면 stream-json
    if enable_session_tracking:
        # json 형식으로 session_id 획득
        output_format = "json"
    else:
        # 기존 방식 유지
        output_format = "stream-json"

    if self.extra_args:
        # extra_args에서 output-format 제거하고 우리가 제어
        args = [arg for arg in shlex.split(self.extra_args)
                if not arg.startswith("--output-format")]
        cmd += args

    cmd += ["--output-format", output_format]
```

**장점**:
- ✅ 기존 코드 호환성 유지
- ✅ use_history가 필요한 경우만 json 사용
- ✅ 단계적 마이그레이션 가능

**단점**:
- ⚠️ 두 가지 파싱 로직 유지 필요

#### 옵션 B: 완전히 json으로 전환 (공격적)

**장점**:
- ✅ 단일 파싱 로직
- ✅ 더 많은 메타데이터 활용

**단점**:
- ❌ 스트리밍 지원 불가
- ❌ 기존 동작 변경

**권장**: **옵션 A** (선택적 사용)

**구현**:
```python
def _parse_output(self, raw_output: str, output_format: str = "stream-json") -> Dict[str, Any]:
    if output_format == "json":
        # 새로운 JSON 형식 파싱
        try:
            data = json.loads(raw_output)

            if data.get("is_error"):
                return {
                    "content": "",
                    "error": data.get("result", "Unknown error"),
                    "session_id": data.get("session_id")
                }

            return {
                "content": data.get("result", ""),
                "usage": {
                    "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                    "output_tokens": data.get("usage", {}).get("output_tokens", 0),
                    "cache_read_tokens": data.get("usage", {}).get("cache_read_input_tokens", 0),
                    "cache_creation_tokens": data.get("usage", {}).get("cache_creation_input_tokens", 0),
                },
                "session_id": data.get("session_id"),
                "total_cost_usd": data.get("total_cost_usd", 0),
                "num_turns": data.get("num_turns", 0),
                "duration_ms": data.get("duration_ms", 0),
            }
        except json.JSONDecodeError:
            # Fallback
            return {"content": raw_output, "usage": {}}

    else:
        # 기존 stream-json 파싱 로직 유지
        # ... 현재 코드 ...
```

**변경 사항**:
- ✅ `_parse_output()`: json 형식 지원 추가
- ✅ `_build_command()`: output_format 동적 선택
- ✅ 반환 dict에 session_id, cost, num_turns 추가

**영향도**: 중간
**리스크**: 중간 (파싱 로직 복잡도 증가)
**예상 작업 시간**: 30분

---

### Phase 3: parallel_tool_calls 프롬프트 수정 (간단) ⭐

**목표**: 병렬 처리 지시문을 프롬프트에 추가

**구현**:
```python
# cores/providers/claude_code_cli_augmented.py

def _build_prompt_with_directives(
    self,
    base_prompt: str,
    parallel_tool_calls: bool = False
) -> str:
    """Add system directives to prompt based on request params."""

    directives = []

    if parallel_tool_calls:
        directives.append(
            "SYSTEM DIRECTIVE: Task 도구를 사용하여 동시에 처리하는데 문제 없는 "
            "작업은 병렬로 처리를 진행하세요."
        )

    if directives:
        directive_text = "\n".join(directives)
        return f"{directive_text}\n\n{base_prompt}"

    return base_prompt


async def generate_str(self, message, request_params=None):
    # 파라미터 추출
    parallel_tool_calls = False
    if request_params:
        parallel_tool_calls = getattr(request_params, "parallel_tool_calls", False)

    # 프롬프트 수정
    full_prompt = self._build_prompt_with_directives(
        base_prompt=message,
        parallel_tool_calls=parallel_tool_calls
    )

    # ... 나머지 코드 ...
```

**변경 사항**:
- ✅ `_build_prompt_with_directives()`: 새 헬퍼 메서드
- ✅ `generate_str()`, `generate()`: 프롬프트 수정 적용
- ✅ 경고 로그 제거 (이제 지원하므로)

**영향도**: 낮음
**리스크**: 낮음 (프롬프트 변경이지만 CLI의 의도된 사용법)
**예상 작업 시간**: 20분

---

### Phase 4: use_history 세션 관리 (복잡, 신중한 설계 필요) 🚨

**목표**: --resume으로 대화 히스토리 유지

**CLI 옵션**:
```bash
# 첫 번째 호출
claude -p "hello?" --output-format json
# → session_id: "35cc0414-..."

# 두 번째 호출 (히스토리 이어서)
claude --resume 35cc0414-... -p "이전 대화 이어서"
```

**설계 고려사항**:

#### 1. 세션 저장소 설계

**옵션 A: Instance-level 저장 (권장)** ⭐
```python
class ClaudeCodeCLIAugmentedLLM:
    def __init__(self, agent=None, ...):
        self.agent = agent
        self.provider = ClaudeCodeCLIProvider(...)
        self.instruction = ...

        # 세션 관리
        self.current_session_id: Optional[str] = None
        self.use_history: bool = False
```

**장점**:
- ✅ Agent마다 독립적인 세션
- ✅ 간단한 구현
- ✅ Thread-safe (각 agent가 별도 인스턴스)

**단점**:
- ⚠️ Agent 재생성 시 히스토리 손실
- ⚠️ 서버 재시작 시 손실

**옵션 B: Global 캐시 (복잡)**
```python
# 전역 세션 저장소
_session_cache: Dict[str, str] = {}  # {agent_name: session_id}

class ClaudeCodeCLIAugmentedLLM:
    def __init__(self, agent=None, ...):
        self.agent_name = agent.name if agent else "default"
```

**장점**:
- ✅ Agent 재생성 후에도 히스토리 유지

**단점**:
- ❌ Thread-safety 문제
- ❌ 메모리 누수 가능성
- ❌ 복잡한 라이프사이클 관리

**권장**: **옵션 A** (Instance-level)

#### 2. 세션 라이프사이클

**질문**:
- 세션은 언제 시작되는가? → use_history=True인 첫 호출
- 세션은 언제 종료되는가? → 명시적 종료 메서드 or Agent 소멸
- 에러 발생 시 세션은? → 유지 (다음 호출에서 재사용)

**구현**:
```python
class ClaudeCodeCLIAugmentedLLM:
    async def generate_str(self, message, request_params=None):
        # 세션 관리 파라미터 추출
        use_history = False
        if request_params:
            use_history = getattr(request_params, "use_history", False)

        # 세션 활성화
        if use_history:
            self.use_history = True

        # 이전 세션이 있으면 resume
        resume_session = None
        if self.use_history and self.current_session_id:
            resume_session = self.current_session_id

        # Provider 호출 (resume 전달)
        result = await self.provider.generate_str(
            prompt=full_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_turns=max_turns,
            resume_session=resume_session,
            enable_session_tracking=self.use_history
        )

        # 새 세션 ID 저장
        if "session_id" in result:
            self.current_session_id = result["session_id"]
            logger.debug(f"Session ID updated: {self.current_session_id}")

        return result.get("content", "")

    def clear_history(self):
        """Clear conversation history."""
        self.current_session_id = None
        self.use_history = False
        logger.info("Conversation history cleared")
```

**Provider 레벨**:
```python
# cores/providers/claude_code_cli.py

async def generate_str(
    self,
    prompt: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    max_turns: Optional[int] = None,
    resume_session: Optional[str] = None,  # 추가
    enable_session_tracking: bool = False   # 추가
) -> str:
    cmd = self._build_command(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        max_turns=max_turns,
        resume_session=resume_session,
        enable_session_tracking=enable_session_tracking
    )

    # output_format 결정
    output_format = "json" if enable_session_tracking else "stream-json"

    result = await self._run_cli(cmd, prompt, output_format=output_format)

    if "error" in result and result["error"]:
        raise Exception(result["error"])

    return result.get("content", "")


def _build_command(
    self,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    max_turns: Optional[int] = None,
    resume_session: Optional[str] = None,  # 추가
    enable_session_tracking: bool = False
) -> List[str]:
    cmd = [self.cli_path]

    # Resume 세션
    if resume_session:
        cmd += ["--resume", resume_session]

    # 나머지 옵션들...

    # Output format (세션 추적 시 json)
    if enable_session_tracking:
        cmd += ["--output-format", "json"]
    else:
        # 기존 로직 (extra_args에서 가져오거나 기본값)
        if self.extra_args:
            cmd += shlex.split(self.extra_args)

    return cmd
```

**변경 사항**:
- ✅ `ClaudeCodeCLIAugmentedLLM`: session_id 관리
- ✅ `ClaudeCodeCLIProvider`: --resume 지원
- ✅ `_build_command()`: resume_session 파라미터
- ✅ `generate_str()`, `generate()`: 세션 관리 로직
- ✅ `clear_history()`: 명시적 세션 종료 메서드

**영향도**: 높음
**리스크**: 높음 (세션 관리 복잡성, 메모리 누수 가능성)
**예상 작업 시간**: 1시간

---

## 🔍 잠재적 이슈 및 해결 방안

### Issue 1: 세션 ID 충돌

**문제**: 여러 Agent가 동시에 작동할 때 세션 충돌
**해결**: Instance-level 저장소 사용 (각 Agent 인스턴스마다 독립적)

### Issue 2: 세션 메모리 누수

**문제**: 장시간 실행 시 session_id가 계속 쌓임
**해결**:
- TTL (Time To Live) 구현
- 명시적 `clear_history()` 메서드 제공
- Agent 소멸 시 세션도 정리

### Issue 3: --output-format 충돌

**문제**: extra_args에 --output-format이 있으면 충돌
**해결**: extra_args 파싱하여 --output-format 제거

```python
def _build_command(self, ...):
    cmd = [self.cli_path]

    # ... 다른 옵션들 ...

    # extra_args에서 output-format 제거
    if self.extra_args:
        args = shlex.split(self.extra_args)
        filtered_args = []
        skip_next = False
        for i, arg in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if arg == "--output-format":
                skip_next = True  # 다음 인자도 건너뛰기
                continue
            if arg.startswith("--output-format="):
                continue
            filtered_args.append(arg)
        cmd += filtered_args

    # 우리가 제어하는 output-format 추가
    if enable_session_tracking:
        cmd += ["--output-format", "json"]
    else:
        cmd += ["--output-format", "stream-json"]
```

### Issue 4: 병렬 처리 프롬프트 오버헤드

**문제**: 모든 요청에 병렬 처리 지시문 추가하면 토큰 낭비
**해결**: parallel_tool_calls=True일 때만 추가

### Issue 5: max_turns 기본값

**문제**: max_iterations가 설정되지 않았을 때 CLI 기본값 사용?
**해결**:
- max_iterations가 None이면 --max-turns 옵션을 추가하지 않음
- CLI의 기본 동작 유지

---

## 📊 구현 우선순위

### 즉시 구현 (Phase 1 + 2 + 3)
1. ✅ **Phase 1**: --max-turns (15분)
2. ✅ **Phase 2**: --output-format json 선택적 사용 (30분)
3. ✅ **Phase 3**: parallel_tool_calls 프롬프트 (20분)

**총 예상 시간**: ~1시간

### 선택적 구현 (Phase 4)
4. ⏸️ **Phase 4**: use_history 세션 관리 (1시간)
   - 복잡도가 높고 엣지 케이스 많음
   - 실제 필요성 검증 후 구현 권장

---

## 🧪 테스트 시나리오

### Test 1: max_iterations (--max-turns)
```python
# 3번 tool 호출 가능
response = await llm.generate_str(
    message="삼성전자 분석",
    request_params=RequestParams(
        model="claude-3-5-sonnet",
        max_iterations=3
    )
)
# CLI: claude -p "..." --max-turns 3
```

### Test 2: parallel_tool_calls
```python
# 병렬 처리 지시문 포함
response = await llm.generate_str(
    message="여러 주식 동시 분석",
    request_params=RequestParams(
        parallel_tool_calls=True
    )
)
# 프롬프트: "SYSTEM DIRECTIVE: Task 도구를 사용하여 ... 병렬로 처리\n\n여러 주식 동시 분석"
```

### Test 3: use_history
```python
# 첫 번째 호출
response1 = await llm.generate_str(
    message="삼성전자에 대해 알려줘",
    request_params=RequestParams(use_history=True)
)
# CLI: claude -p "..." --output-format json
# session_id 저장됨

# 두 번째 호출 (히스토리 이어서)
response2 = await llm.generate_str(
    message="그럼 SK하이닉스는?",
    request_params=RequestParams(use_history=True)
)
# CLI: claude --resume <session_id> -p "..."
# 이전 대화 컨텍스트 유지
```

### Test 4: 통합 테스트
```python
# 모든 기능 동시 사용
response = await llm.generate_str(
    message="여러 주식 분석",
    request_params=RequestParams(
        model="claude-3-5-sonnet",
        maxTokens=10000,
        temperature=0.7,
        max_iterations=3,
        parallel_tool_calls=True,
        use_history=True
    )
)
```

---

## 🚨 리스크 평가

### High Risk
- ❌ **Phase 4 (세션 관리)**: 복잡도 높음, 메모리 관리 필요

### Medium Risk
- ⚠️ **Phase 2 (output-format 변경)**: 파싱 로직 복잡도 증가

### Low Risk
- ✅ **Phase 1 (--max-turns)**: 단순 매핑
- ✅ **Phase 3 (프롬프트 수정)**: 프롬프트 변경만

---

## 💡 권장 구현 전략

### 최소 구현 (권장) ⭐
```
Phase 1 + Phase 2 (선택적) + Phase 3
```
- max_iterations, parallel_tool_calls 완전 지원
- use_history는 경고 유지 또는 간단한 구현
- 약 1시간 작업

### 완전 구현
```
Phase 1 + 2 + 3 + 4
```
- 모든 기능 지원
- 복잡도 높음
- 약 2-3시간 작업 + 충분한 테스트 필요

---

## ✅ 승인 요청 사항

다음 구현을 진행해도 될까요?

### 즉시 구현 제안:
1. ✅ **Phase 1**: --max-turns 매핑
2. ✅ **Phase 2**: --output-format json 선택적 사용 (use_history 필요 시만)
3. ✅ **Phase 3**: parallel_tool_calls 프롬프트 지시문

### 보류/선택적:
4. ⏸️ **Phase 4**: use_history 세션 관리
   - 옵션 A: 간단한 instance-level 구현
   - 옵션 B: 당분간 경고 유지, 향후 필요 시 구현

**승인 후 즉시 구현을 시작하겠습니다!** 🚀

각 Phase별로 문제가 있는지, 다른 접근 방법이 있는지 검토 부탁드립니다.
