---
name: hermes-job-management
description: Consume queued job-management requests, analyze jobs against candidate profile, and send Discord messages directly from Hermes Agent.
---

# Hermes Job Management

이 스킬은 `data/hermes_queue/requests/*.json` 요청 파일을 읽어 다음 작업을 수행한다.

1. 이력서 로우데이터와 채용공고 로우데이터를 읽는다.
2. 기존 Python 점수식이나 top-N 결과를 사용하지 않고 공고를 스스로 선별한다.
3. 선별 이유를 한국어로 요약한다.
4. Discord 메시지를 Hermes Agent가 직접 전송한다.
5. `responses/` 경로에 결과 JSON을 기록한다.

## Required Inputs

- `request_id`
- `candidate_profile`
- `jobs`
- `instructions.response_contract.response_file`

## Required Outputs

응답 파일에는 최소 아래 필드가 있어야 한다.

```json
{
  "request_id": "20260416_120000",
  "status": "completed",
  "selected_job_ids": ["gamejob_123"],
  "summary": "언리얼/클라이언트 중심 공고 3건 선별 후 전송 완료",
  "discord_sent": true
}
```

## Recommended skills.sh references

- `vercel-labs/agent-skills`
- `tool-belt/skills/python-executor`

## Queue Contract

- requests: `data/hermes_queue/requests/*.json`
- responses: `data/hermes_queue/responses/*.json`

## Notes

- 이 프로젝트에서는 Discord 전송 책임이 Python이 아니라 Hermes Agent에 있다.
- 필요 시 skills.sh 구조에 맞춰 `scripts/` 폴더에 실행 스크립트를 추가한다.
