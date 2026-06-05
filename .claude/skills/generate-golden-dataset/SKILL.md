---
name: generate-golden-dataset
description: 마크다운(.md) 파일들을 직접 읽고 분석하여 Golden Dataset(질문-답변 쌍 CSV)을 생성한다. RAGAS 없이 에이전트가 직접 생성.
argument-hint: [소스_디렉토리] [샘플_수] [출력_파일명]
arguments: [source_dir, num_samples, output_file]
disable-model-invocation: true
allowed-tools: Glob Read Write
---

# Golden Dataset 생성 (에이전트 직접 생성)

## 인수 기본값

| 인수 | 값 | 설명 |
|------|-----|------|
| source_dir | `$source_dir` | .md 파일이 있는 디렉토리 (필수) |
| num_samples | `$num_samples` | 생성할 Q&A 샘플 총 수 (기본값: 10) |
| output_file | `$output_file` | 출력 CSV 파일명 (기본값: golden_dataset.csv) |

인수가 비어있으면 위 기본값을 사용한다.

---

## 실행 절차

### 1단계: 문서 수집

- Glob으로 `$source_dir/**/*.md` 파일 목록을 가져온다.
- 파일이 없으면 실행을 중단하고 사용자에게 알린다.
- Read로 모든 .md 파일 내용을 읽는다.

### 2단계: 질문-답변 쌍 생성

읽은 문서들을 바탕으로 아래 4가지 유형의 질문을 균등하게 생성한다.
`$num_samples`가 4로 나누어 떨어지지 않으면 나머지는 `factual` 유형으로 채운다.

#### 질문 유형 정의

| synthesizer_name | 설명 | 예시 |
|-----------------|------|------|
| `single_hop_factual` | 단일 문서에서 직접 찾을 수 있는 구체적 사실 질문 | "X의 정의는 무엇인가?" |
| `single_hop_reasoning` | 단일 문서의 내용을 바탕으로 이유·원리를 묻는 질문 | "왜 X를 사용하는가?" |
| `multi_hop_comparative` | 2개 이상의 문서를 비교·대조해야 답할 수 있는 질문 | "A와 B의 차이점은?" |
| `multi_hop_synthesis` | 여러 문서의 정보를 종합해야 답할 수 있는 질문 | "X를 구현하려면 어떤 단계를 거치는가?" |

#### 생성 기준

- `user_input`: 자연스러운 한국어 질문 (문서의 내용을 그대로 복붙하지 말 것)
- `reference`: 문서에 근거한 완전하고 정확한 답변 (2~5문장)
- `reference_contexts`: 답변의 근거가 된 원문 발췌 (최대 500자, 여러 문서면 `|||` 로 구분)
- `source_file`: 참조한 파일명 (여러 개면 쉼표로 구분)

### 3단계: CSV 파일 저장

아래 헤더로 CSV를 Write 한다.

```
user_input,reference,reference_contexts,source_file,synthesizer_name
```

- 셀 안에 쉼표나 줄바꿈이 있으면 큰따옴표(`"`)로 감싼다.
- 인코딩: UTF-8 with BOM (`utf-8-sig` 호환 형식)
- 파일 경로: `$source_dir/../$output_file` (소스 디렉토리와 같은 레벨에 저장)

### 4단계: 완료 보고

작업이 끝나면 아래 내용을 사용자에게 보고한다.

- 처리한 .md 파일 수
- 유형별 생성된 샘플 수 (표 형식)
- 저장된 CSV 파일 경로
- 품질 주의사항: 생성된 질문 중 문서 내용과 불일치 가능성이 있는 항목이 있으면 명시

---

## 품질 기준

- 동일하거나 유사한 질문을 중복 생성하지 않는다.
- 답변은 반드시 제공된 문서 내용에만 근거한다. 추측이나 외부 지식을 사용하지 않는다.
- `multi_hop` 유형은 반드시 서로 다른 2개 이상의 파일에서 정보를 조합한다. 단일 파일만 참조한 경우 `single_hop`으로 분류한다.
- 질문은 에이전트 평가에 실제로 활용 가능한 수준으로 작성한다 (너무 단순하거나 자명한 질문 지양).
